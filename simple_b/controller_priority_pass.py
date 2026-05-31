"""Priority Pass controller FSM for the simplified simple_b system."""

from __future__ import annotations

import json
import random
import socket
import threading
import time
from typing import Any


class PriorityPassController:
    """Receive traffic-state messages and send traffic-light phase commands."""

    NAME = "controller"
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
        """Create the controller in the CREATED state."""
        self.configuration = configuration
        self.state = self.STATE_CREATED
        self.host = "127.0.0.1"
        self.port = 0
        self.connector = ("127.0.0.1", 0)
        self.traffic_lights: list[str] = []
        self.control: dict[str, Any] = {}
        self.light_states: dict[str, dict[str, Any]] = {}
        self.random = random.Random()
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.last_error: str | None = None

    def configure(self) -> "PriorityPassController":
        """Load endpoints and Priority Pass parameters, then enter CONFIGURED."""
        self._transition("configure")
        self.host = str(self.configuration.get("host", "127.0.0.1"))
        self.port = int(self.configuration["port"])
        connector = self.configuration["connector"]
        self.connector = (str(connector["host"]), int(connector["port"]))
        self.traffic_lights = list(self.configuration.get("traffic_lights", []))
        self.control = dict(self.configuration.get("control", {}))
        self.random.seed(int(self.configuration.get("random_seed", 42)))
        self.light_states = {
            traffic_light: self._new_light_state()
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
            raise RuntimeError(f"PriorityPassController cannot {event} from {self.state}")
        self.state = next_state

    def _auction_transition(self, light_state: dict[str, Any], event: str) -> None:
        current = str(light_state["auction_state"])
        next_state = self.AUCTION_TRANSITIONS.get(current, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"Priority Pass auction cannot {event} from {current}")
        light_state["auction_state"] = next_state

    def _new_light_state(self) -> dict[str, Any]:
        return {
            "auction_state": self.AUCTION_READY,
            "phase": 0,
            "phase_signal": 0,
            "timer": 0,
            "current_phase_timer": 0,
            "number_phases": 4,
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
        for traffic_light, metrics in light_metrics.items():
            if traffic_light not in self.light_states:
                self.light_states[traffic_light] = self._new_light_state()
            commands[traffic_light] = self._step_light(
                self.light_states[traffic_light],
                dict(metrics),
            )
        return commands

    def _step_light(self, light_state: dict[str, Any], metrics: dict[str, Any]) -> int:
        number_phases = max(1, int(metrics.get("number_phases", light_state["number_phases"])))
        light_state["number_phases"] = number_phases
        auction_state = light_state["auction_state"]
        if auction_state == self.AUCTION_READY:
            self._step_ready_for_auction(light_state, metrics)
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
    ) -> None:
        light_state["current_phase_timer"] += 1
        bids = self._get_priority_pass_bids(metrics)
        current_phase = int(light_state["phase"])
        if light_state["current_phase_timer"] > int(self.control["max_green_duration"]):
            bids[current_phase] = -10000.0
        winner_phase = self._determine_auction_winner_phase(bids)
        if winner_phase == current_phase:
            self._auction_transition(light_state, "same_phase")
            light_state["timer"] = int(self.control["auction_suspend_duration"]) - 1
        else:
            light_state["phase"] = winner_phase
            light_state["phase_signal"] += 1
            self._auction_transition(light_state, "new_phase")
            light_state["timer"] = int(self.control["transition_duration"]) - 1

    def _step_changing_signal(self, light_state: dict[str, Any]) -> None:
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return
        light_state["phase_signal"] = int(light_state["phase"]) * 2
        light_state["timer"] = int(self.control["min_green_duration"]) - 1
        light_state["current_phase_timer"] = 0
        self._auction_transition(light_state, "transition_done")

    def _step_wait_min_green(self, light_state: dict[str, Any]) -> None:
        light_state["current_phase_timer"] += 1
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return
        self._auction_transition(light_state, "min_green_done")

    def _step_wait_next_auction(self, light_state: dict[str, Any]) -> None:
        light_state["current_phase_timer"] += 1
        if light_state["timer"] > 0:
            light_state["timer"] -= 1
            return
        self._auction_transition(light_state, "auction_timer_done")

    def _get_priority_pass_bids(self, metrics: dict[str, Any]) -> list[float]:
        strategy = str(self.control.get("bidding_strategy", "phase_queue_length"))
        weighted_strategies = {
            "phase_weigthed_vehicle_position",
            "phase_weighted_vehicle_position",
            "phase_weighted_queue_length",
            "weighted_queue_length",
        }
        if strategy in weighted_strategies:
            phase_bids = list(metrics.get("weighted_queue_lengths", []))
        else:
            phase_bids = list(metrics.get("queue_lengths", []))
        upp_bids = list(metrics.get("upp_bids", [0.0 for _ in phase_bids]))
        tau = float(self.control.get("trade_off", 0.0))
        bids = []
        for index, phase_bid in enumerate(phase_bids):
            upp_bid = float(upp_bids[index]) if index < len(upp_bids) else 0.0
            bids.append((1.0 - tau) * float(phase_bid) + tau * upp_bid)
        return bids or [0.0]

    def _determine_auction_winner_phase(self, bids: list[float]) -> int:
        max_bid = max(bids)
        winners = [index for index, bid in enumerate(bids) if bid == max_bid]
        return int(self.random.choice(winners))

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
