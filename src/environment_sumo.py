"""SUMO environment FSM — connects the FEDORA platform to the SUMO traffic simulator."""

from __future__ import annotations

import json
import os
import random
import shutil
import socket
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any, TextIO

import traci


class SumoEnvironment:
    """Run SUMO via TraCI and publish traffic state to the controller over TCP.

    Implements a finite-state machine lifecycle: CREATED → CONFIGURED → READY → RUNNING → STOPPED.
    """

    NAME = "environment"
    STATE_CREATED = "created"
    STATE_CONFIGURED = "configured"
    STATE_READY = "ready"
    STATE_RUNNING = "running"
    STATE_STOPPED = "stopped"
    STATE_FAILED = "failed"
    LANE_MEASUREMENT_QUEUE_LENGTHS = "queue_lengths"
    LANE_MEASUREMENT_WEIGHTED_QUEUE_LENGTHS = "weighted_queue_lengths"
    LANE_MEASUREMENT_UPP_BIDS = "upp_bids"
    SUPPORTED_LANE_MEASUREMENTS = {
        LANE_MEASUREMENT_QUEUE_LENGTHS,
        LANE_MEASUREMENT_WEIGHTED_QUEUE_LENGTHS,
        LANE_MEASUREMENT_UPP_BIDS,
    }
    SUPPORTED_STATE_KEYS: frozenset[str] = frozenset(
        {
            "step",
            "time",
            "vehicle_ids",
            "vehicle_lanes",
            "vehicle_lane_positions",
            "vehicle_upp",
            "pending_commands",
            "vehicle_speeds",
            "vehicle_waiting_times",
        }
    )

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
        STATE_READY: {
            "start": STATE_RUNNING,
            "stop": STATE_STOPPED,
            "fail": STATE_FAILED,
        },
        STATE_RUNNING: {"stop": STATE_STOPPED, "fail": STATE_FAILED},
        STATE_STOPPED: {"configure": STATE_CONFIGURED, "fail": STATE_FAILED},
        STATE_FAILED: {"stop": STATE_STOPPED},
    }

    def __init__(self, configuration: dict[str, Any], scenario_path: Path) -> None:
        """Initialize the environment in the CREATED state.

        Args:
            configuration: Flat environment configuration dict assembled by the Orchestrator.
            scenario_path: Directory containing the scenario's SUMO files.
        """
        self.configuration = configuration
        self.scenario_path = scenario_path
        self.state = self.STATE_CREATED

        # network endpoints (own listener and orchestrator target); populated in configure()
        self.host = "127.0.0.1"
        self.port = 0
        self.orchestrator = ("127.0.0.1", 0)

        # SUMO process settings (populated in configure())
        self.sumo_binary = "sumo-gui"
        self.sumo_config_file = self.scenario_path / "config.sumocfg"
        self.sumo_label = "simple_b"
        self.traffic_lights: list[str] = []
        self.traci_spawning_active = True

        # phase-to-lane mapping and which metrics to collect
        self.pressure_lanes: dict[str, dict[str, list[str]]] = {}
        self.enabled_lane_measurements: set[str] = set()

        # demand parameters (populated in configure())
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

        # TraCI connection and per-step simulation state
        self.connection: Any | None = None
        self.time = 0.0
        self.step = 0
        self.vehicle_counter = 0
        self.vehicle_upp: dict[str, int] = {}
        self.vehicle_ids: list[str] = []
        self.vehicle_lanes: dict[str, str] = {}
        self.vehicle_lane_positions: dict[str, float] = {}
        self.lane_lengths: dict[str, float] = {}
        self.pending_commands: dict[str, int] = {}

        # synchronization events for the orchestrator step/apply handshake
        self.step_event = threading.Event()
        self.apply_event = threading.Event()
        self.command_lock = threading.Lock()
        self.done_event = threading.Event()
        self.stop_event = threading.Event()

        # TCP server and run-loop threads
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.run_thread: threading.Thread | None = None
        self.last_error: str | None = None
        self._orchestrator_connection: socket.socket | None = None
        self._orchestrator_lock = threading.Lock()

        # vehicle event log
        self.vehicle_log_file: TextIO | None = None
        self.vehicle_log_path: Path = Path("logs/vehicle_log.jsonl")
        self.vehicle_log_lock = threading.Lock()
        self.vehicle_arrivals: dict[str, float] = {}
        self.vehicle_log_enabled: bool = True

        # state reporting config and caches for TraCI-fetched fields (populated in _run_step)
        self._state_cfg: dict[str, bool] = {}
        self._cached_vehicle_speeds: dict[str, float] = {}
        self._cached_vehicle_waiting_times: dict[str, float] = {}

    def configure(self) -> "SumoEnvironment":
        """Load all runtime settings from the configuration dict and enter CONFIGURED.

        Returns:
            self, for method chaining.
        """
        self._transition("configure")

        self.host = str(self.configuration.get("host", "127.0.0.1"))
        self.port = int(self.configuration["port"])
        orchestrator = self.configuration["orchestrator"]
        self.orchestrator = (str(orchestrator["host"]), int(orchestrator["port"]))

        sumo_cfg = dict(self.configuration.get("settings", {}))
        network = dict(self.configuration.get("network", {}))
        demand = dict(self.configuration.get("demand", {}))
        visualization = dict(self.configuration.get("visualization", {}))

        # Sensor range and weighted-position bracket parameters
        measurement_details = (
            self.configuration.get("setup", {})
            .get("measurements", {})
            .get("sumo", {})
            .get("measurement_details", {})
        )

        # SUMO process settings
        self.sumo_binary = self._resolve_sumo_binary(
            str(sumo_cfg.get("binary", "sumo-gui"))
        )
        self.sumo_config_file = self._resolve_path(str(sumo_cfg["config_file"]))
        self.sumo_label = str(sumo_cfg.get("label", "simple_b"))
        self.random.seed(int(sumo_cfg.get("random_seed", 42)))

        self.traffic_lights = list(network.get("traffic_lights", []))
        self.traci_spawning_active = bool(demand.get("traci_spawning_active", True))

        # Phase-to-lane mapping used to compute per-phase queue metrics
        self.pressure_lanes = self._load_pressure_lanes()

        # Which measurements to collect — injected by Orchestrator or read from config
        injected = self.configuration.get("lane_measurements_enabled")
        if injected is not None:
            self.enabled_lane_measurements = {str(m) for m in injected}
            unknown = self.enabled_lane_measurements - self.SUPPORTED_LANE_MEASUREMENTS
            if unknown:
                raise ValueError(
                    f"Unsupported lane measurements: {', '.join(sorted(unknown))}. "
                    f"Supported: {', '.join(sorted(self.SUPPORTED_LANE_MEASUREMENTS))}"
                )
        else:
            self.enabled_lane_measurements = self._load_enabled_lane_measurements()

        # Load route probabilities JSON from the scenario directory
        route_probs_path = self._resolve_path(str(demand["route_probabilities_file"]))
        with route_probs_path.open("r", encoding="utf-8") as f:
            self.route_probabilities = json.load(f)

        # Per-entrance spawn probability — explicit or derived from hourly flow rate
        if "spawn_probabilities" in demand:
            self.spawn_probabilities = {
                str(k): float(v) for k, v in demand["spawn_probabilities"].items()
            }
        else:
            prob = float(demand["flow_per_entrance_per_hour"]) / 3600.0
            self.spawn_probabilities = {
                entrance: prob for entrance in self.route_probabilities
            }

        self.vot_spawn_probabilities = dict(demand.get("vot_spawn_probabilities", {}))
        self.vot_upp_spawn_probabilities = dict(
            demand.get("vot_upp_spawn_probabilities", {})
        )

        # Vehicle RGBA colors keyed by category ("regular", "priority_pass", ...)
        colors = dict(visualization.get("vehicle_colors", {}))
        self.vehicle_colors = {
            name: tuple(int(c) for c in rgba) for name, rgba in colors.items()
        }

        self.sensor_distance = float(measurement_details.get("sensor_distance", 100.0))
        self.position_distances = [
            float(v)
            for v in measurement_details.get("position_distance_to_intersection", [])
        ]
        self.position_weights = [
            float(v) for v in measurement_details.get("position_weights", [1.0])
        ]
        self.spawn_horizon = int(demand.get("spawn_horizon", 0))
        self.max_steps = int(demand.get("max_steps", 0))
        self.step_delay_seconds = float(demand.get("step_delay_seconds", 0.0))
        self.controller_response_timeout_seconds = float(
            self.configuration.get("controller_response_timeout_seconds", 0.05)
        )

        # Prepare the vehicle event log in the recorder's log directory
        logs_dir = self.configuration.get("logs_dir", "logs")
        os.makedirs(logs_dir, exist_ok=True)
        self.vehicle_log_path = Path(logs_dir) / "vehicle_log.jsonl"

        self.vehicle_log_enabled = bool(
            self.configuration.get("vehicle_log_enabled", True)
        )
        self._state_cfg = dict(self.configuration.get("state_cfg", {}))
        unsupported = [
            k
            for k, v in self._state_cfg.items()
            if v and k not in self.SUPPORTED_STATE_KEYS
        ]
        if unsupported:
            warnings.warn(
                f"{self.__class__.__name__}: state_cfg has unsupported keys {unsupported}",
                UserWarning,
                stacklevel=2,
            )

        return self

    def start(self) -> None:
        """Open the TCP listener, start SUMO, and enter RUNNING."""
        if self.state == self.STATE_CREATED:
            self.configure()
        if self.state == self.STATE_CONFIGURED:
            self._open_server()

            if self.vehicle_log_enabled:
                # open vehicle log in write mode to start fresh for each run
                self.vehicle_log_file = self.vehicle_log_path.open(
                    "w", encoding="utf-8"
                )
                self._write_vehicle_log_meta()

            # launch SUMO process; sends environment_started to kick off the loop
            self._open_sumo()
            self._transition("prepare")

        self._transition("start")
        self.run_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.run_thread.start()

    def stop(self) -> None:
        """Stop SUMO and the TCP listener, then enter STOPPED."""
        if self.state == self.STATE_STOPPED:
            return

        # unblock any thread waiting on step_event or apply_event
        self.stop_event.set()
        self.step_event.set()
        self.apply_event.set()
        self.done_event.set()

        # close the persistent outgoing connection to the orchestrator
        with self._orchestrator_lock:
            if self._orchestrator_connection is not None:
                try:
                    self._orchestrator_connection.close()
                except OSError:
                    pass
                self._orchestrator_connection = None
        if self.server_socket is not None:
            self.server_socket.close()

        # close the TraCI connection to SUMO
        if self.connection is not None:
            try:
                self.connection.close()
            except (AttributeError, OSError):
                pass
            self.connection = None
        if self.vehicle_log_file is not None:
            self.vehicle_log_file.close()
        self._transition("stop")

    def wait_until_done(self) -> None:
        """Block the calling thread until the environment loop finishes."""
        self.done_event.wait()
        if self.run_thread is not None:
            self.run_thread.join(timeout=5.0)

    def fail(self, error: Exception | str) -> None:
        """Record an unrecoverable error and enter FAILED.

        Args:
            error: The exception or message describing the failure.
        """
        self.last_error = str(error)
        if self.state != self.STATE_FAILED:
            self._transition("fail")
        self.done_event.set()

    def _transition(self, event: str) -> None:
        """Apply a lifecycle event and advance the FSM state.

        Args:
            event: Transition event name (e.g. "configure", "start", "stop").
        """
        next_state = self.TRANSITIONS.get(self.state, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"SumoEnvironment cannot {event} from {self.state}")
        self.state = next_state

    def _resolve_path(self, path_value: str) -> Path:
        """Resolve a path string relative to the scenario directory if not absolute.

        Args:
            path_value: Absolute or relative file path string.
        Returns:
            Resolved Path object.
        """
        path = Path(path_value)
        if path.is_absolute():
            return path
        return self.scenario_path / path

    def _resolve_sumo_binary(self, binary_name: str) -> str:
        """Locate the SUMO executable on the current system.

        Args:
            binary_name: Configured binary name or path (e.g. "sumo-gui").
        Returns:
            Absolute path string to the located SUMO binary.
        Raises:
            FileNotFoundError: If no matching binary can be found.
        """
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
        searched = "\n".join(str(c) for c in candidates)
        raise FileNotFoundError(
            f"Could not find SUMO executable '{binary_name}'. "
            "Put SUMO on PATH, set SUMO_HOME, or set "
            "environment.settings.binary in config.json "
            f"to the executable path. Checked:\n{searched}"
        )

    def _sumo_binary_candidates(self, executable_name: str) -> list[Path]:
        """Build a list of candidate SUMO binary paths from known environment variables.

        Args:
            executable_name: Windows executable filename (e.g. "sumo-gui.exe").
        Returns:
            List of candidate Path objects to check.
        """
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
            candidates.append(
                Path(program_files) / "Eclipse" / "Sumo" / "bin" / executable_name
            )
        return candidates

    def _lane_measurements_config(self) -> dict[str, Any]:
        """Return the lane_measurements sub-section from the configuration.

        Raises:
            KeyError: If setup.measurements.sumo.lane_measurements is absent.
        """
        try:
            return self.configuration["setup"]["measurements"]["sumo"][
                "lane_measurements"
            ]
        except KeyError as error:
            raise KeyError(
                "Missing setup.measurements.sumo.lane_measurements in config.json"
            ) from error

    def _load_pressure_lanes(self) -> dict[str, Any]:
        """Load the phase-to-lanes mapping JSON file referenced in the configuration.

        Returns:
            Dict mapping traffic-light ID → phase index → list of lane IDs.
        Raises:
            KeyError: If the pressure_lanes config key or the JSON file is missing.
        """
        lane_cfg = self._lane_measurements_config()
        if "pressure_lanes" not in lane_cfg:
            raise KeyError(
                "Missing setup.measurements.sumo."
                "lane_measurements.pressure_lanes in config.json"
            )
        path = self._resolve_path(str(lane_cfg["pressure_lanes"]))
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_enabled_lane_measurements(self) -> set[str]:
        """Read the set of enabled lane measurement types from the configuration.

        Returns:
            Set of enabled measurement name strings.
        Raises:
            ValueError: If any listed measurement type is unsupported.
        """
        lane_cfg = self._lane_measurements_config()
        enabled = {str(m) for m in lane_cfg.get("enabled", [])}
        unknown = enabled - self.SUPPORTED_LANE_MEASUREMENTS
        if unknown:
            raise ValueError(
                f"Unsupported lane measurements in config.json: {', '.join(sorted(unknown))}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_LANE_MEASUREMENTS))}"
            )
        return enabled

    def _open_server(self) -> None:
        """Bind and start the TCP listener in a background daemon thread."""
        self.stop_event.clear()

        # SO_REUSEADDR lets the port be reused immediately after a previous run
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()

        # daemon thread exits automatically when the main process ends
        self.server_thread = threading.Thread(target=self._serve, daemon=True)
        self.server_thread.start()

    def _serve(self) -> None:
        """Accept incoming TCP connections and spawn a handler thread for each."""
        while not self.stop_event.is_set():
            try:
                assert self.server_socket is not None
                client, _address = self.server_socket.accept()
            except OSError:
                break
            thread = threading.Thread(
                target=self._handle_client, args=(client,), daemon=True
            )
            thread.start()

    def _handle_client(self, client: socket.socket) -> None:
        """Read JSON-line messages from a single persistent TCP connection.

        Args:
            client: Accepted client socket.
        """
        # 1-second timeout allows the loop to check stop_event without blocking forever
        client.settimeout(1.0)
        buffer = b""
        with client:
            while not self.stop_event.is_set():
                try:
                    chunk = client.recv(65536)
                except socket.timeout:
                    continue  # check stop_event and retry
                except OSError:
                    break
                if not chunk:
                    break  # client closed the connection
                buffer += chunk

                # dispatch all complete newline-terminated messages in the buffer
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_message(json.loads(line))

    def _handle_message(self, message: dict[str, Any]) -> None:
        """Dispatch an incoming message to the appropriate handler by topic.

        Args:
            message: Decoded JSON message dict.
        """
        topic = message.get("topic")
        if topic == "apply_and_advance":
            payload = dict(message.get("payload", {}))
            commands = {
                str(tl): int(phase)
                for tl, phase in dict(payload.get("commands", {})).items()
            }

            # queue commands then signal _run_step to apply them
            with self.command_lock:
                self.pending_commands.update(commands)
                self.apply_event.set()

        elif topic == "step":
            # release _run_loop to execute the next simulation step
            self.step_event.set()

        elif topic == "get_state":
            self._send_state_report()

        elif topic == "shutdown":
            # unblock all waits so the run thread can exit cleanly
            self.stop_event.set()
            self.step_event.set()
            self.apply_event.set()

    def _open_sumo(self) -> None:
        """Start the SUMO process via TraCI and cache initial lane geometry."""
        # Add SUMO Python tools to path so TraCI utilities are importable
        if "SUMO_HOME" in os.environ:
            tools_path = os.path.join(os.environ["SUMO_HOME"], "tools")
            if tools_path not in sys.path:
                sys.path.append(tools_path)

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

        # Cache lane lengths upfront to avoid per-step TraCI round-trips
        assert self.connection is not None
        self.lane_lengths = {
            lane: float(self.connection.lane.getLength(lane))
            for lane in self.connection.lane.getIDList()
        }

        self._send_message(
            "logic_module", "environment_started", {"label": self.sumo_label}
        )

    _STEP_TIMEOUT_SECONDS = 30.0

    def _run_loop(self) -> None:
        """Main simulation loop — runs on a background thread until done or stopped."""
        try:
            while not self.stop_event.is_set() and not self._simulation_ended():
                # wait for the orchestrator to send a step signal before advancing
                step_received = self.step_event.wait(timeout=self._STEP_TIMEOUT_SECONDS)
                if not step_received:
                    if not self.stop_event.is_set():
                        raise TimeoutError(
                            f"No step signal received within {self._STEP_TIMEOUT_SECONDS}s"
                            " — orchestrator may have lost the connection"
                        )
                    break
                self.step_event.clear()
                if self.stop_event.is_set():
                    break
                self._run_step()

                # optional slow-motion mode for visual debugging
                if self.step_delay_seconds > 0:
                    time.sleep(self.step_delay_seconds)

            # notify logic module that the environment run is over
            self._send_message(
                "logic_module",
                "environment_stopped",
                {"time": self.time, "step": self.step},
            )
        except Exception as error:
            self.fail(error)
        finally:
            self.done_event.set()

    def _simulation_ended(self) -> bool:
        """Return True when the configured stop condition has been reached.

        Returns:
            True if the simulation should stop, False to continue running.
        """
        if self.max_steps and self.step >= self.max_steps:
            return True
        if self.connection is None:
            return True
        if not self.traci_spawning_active:
            # Without TraCI spawning, stop when all vehicles have left
            return (
                self.max_steps == 0 and int(self.connection.vehicle.getIDCount()) == 0
            )

        if self.time <= self.spawn_horizon:
            return False

        # After the spawn horizon, wait until the last vehicle has exited
        return int(self.connection.vehicle.getIDCount()) == 0

    def _run_step(self) -> None:
        """Execute one simulation cycle: spawn, measure, send state, advance SUMO."""
        assert self.connection is not None
        if self.traci_spawning_active:
            self._spawn_vehicles()

        # detect arrivals/departures before reading positions
        self._track_vehicle_events()
        self._update_vehicle_positions()

        # cache TraCI-fetched state for get_state responses, only when configured
        if self._state_cfg.get("vehicle_speeds", False):
            self._cached_vehicle_speeds = {
                vid: float(self.connection.vehicle.getSpeed(vid))
                for vid in self.vehicle_ids
            }
        if self._state_cfg.get("vehicle_waiting_times", False):
            self._cached_vehicle_waiting_times = {
                vid: float(self.connection.vehicle.getAccumulatedWaitingTime(vid))
                for vid in self.vehicle_ids
            }

        # send current state to the controller and wait briefly for a response
        self._send_message("logic_module", "traffic_state", self._build_traffic_state())
        self.apply_event.wait(self.controller_response_timeout_seconds)
        self.apply_event.clear()
        self._apply_pending_commands()
        self.connection.simulationStep()
        self.step += 1

    def _spawn_vehicles(self) -> None:
        """Probabilistically insert new vehicles into SUMO for the current time step."""
        assert self.connection is not None
        if self.time >= self.spawn_horizon:
            return
        for entrance, probability in self.spawn_probabilities.items():
            if self.random.random() > probability:
                continue

            # sample a route and a value-of-time class for this vehicle
            route = self._weighted_choice(self.route_probabilities[entrance])
            vot = self._weighted_choice(self.vot_spawn_probabilities)

            # decide whether this vehicle carries a UPP priority bid based on its vot class
            upp_probability = float(self.vot_upp_spawn_probabilities.get(str(vot), 0.0))
            upp = int(self.random.random() < upp_probability)
            vehicle_id = f"v_{self.vehicle_counter}"
            self.vehicle_counter += 1
            self.vehicle_upp[vehicle_id] = upp
            self.connection.vehicle.add(vehicle_id, route)

            # visually distinguish priority vehicles in the SUMO GUI
            color_key = "priority_pass" if upp else "regular"
            if color_key in self.vehicle_colors:
                self.connection.vehicle.setColor(
                    vehicle_id, self.vehicle_colors[color_key]
                )

    def _weighted_choice(self, weights_by_item: dict[str, float]) -> str:
        """Sample one key from a dict proportionally to its weight values.

        Args:
            weights_by_item: Dict mapping item strings to their relative weights.
        Returns:
            One sampled item key.
        """
        total_weight = sum(float(w) for w in weights_by_item.values())
        threshold = self.random.random() * total_weight
        cumulative = 0.0
        for item, weight in weights_by_item.items():
            cumulative += float(weight)
            if cumulative >= threshold:
                return str(item)
        return str(next(reversed(weights_by_item)))

    def _track_vehicle_events(self) -> None:
        """Log vehicle arrival and departure events compared to the previous step."""
        assert self.connection is not None
        current_ids = set(self.connection.vehicle.getIDList())
        previous_ids = set(self.vehicle_ids)
        self.time = float(self.connection.simulation.getTime())

        # vehicles in current but not previous → newly entered the network
        for vehicle_id in current_ids - previous_ids:
            self.vehicle_arrivals[vehicle_id] = self.time
            self._log_vehicle_event(vehicle_id, "arrival", self.time)

        # vehicles in previous but not current → left the network this step
        for vehicle_id in previous_ids - current_ids:
            if vehicle_id in self.vehicle_arrivals:
                self._log_vehicle_event(vehicle_id, "departure", self.time)
                del self.vehicle_arrivals[vehicle_id]

    def _update_vehicle_positions(self) -> None:
        """Fetch the current vehicle list and their lane positions from TraCI."""
        assert self.connection is not None
        self.time = float(self.connection.simulation.getTime())
        self.vehicle_ids = list(self.connection.vehicle.getIDList())
        self.vehicle_lanes = {}
        self.vehicle_lane_positions = {}
        for vehicle_id in self.vehicle_ids:
            self.vehicle_lanes[vehicle_id] = str(
                self.connection.vehicle.getLaneID(vehicle_id)
            )
            self.vehicle_lane_positions[vehicle_id] = float(
                self.connection.vehicle.getLanePosition(vehicle_id)
            )

    def _build_traffic_state(self) -> dict[str, Any]:
        """Assemble the traffic_state payload for the current simulation step.

        Returns:
            Dict with simulation time, step counter, and per-traffic-light metrics.
        """
        return {
            "time": self.time,
            "step": self.step,
            "traffic_lights": {
                tl: self._build_traffic_light_metrics(tl) for tl in self.traffic_lights
            },
        }

    def _build_traffic_light_metrics(self, traffic_light: str) -> dict[str, Any]:
        """Collect all enabled measurements for a single traffic light.

        Args:
            traffic_light: SUMO traffic light ID.
        Returns:
            Dict of metric names to values for this traffic light.
        """
        assert self.connection is not None
        phase_lanes = self.pressure_lanes[traffic_light]
        metrics: dict[str, Any] = {
            "number_phases": len(phase_lanes),
            "phase_signal": int(self.connection.trafficlight.getPhase(traffic_light)),
            "signal_state": self.connection.trafficlight.getRedYellowGreenState(
                traffic_light
            ),
        }
        if self.LANE_MEASUREMENT_QUEUE_LENGTHS in self.enabled_lane_measurements:
            metrics["queue_lengths"] = self._get_phase_queue_lengths(phase_lanes)
        if (
            self.LANE_MEASUREMENT_WEIGHTED_QUEUE_LENGTHS
            in self.enabled_lane_measurements
        ):
            metrics["weighted_queue_lengths"] = self._get_phase_weighted_queue_lengths(
                phase_lanes
            )
        if self.LANE_MEASUREMENT_UPP_BIDS in self.enabled_lane_measurements:
            metrics["upp_bids"] = self._get_phase_upp_bids(phase_lanes)

        return metrics

    def _get_phase_queue_lengths(
        self, phase_lanes: dict[str, list[str]]
    ) -> list[float]:
        """Count vehicles per phase that are within the sensor range.

        Args:
            phase_lanes: Maps phase index to the list of incoming lane IDs for that phase.
        Returns:
            List of vehicle counts, one entry per phase.
        """
        result = self._new_phase_result(phase_lanes)
        for vehicle_id in self.vehicle_ids:
            phase = self._get_vehicle_phase(vehicle_id, phase_lanes)
            if phase is not None and self._vehicle_is_inside_sensor(vehicle_id):
                result[phase] += 1.0
        return result

    def _get_phase_weighted_queue_lengths(
        self, phase_lanes: dict[str, list[str]]
    ) -> list[float]:
        """Sum position-weighted vehicle counts per phase within the sensor range.

        Args:
            phase_lanes: Maps phase index to the list of incoming lane IDs for that phase.
        Returns:
            List of weighted queue sums, one entry per phase.
        """
        result = self._new_phase_result(phase_lanes)
        for vehicle_id in self.vehicle_ids:
            phase = self._get_vehicle_phase(vehicle_id, phase_lanes)
            if phase is None or not self._vehicle_is_inside_sensor(vehicle_id):
                continue

            # Map vehicle distance to a weight bracket (closer = higher bracket index)
            distance = self._vehicle_distance(vehicle_id)
            weight_index = sum(1 for d in self.position_distances if distance >= d)
            weight_index = min(weight_index, len(self.position_weights) - 1)
            result[phase] += self.position_weights[weight_index]
        return result

    def _get_phase_upp_bids(self, phase_lanes: dict[str, list[str]]) -> list[float]:
        """Sum UPP priority bids per phase within the sensor range.

        Args:
            phase_lanes: Maps phase index to the list of incoming lane IDs for that phase.
        Returns:
            List of aggregated UPP bid values, one entry per phase.
        """
        result = self._new_phase_result(phase_lanes)
        for vehicle_id in self.vehicle_ids:
            phase = self._get_vehicle_phase(vehicle_id, phase_lanes)
            if phase is not None and self._vehicle_is_inside_sensor(vehicle_id):
                result[phase] += float(self.vehicle_upp.get(vehicle_id, 0))
        return result

    def _new_phase_result(self, phase_lanes: dict[str, list[str]]) -> list[float]:
        """Return a zero-initialized list with one entry per phase.

        Args:
            phase_lanes: Phase-to-lanes mapping used to determine the phase count.
        Returns:
            List of zeros, length equal to the number of phases.
        """
        number_phases = max(int(p) for p in phase_lanes) + 1
        return [0.0] * number_phases

    def _get_vehicle_phase(
        self,
        vehicle_id: str,
        phase_lanes: dict[str, list[str]],
    ) -> int | None:
        """Return the phase index corresponding to the vehicle's current lane.

        Args:
            vehicle_id: SUMO vehicle ID.
            phase_lanes: Maps phase index to the list of incoming lane IDs for that phase.
        Returns:
            Phase index, or None if the lane is not covered by any phase.
        """
        lane = self.vehicle_lanes[vehicle_id]
        for phase, lanes in phase_lanes.items():
            if lane in lanes:
                return int(phase)
        return None

    def _vehicle_is_inside_sensor(self, vehicle_id: str) -> bool:
        """Return True if the vehicle is within the configured sensor detection range.

        Args:
            vehicle_id: SUMO vehicle ID.
        Returns:
            True if the vehicle is within sensor_distance metres of the stop line.
        """
        return self._vehicle_distance(vehicle_id) <= self.sensor_distance

    def _vehicle_distance(self, vehicle_id: str) -> float:
        """Return the vehicle's distance to the end of its current lane in metres.

        Args:
            vehicle_id: SUMO vehicle ID.
        Returns:
            Distance in metres from the vehicle to the lane's stop line.
        """
        lane = self.vehicle_lanes[vehicle_id]
        lane_length = self.lane_lengths.get(lane, 0.0)
        return lane_length - self.vehicle_lane_positions[vehicle_id]

    def _apply_pending_commands(self) -> None:
        """Apply all queued traffic-light phase commands to SUMO."""
        assert self.connection is not None
        with self.command_lock:
            commands = dict(self.pending_commands)
            self.pending_commands.clear()
        for traffic_light, phase_signal in commands.items():
            self.connection.trafficlight.setPhase(traffic_light, phase_signal)

    def _write_vehicle_log_meta(self) -> None:
        """Write a run_meta header as the first record of vehicle_log.jsonl."""
        meta = {
            "type": "run_meta",
            "scenario": self.configuration.get("settings", {}).get("label", "unknown"),
            "traffic_lights": list(self.traffic_lights),
            "max_steps": self.max_steps,
            "spawn_horizon": self.spawn_horizon,
            "random_seed": int(
                self.configuration.get("settings", {}).get("random_seed", 42)
            ),
        }
        with self.vehicle_log_lock:
            if self.vehicle_log_file is not None:
                self.vehicle_log_file.write(json.dumps(meta) + "\n")
                self.vehicle_log_file.flush()

    def _send_state_report(self) -> None:
        """Respond to a get_state request with a snapshot of configured environment state."""
        cfg = self._state_cfg
        state: dict[str, Any] = {}
        if cfg.get("step", False):
            state["step"] = self.step
        if cfg.get("time", False):
            state["time"] = self.time
        if cfg.get("vehicle_ids", False):
            state["vehicle_ids"] = list(self.vehicle_ids)
        if cfg.get("vehicle_lanes", False):
            state["vehicle_lanes"] = dict(self.vehicle_lanes)
        if cfg.get("vehicle_lane_positions", False):
            state["vehicle_lane_positions"] = dict(self.vehicle_lane_positions)
        if cfg.get("vehicle_upp", False):
            state["vehicle_upp"] = dict(self.vehicle_upp)
        if cfg.get("pending_commands", False):
            state["pending_commands"] = dict(self.pending_commands)
        if cfg.get("vehicle_speeds", False) and self._cached_vehicle_speeds:
            state["vehicle_speeds"] = dict(self._cached_vehicle_speeds)
        if (
            cfg.get("vehicle_waiting_times", False)
            and self._cached_vehicle_waiting_times
        ):
            state["vehicle_waiting_times"] = dict(self._cached_vehicle_waiting_times)
        self._send_message("orchestrator", "state_report", state)

    def _log_vehicle_event(
        self, vehicle_id: str, event_type: str, event_time: float
    ) -> None:
        """Append a vehicle arrival or departure record to the JSONL log file.

        Args:
            vehicle_id: SUMO vehicle ID.
            event_type: "arrival" or "departure".
            event_time: Simulation time of the event in seconds.
        """
        record = {
            "vehicle_id": vehicle_id,
            "event_type": event_type,
            "time": event_time,
            "priority": self.vehicle_upp.get(vehicle_id, 0),
        }
        with self.vehicle_log_lock:
            if self.vehicle_log_file is not None:
                self.vehicle_log_file.write(json.dumps(record) + "\n")
                self.vehicle_log_file.flush()

    def _send_message(self, target: str, topic: str, payload: dict[str, Any]) -> None:
        """Serialize and send a JSON-line message to the orchestrator.

        Args:
            target: Destination component name (e.g. "logic_module").
            topic: Message topic string.
            payload: Message payload dict.
        """
        message = {
            "sender": self.NAME,
            "target": target,
            "topic": topic,
            "sent_at": time.time(),
            "payload": payload,
        }
        encoded = json.dumps(message, sort_keys=True).encode("utf-8") + b"\n"

        with self._orchestrator_lock:
            try:
                # lazily create and cache the outgoing connection on first use
                if self._orchestrator_connection is None:
                    conn = socket.create_connection(self.orchestrator, timeout=5.0)
                    conn.settimeout(None)
                    self._orchestrator_connection = conn
                self._orchestrator_connection.sendall(encoded)

            except OSError as error:
                self.last_error = str(error)
                # invalidate the cached connection so the next call reconnects
                try:
                    if self._orchestrator_connection is not None:
                        self._orchestrator_connection.close()
                except OSError:
                    pass
                self._orchestrator_connection = None
