"""Configurable fixed-cycle traffic light controller FSM."""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any


class FixedCycleController:
    """Configurable fixed-cycle controller: cycles traffic lights through user-defined phase durations.

    Each intersection runs an independent schedule with configurable green-phase durations,
    transition (amber) duration, and an optional per-intersection startup time offset. Unlike
    the baseline (no controller), phase durations and offsets are explicit in the configuration
    rather than relying on SUMO's built-in signal plans.
    """

    NAME = "logic_module"
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
        """Initialize the controller in the CREATED state.

        Args:
            configuration: Controller configuration dict assembled by the Orchestrator.
        """
        self.configuration = configuration
        self.state = self.STATE_CREATED

        # network endpoints (own listener and orchestrator target); populated in configure()
        self.host = "127.0.0.1"
        self.port = 0
        self.orchestrator = ("127.0.0.1", 0)

        # cycle parameters (populated in configure())
        self.traffic_lights: list[str] = []
        self.control: dict[str, Any] = {}

        # per-light cycle state machines, keyed by traffic light ID
        self.light_states: dict[str, dict[str, Any]] = {}

        # TCP server state
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.last_error: str | None = None
        self._orchestrator_connection: socket.socket | None = None
        self._orchestrator_lock = threading.Lock()

    def get_required_measurements(self) -> list[str]:
        """Return the list of simulation measurements this controller requires.

        Returns:
            Empty list — fixed-cycle control does not use queue measurements.
        """
        return []

    def configure(self) -> "FixedCycleController":
        """Load endpoints and fixed-cycle parameters, then enter CONFIGURED.

        Returns:
            self, for method chaining.
        """
        self._transition("configure")

        # read TCP endpoint and orchestrator contact from config
        self.host = str(self.configuration.get("host", "127.0.0.1"))
        self.port = int(self.configuration["port"])
        orchestrator = self.configuration["orchestrator"]
        self.orchestrator = (str(orchestrator["host"]), int(orchestrator["port"]))
        self.traffic_lights = list(self.configuration.get("traffic_lights", []))
        self.control = dict(self.configuration.get("fixed_cycle", {}))

        # initialise a cycle state machine for each known traffic light
        self.light_states = {
            tl: self._new_light_state(tl) for tl in self.traffic_lights
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

        # signal handler threads to exit
        self.stop_event.set()

        # close the persistent connection to the orchestrator
        with self._orchestrator_lock:
            if self._orchestrator_connection is not None:
                try:
                    self._orchestrator_connection.close()
                except OSError:
                    pass
                self._orchestrator_connection = None

        if self.server_socket is not None:
            self.server_socket.close()

        self._transition("stop")

    def fail(self, error: Exception | str) -> None:
        """Record an unrecoverable error and enter FAILED.

        Args:
            error: The exception or message describing the failure.
        """
        self.last_error = str(error)
        if self.state != self.STATE_FAILED:
            self._transition("fail")

    def _transition(self, event: str) -> None:
        """Apply a lifecycle event and advance the FSM state.

        Args:
            event: Transition event name (e.g. "configure", "start", "stop").
        """
        next_state = self.TRANSITIONS.get(self.state, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"FixedCycleController cannot {event} from {self.state}")

        self.state = next_state

    def _cycle_transition(self, light_state: dict[str, Any], event: str) -> None:
        """Advance the per-light cycle state machine.

        Args:
            light_state: Mutable state dict for one traffic light.
            event: Cycle event name (e.g. "delay_done", "green_done").
        """
        current = str(light_state["cycle_state"])
        next_state = self.CYCLE_TRANSITIONS.get(current, {}).get(event)

        if next_state is None:
            raise RuntimeError(f"Fixed-cycle controller cannot {event} from {current}")

        light_state["cycle_state"] = next_state

    def _new_light_state(self, traffic_light: str) -> dict[str, Any]:
        """Build the initial cycle state for one traffic light.

        Args:
            traffic_light: SUMO traffic light ID (used to look up its startup time offset).
        Returns:
            Initial state dict with cycle_state, phase, phase_signal, and timer fields.
        """
        time_delays = dict(self.control.get("time_delays", {}))
        delay = int(
            time_delays.get(traffic_light, self.control.get("default_time_delay", 0))
        )

        return {
            "cycle_state": self.CYCLE_DELAY if delay > 0 else self.CYCLE_GREEN,
            "phase": 0,
            "phase_signal": 0,
            # Start the timer at the configured delay, or at the first green duration
            "timer": delay if delay > 0 else self._phase_duration(0) - 1,
        }

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
        """Dispatch an incoming message by topic.

        Args:
            message: Decoded JSON message dict.
        """
        if message.get("topic") == "traffic_state":
            payload = dict(message.get("payload", {}))
            commands = self._build_commands(payload)
            self._send_message(
                "simulation",
                "logic_command",
                {
                    "type": "traffic_light_command",
                    "time": payload.get("time"),
                    "step": payload.get("step"),
                    "commands": commands,
                    "controller_states": self.light_states,
                },
            )
        elif message.get("topic") == "shutdown":
            self.stop()

    def _build_commands(self, traffic_state: dict[str, Any]) -> dict[str, int]:
        """Compute the target phase signal for every traffic light in this step.

        Args:
            traffic_state: traffic_state payload from the simulation.
        Returns:
            Dict mapping traffic-light ID to its next phase signal index.
        """
        commands = {}
        light_metrics = dict(traffic_state.get("traffic_lights", {}))

        for traffic_light in light_metrics:
            # auto-register lights that appear in simulation data but not in the config
            if traffic_light not in self.light_states:
                self.light_states[traffic_light] = self._new_light_state(traffic_light)
            commands[traffic_light] = self._step_light(self.light_states[traffic_light])

        return commands

    def _step_light(self, light_state: dict[str, Any]) -> int:
        """Advance one time step for a single traffic light and return its phase signal.

        Args:
            light_state: Mutable state dict for one traffic light.
        Returns:
            Phase signal index to send to SUMO.
        """
        # Count down the current timer; signal stays unchanged while waiting
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return int(light_state["phase_signal"])

        if light_state["cycle_state"] == self.CYCLE_DELAY:
            # Startup offset expired — begin phase 0 green
            light_state["phase"] = 0
            light_state["phase_signal"] = 0
            light_state["timer"] = self._phase_duration(0) - 1
            self._cycle_transition(light_state, "delay_done")

        elif light_state["cycle_state"] == self.CYCLE_GREEN:
            # Green expired — enter yellow transition (odd phase signals are transitions)
            light_state["phase_signal"] = int(light_state["phase"]) * 2 + 1
            light_state["timer"] = int(self.control["transition_duration"]) - 1
            self._cycle_transition(light_state, "green_done")

        elif light_state["cycle_state"] == self.CYCLE_TRANSITION:
            # Transition done — advance to the next phase and start its green
            number_phases = len(self.control["phase_durations"])
            light_state["phase"] = (int(light_state["phase"]) + 1) % number_phases
            light_state["phase_signal"] = int(light_state["phase"]) * 2
            light_state["timer"] = self._phase_duration(int(light_state["phase"])) - 1
            self._cycle_transition(light_state, "transition_done")

        return int(light_state["phase_signal"])

    def _phase_duration(self, phase: int) -> int:
        """Return the configured green duration for the given phase index.

        Args:
            phase: Phase index (wraps around if out of bounds).
        Returns:
            Duration in simulation steps.
        """
        durations = list(self.control["phase_durations"])
        return int(durations[phase % len(durations)])

    def _send_message(self, target: str, topic: str, payload: dict[str, Any]) -> None:
        """Serialize and send a JSON-line message to the orchestrator.

        Args:
            target: Destination component name (e.g. "simulation").
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
