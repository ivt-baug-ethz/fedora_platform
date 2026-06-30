"""Max-pressure traffic light controller FSM."""

from __future__ import annotations

import json
import random
import socket
import threading
import time
import warnings
from typing import Any


class MaxPressureController:
    """Assign green phases by auction, granting right-of-way to the highest-queue-length direction.

    Uses a per-intersection auction to select the winning phase each cycle, subject to
    minimum and maximum green time constraints.
    """

    NAME = "logic_module"
    STATE_CREATED = "created"
    STATE_CONFIGURED = "configured"
    STATE_READY = "ready"
    STATE_RUNNING = "running"
    STATE_STOPPED = "stopped"
    STATE_FAILED = "failed"

    AUCTION_READY = "ready_for_auction"
    AUCTION_CHANGING_SIGNAL = "changing_signal"
    AUCTION_WAIT_MIN_GREEN = "wait_min_green_time"
    AUCTION_WAIT_NEXT = "wait_for_next_auction"
    SUPPORTED_STATE_KEYS: frozenset[str] = frozenset({
        "step", "controller_type", "light_states", "bids", "phase_switched",
    })

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
    AUCTION_TRANSITIONS = {
        AUCTION_READY: {
            "same_phase": AUCTION_WAIT_NEXT,
            "new_phase": AUCTION_CHANGING_SIGNAL,
        },
        AUCTION_CHANGING_SIGNAL: {"transition_done": AUCTION_WAIT_MIN_GREEN},
        AUCTION_WAIT_MIN_GREEN: {"min_green_done": AUCTION_READY},
        AUCTION_WAIT_NEXT: {"auction_timer_done": AUCTION_READY},
    }

    def __init__(self, configuration: dict[str, Any]):
        """Initialize the controller in the CREATED state.

        Args:
            configuration: Controller configuration dict assembled by the Orchestrator.
        """
        self.configuration = configuration
        self.state = self.STATE_CREATED

        # network endpoints; populated in configure()
        self.host = "127.0.0.1"
        self.port = 0
        self.orchestrator = ("127.0.0.1", 0)

        # auction parameters; populated in configure()
        self.traffic_lights: list[str] = []
        self.control: dict[str, Any] = {}

        # per-light auction state machines, keyed by traffic light ID
        self.light_states: dict[str, dict[str, Any]] = {}
        self.random = random.Random()

        # state reporting config and per-step cache for state_report responses
        self._state_cfg: dict[str, bool] = {}
        self._last_step: int = 0
        self._last_bids: dict[str, list[float]] = {}
        self._last_phase_switched: dict[str, bool] = {}

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
            List containing the queue measurement type needed for the configured bidding strategy.
        """
        strategy = self.configuration.get("max_pressure", {}).get(
            "bidding_strategy", "phase_queue_length"
        )

        if "weighted" in strategy:
            return ["weighted_queue_lengths"]

        return ["queue_lengths"]

    def configure(self) -> "MaxPressureController":
        """Load endpoints and max-pressure parameters, then enter CONFIGURED.

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
        self.control = dict(self.configuration.get("max_pressure", {}))
        self._state_cfg = dict(self.configuration.get("state_cfg", {}))
        unsupported = [
            k for k, v in self._state_cfg.items() if v and k not in self.SUPPORTED_STATE_KEYS
        ]
        if unsupported:
            warnings.warn(
                f"{self.__class__.__name__}: state_cfg has unsupported keys {unsupported}",
                UserWarning,
                stacklevel=2,
            )

        # seed random for deterministic tie-breaking across runs
        self.random.seed(int(self.configuration.get("random_seed", 42)))
        self.light_states = {tl: self._new_light_state() for tl in self.traffic_lights}
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
            raise RuntimeError(
                f"MaxPressureController cannot {event} from {self.state}"
            )

        self.state = next_state

    def _auction_transition(self, light_state: dict[str, Any], event: str) -> None:
        """Advance the per-light auction state machine.

        Args:
            light_state: Mutable state dict for one traffic light.
            event: Auction event name (e.g. "same_phase", "new_phase").
        """
        current = str(light_state["auction_state"])
        next_state = self.AUCTION_TRANSITIONS.get(current, {}).get(event)

        if next_state is None:
            raise RuntimeError(f"Max-pressure auction cannot {event} from {current}")

        light_state["auction_state"] = next_state

    def _new_light_state(self) -> dict[str, Any]:
        """Return the initial auction state for one traffic light.

        Returns:
            State dict with auction_state, phase, phase_signal, and timer fields.
        """
        return {
            "auction_state": self.AUCTION_READY,
            "phase": 0,
            "phase_signal": 0,
            "timer": 0,
            "current_phase_timer": 0,
            "number_phases": 4,
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
            self._last_step = int(payload.get("step", self._last_step))
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

        elif message.get("topic") == "get_state":
            cfg = self._state_cfg
            state: dict[str, Any] = {}
            if cfg.get("step", False):
                state["step"] = self._last_step
            if cfg.get("controller_type", False):
                state["controller_type"] = "controller_max_pressure"
            if cfg.get("light_states", False):
                state["light_states"] = dict(self.light_states)
            if cfg.get("bids", False):
                state["bids"] = dict(self._last_bids)
            if cfg.get("phase_switched", False):
                state["phase_switched"] = dict(self._last_phase_switched)
            self._send_message("orchestrator", "state_report", state)

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
        for traffic_light, metrics in light_metrics.items():
            # auto-register lights that appear in simulation data but not in the config
            if traffic_light not in self.light_states:
                self.light_states[traffic_light] = self._new_light_state()
            commands[traffic_light] = self._step_light(
                self.light_states[traffic_light],
                dict(metrics),
                traffic_light,
            )

        return commands

    def _step_light(
        self,
        light_state: dict[str, Any],
        metrics: dict[str, Any],
        traffic_light: str = "",
    ) -> int:
        """Advance one time step for a single traffic light and return its phase signal.

        Args:
            light_state: Mutable state dict for one traffic light.
            metrics: Current measurement data for this traffic light.
            traffic_light: Traffic light ID for bid caching.
        Returns:
            Phase signal index to send to SUMO.
        """
        # update phase count in case it changed since the last step
        number_phases = max(
            1, int(metrics.get("number_phases", light_state["number_phases"]))
        )
        light_state["number_phases"] = number_phases

        # dispatch to the appropriate sub-handler based on auction state
        auction_state = light_state["auction_state"]
        if auction_state == self.AUCTION_READY:
            self._step_ready_for_auction(light_state, metrics, traffic_light)
        elif auction_state == self.AUCTION_CHANGING_SIGNAL:
            self._step_changing_signal(light_state)
        elif auction_state == self.AUCTION_WAIT_MIN_GREEN:
            self._step_wait_min_green(light_state)
        elif auction_state == self.AUCTION_WAIT_NEXT:
            self._step_wait_next_auction(light_state)
        return int(light_state["phase_signal"])

    def _step_ready_for_auction(
        self,
        light_state: dict[str, Any],
        metrics: dict[str, Any],
        traffic_light: str = "",
    ) -> None:
        """Run the auction to decide whether to keep or switch the current phase.

        Args:
            light_state: Mutable state dict for one traffic light.
            metrics: Current measurement data for this traffic light.
            traffic_light: Traffic light ID, used to update the last-bid cache.
        """
        light_state["current_phase_timer"] += 1
        bids = self._get_phase_bids(metrics)
        current_phase = int(light_state["phase"])

        # Force a phase switch if the current phase has held green too long
        if light_state["current_phase_timer"] > int(self.control["max_green_duration"]):
            bids[current_phase] = -10000.0

        winner_phase = self._determine_auction_winner(bids)
        phase_switched = winner_phase != current_phase
        if traffic_light:
            if self._state_cfg.get("bids", False):
                self._last_bids[traffic_light] = list(bids)
            if self._state_cfg.get("phase_switched", False):
                self._last_phase_switched[traffic_light] = phase_switched

        if not phase_switched:
            self._auction_transition(light_state, "same_phase")
            light_state["timer"] = int(self.control["auction_suspend_duration"]) - 1
        else:
            light_state["phase"] = winner_phase
            light_state["phase_signal"] += 1
            self._auction_transition(light_state, "new_phase")
            light_state["timer"] = int(self.control["transition_duration"]) - 1

    def _step_changing_signal(self, light_state: dict[str, Any]) -> None:
        """Count down the yellow transition timer before entering the new green phase.

        Args:
            light_state: Mutable state dict for one traffic light.
        """
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return

        # Transition complete — set the even phase signal for the new green phase
        light_state["phase_signal"] = int(light_state["phase"]) * 2
        light_state["timer"] = int(self.control["min_green_duration"]) - 1
        light_state["current_phase_timer"] = 0
        self._auction_transition(light_state, "transition_done")

    def _step_wait_min_green(self, light_state: dict[str, Any]) -> None:
        """Count down the minimum green timer before allowing the next auction.

        Args:
            light_state: Mutable state dict for one traffic light.
        """
        light_state["current_phase_timer"] += 1
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return
        self._auction_transition(light_state, "min_green_done")

    def _step_wait_next_auction(self, light_state: dict[str, Any]) -> None:
        """Count down the inter-auction suspension timer.

        Args:
            light_state: Mutable state dict for one traffic light.
        """
        light_state["current_phase_timer"] += 1
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return
        self._auction_transition(light_state, "auction_timer_done")

    def _get_phase_bids(self, metrics: dict[str, Any]) -> list[float]:
        """Extract per-phase bid values from the traffic state metrics.

        Args:
            metrics: Measurement data for one traffic light.
        Returns:
            List of bid values, one per phase.
        """
        strategy = str(self.control.get("bidding_strategy", "phase_queue_length"))

        # all strategies with "weighted" in their name use position-weighted queue lengths
        weighted_strategies = {
            "phase_weighted_vehicle_position",
            "phase_weighted_queue_length",
            "weighted_queue_length",
        }

        if strategy in weighted_strategies:
            bids = list(metrics.get("weighted_queue_lengths", []))
        else:
            bids = list(metrics.get("queue_lengths", []))

        # fall back to a single zero bid if no measurements are available
        return [float(b) for b in bids] or [0.0]

    def _determine_auction_winner(self, bids: list[float]) -> int:
        """Return the index of the phase with the highest bid, breaking ties randomly.

        Args:
            bids: List of bid values, one per phase.
        Returns:
            Index of the winning phase.
        """
        max_bid = max(bids)
        winners = [i for i, b in enumerate(bids) if b == max_bid]
        return int(self.random.choice(winners))

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
