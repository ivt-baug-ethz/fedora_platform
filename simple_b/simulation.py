"""SUMO simulation FSM for the simplified simple_b system."""

from __future__ import annotations

import json
import os
import random
import shutil
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any


class Simulation:
    """Run SUMO through TraCI and exchange traffic state over TCP."""

    NAME = "simulation"
    STATE_CREATED = "created"
    STATE_CONFIGURED = "configured"
    STATE_READY = "ready"
    STATE_RUNNING = "running"
    STATE_STOPPED = "stopped"
    STATE_FAILED = "failed"

    STATES = (
        STATE_CREATED,
        STATE_CONFIGURED,
        STATE_READY,
        STATE_RUNNING,
        STATE_STOPPED,
        STATE_FAILED,
    )
    TRANSITIONS = {
        STATE_CREATED: {
            "configure": STATE_CONFIGURED,
            "stop": STATE_STOPPED,
            "fail": STATE_FAILED,
        },
        STATE_CONFIGURED: {
            "prepare": STATE_READY,
            "stop": STATE_STOPPED,
            "fail": STATE_FAILED,
        },
        STATE_READY: {"start": STATE_RUNNING, "stop": STATE_STOPPED, "fail": STATE_FAILED},
        STATE_RUNNING: {"stop": STATE_STOPPED, "fail": STATE_FAILED},
        STATE_STOPPED: {"configure": STATE_CONFIGURED, "fail": STATE_FAILED},
        STATE_FAILED: {"stop": STATE_STOPPED},
    }

    def __init__(self, configuration: dict[str, Any]):
        """Create the simulation in the CREATED state."""
        self.configuration = configuration
        self.state = self.STATE_CREATED
        self.base_path = Path(__file__).resolve().parent
        self.host = "127.0.0.1"
        self.port = 0
        self.connector = ("127.0.0.1", 0)
        self.sumo_binary = "sumo-gui"
        self.sumo_config_file = self.base_path / "sumo_simulation_files" / "Configuration.sumocfg"
        self.sumo_label = "simple_b"
        self.traffic_lights: list[str] = []
        self.phase_bidder_lanes: dict[str, dict[str, list[str]]] = {}
        self.route_probabilities: dict[str, dict[str, float]] = {}
        self.spawn_probabilities: dict[str, float] = {}
        self.vot_spawn_probabilities: dict[str, float] = {}
        self.vot_upp_spawn_probabilities: dict[str, float] = {}
        self.vehicle_colors: dict[str, tuple[int, int, int, int]] = {}
        self.sensor_distance = 100.0
        self.position_distances: list[float] = []
        self.position_weights: list[float] = []
        self.spawn_horizon = 0
        self.max_steps = 0
        self.step_delay_seconds = 0.0
        self.controller_response_timeout_seconds = 0.05
        self.random = random.Random()
        self.connection: Any | None = None
        self.traci_module: Any | None = None
        self.time = 0.0
        self.step = 0
        self.vehicle_counter = 0
        self.vehicle_upp: dict[str, int] = {}
        self.vehicle_ids: list[str] = []
        self.vehicle_lanes: dict[str, str] = {}
        self.vehicle_lane_positions: dict[str, float] = {}
        self.lane_lengths: dict[str, float] = {}
        self.pending_commands: dict[str, int] = {}
        self.command_event = threading.Event()
        self.command_lock = threading.Lock()
        self.done_event = threading.Event()
        self.stop_event = threading.Event()
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.run_thread: threading.Thread | None = None
        self.last_error: str | None = None

    def configure(self) -> "Simulation":
        """Load paths, metadata, and runtime settings, then enter CONFIGURED."""
        self._transition("configure")
        self.host = str(self.configuration.get("host", "127.0.0.1"))
        self.port = int(self.configuration["port"])
        connector = self.configuration["connector"]
        self.connector = (str(connector["host"]), int(connector["port"]))
        self.sumo_binary = self._resolve_sumo_binary(
            str(self.configuration.get("sumo_binary", "sumo-gui"))
        )
        self.sumo_config_file = self._resolve_path(str(self.configuration["sumo_config_file"]))
        self.sumo_label = str(self.configuration.get("sumo_label", "simple_b"))
        self.traffic_lights = list(self.configuration.get("traffic_lights", []))
        self.phase_bidder_lanes = self._load_json_file("phase_bidder_lanes_file")
        self.route_probabilities = self._load_json_file("route_probabilities_file")
        self.spawn_probabilities = self._build_spawn_probabilities()
        self.vot_spawn_probabilities = dict(self.configuration["vot_spawn_probabilities"])
        self.vot_upp_spawn_probabilities = dict(self.configuration["vot_upp_spawn_probabilities"])
        self.vehicle_colors = self._build_vehicle_colors()
        self.sensor_distance = float(self.configuration.get("sensor_distance", 100.0))
        self.position_distances = [
            float(value)
            for value in self.configuration.get("position_distance_to_intersection", [])
        ]
        self.position_weights = [
            float(value)
            for value in self.configuration.get("position_weights", [1.0])
        ]
        self.spawn_horizon = int(self.configuration.get("spawn_horizon", 0))
        self.max_steps = int(self.configuration.get("max_steps", 0))
        self.step_delay_seconds = float(self.configuration.get("step_delay_seconds", 0.0))
        self.controller_response_timeout_seconds = float(
            self.configuration.get("controller_response_timeout_seconds", 0.05)
        )
        self.random.seed(int(self.configuration.get("random_seed", 42)))
        return self

    def start(self) -> None:
        """Open the TCP listener, start SUMO GUI, and enter RUNNING."""
        if self.state == self.STATE_CREATED:
            self.configure()
        if self.state == self.STATE_CONFIGURED:
            self._open_server()
            self._open_sumo()
            self._transition("prepare")
        self._transition("start")
        self.run_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.run_thread.start()

    def stop(self) -> None:
        """Stop SUMO, stop the TCP listener, and enter STOPPED."""
        if self.state == self.STATE_STOPPED:
            return
        self.stop_event.set()
        self.done_event.set()
        if self.server_socket is not None:
            self.server_socket.close()
        if self.connection is not None:
            try:
                self.connection.close()
            except (AttributeError, OSError):
                pass
            self.connection = None
        self._transition("stop")

    def wait_until_done(self) -> None:
        """Block until the simulation loop completes."""
        self.done_event.wait()
        if self.run_thread is not None:
            self.run_thread.join(timeout=5.0)

    def fail(self, error: Exception | str) -> None:
        """Record an unrecoverable error and enter FAILED."""
        self.last_error = str(error)
        if self.state != self.STATE_FAILED:
            self._transition("fail")
        self.done_event.set()

    def _transition(self, event: str) -> None:
        next_state = self.TRANSITIONS.get(self.state, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"Simulation cannot {event} from {self.state}")
        self.state = next_state

    def _resolve_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        return self.base_path / path

    def _resolve_sumo_binary(self, binary_name: str) -> str:
        configured_path = Path(binary_name)
        if configured_path.is_file():
            return str(configured_path)
        path_binary = shutil.which(binary_name)
        if path_binary is not None:
            return path_binary

        executable_name = "sumo-gui.exe" if "gui" in binary_name.lower() else "sumo.exe"
        candidates = self._sumo_binary_candidates(executable_name)
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        searched = "\n".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(
            f"Could not find SUMO executable '{binary_name}'. "
            "Put SUMO on PATH, set SUMO_HOME, or set simulation.sumo_binary in config.json "
            f"to the executable path. Checked:\n{searched}"
        )

    def _sumo_binary_candidates(self, executable_name: str) -> list[Path]:
        candidates = []
        sumo_home = os.environ.get("SUMO_HOME")
        if sumo_home:
            candidates.append(Path(sumo_home) / "bin" / executable_name)
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            local_path = Path(local_app_data)
            candidates.extend(
                sorted(local_path.glob(f"sumo-*\\bin\\{executable_name}"), reverse=True)
            )
            candidates.append(local_path / "sumo-1.19.0" / "bin" / executable_name)
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            candidates.append(Path(program_files) / "Eclipse" / "Sumo" / "bin" / executable_name)
        return candidates

    def _load_json_file(self, key: str) -> dict[str, Any]:
        path = self._resolve_path(str(self.configuration[key]))
        with path.open("r", encoding="utf-8") as json_file:
            return json.load(json_file)

    def _build_spawn_probabilities(self) -> dict[str, float]:
        configured = self.configuration.get("spawn_probabilities")
        if configured:
            return {str(key): float(value) for key, value in configured.items()}
        probability = float(self.configuration["flow_per_entrance_per_hour"]) / 3600.0
        return {entrance: probability for entrance in self.route_probabilities}

    def _build_vehicle_colors(self) -> dict[str, tuple[int, int, int, int]]:
        colors = dict(self.configuration.get("vehicle_colors", {}))
        return {
            name: tuple(int(channel) for channel in value)
            for name, value in colors.items()
        }

    def _open_server(self) -> None:
        self.stop_event.clear()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.server_thread = threading.Thread(target=self._serve, daemon=True)
        self.server_thread.start()

    def _serve(self) -> None:
        while not self.stop_event.is_set():
            try:
                assert self.server_socket is not None
                client, _address = self.server_socket.accept()
            except OSError:
                break
            thread = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
            thread.start()

    def _handle_client(self, client: socket.socket) -> None:
        with client:
            data = b""
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                data += chunk
        for line in data.decode("utf-8").splitlines():
            if line.strip():
                self._handle_message(json.loads(line))

    def _handle_message(self, message: dict[str, Any]) -> None:
        if message.get("topic") == "traffic_light_command":
            payload = dict(message.get("payload", {}))
            commands = {
                str(traffic_light): int(phase)
                for traffic_light, phase in dict(payload.get("commands", {})).items()
            }
            with self.command_lock:
                self.pending_commands.update(commands)
                self.command_event.set()
        elif message.get("topic") == "shutdown":
            self.stop_event.set()

    def _open_sumo(self) -> None:
        if "SUMO_HOME" in os.environ:
            tools_path = os.path.join(os.environ["SUMO_HOME"], "tools")
            if tools_path not in sys.path:
                sys.path.append(tools_path)
        import traci

        self.traci_module = traci
        command = [
            self.sumo_binary,
            "-c",
            str(self.sumo_config_file),
            "--start",
            "--quit-on-end",
            "--time-to-teleport",
            "-1",
        ]
        traci.start(command, label=self.sumo_label)
        self.connection = traci.getConnection(self.sumo_label)
        self._crawl_initial_traci_data()
        self._send_message("controller", "simulation_started", {"label": self.sumo_label})

    def _crawl_initial_traci_data(self) -> None:
        assert self.connection is not None
        self.lane_lengths = {
            lane: float(self.connection.lane.getLength(lane))
            for lane in self.connection.lane.getIDList()
        }

    def _run_loop(self) -> None:
        try:
            while not self.stop_event.is_set() and not self._criterion_to_abort():
                self._run_step()
                if self.step_delay_seconds > 0:
                    time.sleep(self.step_delay_seconds)
            self._send_message(
                "controller",
                "simulation_stopped",
                {"time": self.time, "step": self.step},
            )
        except Exception as error:
            self.fail(error)
        finally:
            self.done_event.set()

    def _criterion_to_abort(self) -> bool:
        if self.max_steps and self.step >= self.max_steps:
            return True
        if self.connection is None:
            return True
        if self.time <= self.spawn_horizon:
            return False
        return int(self.connection.vehicle.getIDCount()) == 0

    def _run_step(self) -> None:
        assert self.connection is not None
        self._spawn_vehicles()
        self._crawl_step_traci_data()
        self._send_message("controller", "traffic_state", self._build_traffic_state())
        self.command_event.wait(self.controller_response_timeout_seconds)
        self.command_event.clear()
        self._apply_pending_commands()
        self.connection.simulationStep()
        self.step += 1

    def _spawn_vehicles(self) -> None:
        assert self.connection is not None
        if self.time >= self.spawn_horizon:
            return
        for entrance, probability in self.spawn_probabilities.items():
            if self.random.random() > probability:
                continue
            route = self._weighted_choice(self.route_probabilities[entrance])
            vot = self._weighted_choice(self.vot_spawn_probabilities)
            upp_probability = float(self.vot_upp_spawn_probabilities.get(str(vot), 0.0))
            upp = int(self.random.random() < upp_probability)
            vehicle_id = f"v_{self.vehicle_counter}"
            self.vehicle_counter += 1
            self.vehicle_upp[vehicle_id] = upp
            self.connection.vehicle.add(vehicle_id, route)
            color_key = "priority_pass" if upp else "regular"
            if color_key in self.vehicle_colors:
                self.connection.vehicle.setColor(vehicle_id, self.vehicle_colors[color_key])

    def _weighted_choice(self, weights_by_item: dict[str, float]) -> str:
        total_weight = sum(float(weight) for weight in weights_by_item.values())
        threshold = self.random.random() * total_weight
        cumulative = 0.0
        for item, weight in weights_by_item.items():
            cumulative += float(weight)
            if cumulative >= threshold:
                return str(item)
        return str(next(reversed(weights_by_item)))

    def _crawl_step_traci_data(self) -> None:
        assert self.connection is not None
        self.time = float(self.connection.simulation.getTime())
        self.vehicle_ids = list(self.connection.vehicle.getIDList())
        self.vehicle_lanes = {}
        self.vehicle_lane_positions = {}
        for vehicle_id in self.vehicle_ids:
            lane = str(self.connection.vehicle.getLaneID(vehicle_id))
            self.vehicle_lanes[vehicle_id] = lane
            self.vehicle_lane_positions[vehicle_id] = float(
                self.connection.vehicle.getLanePosition(vehicle_id)
            )

    def _build_traffic_state(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "step": self.step,
            "traffic_lights": {
                traffic_light: self._build_traffic_light_metrics(traffic_light)
                for traffic_light in self.traffic_lights
            },
        }

    def _build_traffic_light_metrics(self, traffic_light: str) -> dict[str, Any]:
        assert self.connection is not None
        phase_lanes = self.phase_bidder_lanes[traffic_light]
        queue_lengths = self._get_phase_queue_lengths(phase_lanes)
        weighted_queue_lengths = self._get_phase_weighted_queue_lengths(phase_lanes)
        upp_bids = self._get_phase_upp_bids(phase_lanes)
        return {
            "number_phases": len(phase_lanes),
            "phase_signal": int(self.connection.trafficlight.getPhase(traffic_light)),
            "signal_state": self.connection.trafficlight.getRedYellowGreenState(traffic_light),
            "queue_lengths": queue_lengths,
            "weighted_queue_lengths": weighted_queue_lengths,
            "upp_bids": upp_bids,
        }

    def _get_phase_queue_lengths(self, phase_lanes: dict[str, list[str]]) -> list[float]:
        result = self._new_phase_result(phase_lanes)
        for vehicle_id in self.vehicle_ids:
            phase = self._get_vehicle_phase(vehicle_id, phase_lanes)
            if phase is not None and self._vehicle_is_inside_sensor(vehicle_id):
                result[phase] += 1.0
        return result

    def _get_phase_weighted_queue_lengths(self, phase_lanes: dict[str, list[str]]) -> list[float]:
        result = self._new_phase_result(phase_lanes)
        for vehicle_id in self.vehicle_ids:
            phase = self._get_vehicle_phase(vehicle_id, phase_lanes)
            if phase is None or not self._vehicle_is_inside_sensor(vehicle_id):
                continue
            result[phase] += self._distance_weight(self._vehicle_distance(vehicle_id))
        return result

    def _get_phase_upp_bids(self, phase_lanes: dict[str, list[str]]) -> list[float]:
        result = self._new_phase_result(phase_lanes)
        for vehicle_id in self.vehicle_ids:
            phase = self._get_vehicle_phase(vehicle_id, phase_lanes)
            if phase is not None and self._vehicle_is_inside_sensor(vehicle_id):
                result[phase] += float(self.vehicle_upp.get(vehicle_id, 0))
        return result

    def _new_phase_result(self, phase_lanes: dict[str, list[str]]) -> list[float]:
        number_phases = max(int(phase) for phase in phase_lanes) + 1
        return [0.0 for _ in range(number_phases)]

    def _get_vehicle_phase(
        self,
        vehicle_id: str,
        phase_lanes: dict[str, list[str]],
    ) -> int | None:
        lane = self.vehicle_lanes[vehicle_id]
        for phase, lanes in phase_lanes.items():
            if lane in lanes:
                return int(phase)
        return None

    def _vehicle_is_inside_sensor(self, vehicle_id: str) -> bool:
        return self._vehicle_distance(vehicle_id) <= self.sensor_distance

    def _vehicle_distance(self, vehicle_id: str) -> float:
        lane = self.vehicle_lanes[vehicle_id]
        lane_length = self.lane_lengths.get(lane, 0.0)
        return lane_length - self.vehicle_lane_positions[vehicle_id]

    def _distance_weight(self, distance_to_intersection: float) -> float:
        index = 0
        while index < len(self.position_distances):
            if distance_to_intersection < self.position_distances[index]:
                break
            index += 1
        index = min(index, len(self.position_weights) - 1)
        return self.position_weights[index]

    def _apply_pending_commands(self) -> None:
        assert self.connection is not None
        with self.command_lock:
            commands = dict(self.pending_commands)
            self.pending_commands.clear()
        for traffic_light, phase_signal in commands.items():
            self.connection.trafficlight.setPhase(traffic_light, phase_signal)

    def _send_message(self, target: str, topic: str, payload: dict[str, Any]) -> None:
        message = {
            "sender": self.NAME,
            "target": target,
            "topic": topic,
            "sent_at": time.time(),
            "payload": payload,
        }
        try:
            with socket.create_connection(self.connector, timeout=2.0) as connection:
                connection.sendall(json.dumps(message, sort_keys=True).encode("utf-8") + b"\n")
        except OSError as error:
            self.last_error = str(error)
