"""Fixed-cycle controller FSM for the simplified simple_b system."""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any


class FixedCycleController:
    """Cycle traffic lights through configured green and transition phases."""

    NAME = "controller"
    STATE_CREATED = "created"
    STATE_CONFIGURED = "configured"
    STATE_READY = "ready"
    STATE_RUNNING = "running"
    STATE_STOPPED = "stopped"
    STATE_FAILED = "failed"

    CYCLE_DELAY = "delay"
    CYCLE_GREEN = "green"
    CYCLE_TRANSITION = "transition"

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
    CYCLE_TRANSITIONS = {
        CYCLE_DELAY: {"delay_done": CYCLE_GREEN},
        CYCLE_GREEN: {"green_done": CYCLE_TRANSITION},
        CYCLE_TRANSITION: {"transition_done": CYCLE_GREEN},
    }

    def __init__(self, configuration: dict[str, Any]):
        """Create the controller in the CREATED state."""
        self.configuration = configuration
        self.state = self.STATE_CREATED
        self.host = "127.0.0.1"
        self.port = 0
        self.connector = ("127.0.0.1", 0)
        self.traffic_lights: list[str] = []
        self.control: dict[str, Any] = {}
        self.light_states: dict[str, dict[str, Any]] = {}
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.last_error: str | None = None

    def configure(self) -> "FixedCycleController":
        """Load endpoints and fixed-cycle parameters, then enter CONFIGURED."""
        self._transition("configure")
        self.host = str(self.configuration.get("host", "127.0.0.1"))
        self.port = int(self.configuration["port"])
        connector = self.configuration["connector"]
        self.connector = (str(connector["host"]), int(connector["port"]))
        self.traffic_lights = list(self.configuration.get("traffic_lights", []))
        self.control = dict(self.configuration.get("fixed_cycle", {}))
        self.light_states = {
            traffic_light: self._new_light_state(traffic_light)
            for traffic_light in self.traffic_lights
        }
        return self

    def start(self) -> None:
        """Open the controller TCP listener and enter RUNNING."""
        if self.state == self.STATE_CREATED:
            self.configure()
        if self.state == self.STATE_CONFIGURED:
            self._open_server()
            self._transition("prepare")
        self._transition("start")

    def stop(self) -> None:
        """Stop the listener and enter STOPPED."""
        if self.state == self.STATE_STOPPED:
            return
        self.stop_event.set()
        if self.server_socket is not None:
            self.server_socket.close()
        self._transition("stop")

    def fail(self, error: Exception | str) -> None:
        """Record an unrecoverable error and enter FAILED."""
        self.last_error = str(error)
        if self.state != self.STATE_FAILED:
            self._transition("fail")

    def _transition(self, event: str) -> None:
        next_state = self.TRANSITIONS.get(self.state, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"FixedCycleController cannot {event} from {self.state}")
        self.state = next_state

    def _cycle_transition(self, light_state: dict[str, Any], event: str) -> None:
        current = str(light_state["cycle_state"])
        next_state = self.CYCLE_TRANSITIONS.get(current, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"Fixed-cycle controller cannot {event} from {current}")
        light_state["cycle_state"] = next_state

    def _new_light_state(self, traffic_light: str) -> dict[str, Any]:
        time_delays = dict(self.control.get("time_delays", {}))
        delay = int(
            time_delays.get(traffic_light, self.control.get("default_time_delay", 0))
        )
        return {
            "cycle_state": self.CYCLE_DELAY if delay > 0 else self.CYCLE_GREEN,
            "phase": 0,
            "phase_signal": 0,
            "timer": delay if delay > 0 else self._phase_duration(0) - 1,
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
            thread = threading.Thread(
                target=self._handle_client, args=(client,), daemon=True
            )
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
        if message.get("topic") == "traffic_state":
            payload = dict(message.get("payload", {}))
            commands = self._build_commands(payload)
            self._send_message(
                "simulation",
                "traffic_light_command",
                {
                    "time": payload.get("time"),
                    "step": payload.get("step"),
                    "commands": commands,
                    "controller_states": self.light_states,
                },
            )
        elif message.get("topic") == "shutdown":
            self.stop()

    def _build_commands(self, traffic_state: dict[str, Any]) -> dict[str, int]:
        commands = {}
        light_metrics = dict(traffic_state.get("traffic_lights", {}))
        for traffic_light in light_metrics:
            if traffic_light not in self.light_states:
                self.light_states[traffic_light] = self._new_light_state(traffic_light)
            commands[traffic_light] = self._step_light(self.light_states[traffic_light])
        return commands

    def _step_light(self, light_state: dict[str, Any]) -> int:
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return int(light_state["phase_signal"])
        if light_state["cycle_state"] == self.CYCLE_DELAY:
            light_state["phase"] = 0
            light_state["phase_signal"] = 0
            light_state["timer"] = self._phase_duration(0) - 1
            self._cycle_transition(light_state, "delay_done")
        elif light_state["cycle_state"] == self.CYCLE_GREEN:
            light_state["phase_signal"] = int(light_state["phase"]) * 2 + 1
            light_state["timer"] = int(self.control["transition_duration"]) - 1
            self._cycle_transition(light_state, "green_done")
        elif light_state["cycle_state"] == self.CYCLE_TRANSITION:
            number_phases = len(self.control["phase_durations"])
            light_state["phase"] = (int(light_state["phase"]) + 1) % number_phases
            light_state["phase_signal"] = int(light_state["phase"]) * 2
            light_state["timer"] = self._phase_duration(int(light_state["phase"])) - 1
            self._cycle_transition(light_state, "transition_done")
        return int(light_state["phase_signal"])

    def _phase_duration(self, phase: int) -> int:
        durations = list(self.control["phase_durations"])
        return int(durations[phase % len(durations)])

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
                connection.sendall(
                    json.dumps(message, sort_keys=True).encode("utf-8") + b"\n"
                )
        except OSError as error:
            self.last_error = str(error)
