"""TCP connector FSM for the simplified simple_b system."""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any


class Connector:
    """Route JSON-line TCP messages between simple_b components."""

    NAME = "connector"
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
        """Create the connector in the CREATED state."""
        self.configuration = configuration
        self.state = self.STATE_CREATED
        self.host = "127.0.0.1"
        self.port = 0
        self.socket_timeout = 2.0
        self.components: dict[str, tuple[str, int]] = {}
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.last_error: str | None = None

    def configure(self) -> "Connector":
        """Load TCP endpoints and move from CREATED or STOPPED to CONFIGURED."""
        self._transition("configure")
        self.host = str(self.configuration.get("host", "127.0.0.1"))
        self.port = int(self.configuration["port"])
        self.socket_timeout = float(self.configuration.get("socket_timeout", 2.0))
        endpoints = self.configuration.get("components", {})
        self.components = {
            name: (str(endpoint["host"]), int(endpoint["port"]))
            for name, endpoint in endpoints.items()
        }
        return self

    def start(self) -> None:
        """Open the connector TCP listener and enter RUNNING."""
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
            raise RuntimeError(f"Connector cannot {event} from {self.state}")
        self.state = next_state

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
                self._route(json.loads(line))

    def _route(self, message: dict[str, Any]) -> None:
        message.setdefault("received_at", time.time())
        sender = str(message.get("sender", "unknown"))
        target = str(message.get("target", "broadcast"))
        if target != "recorder":
            self._log_message(message)
        if target == "broadcast":
            for component in self.components:
                if component != sender:
                    self._forward(component, message)
            return
        if target in self.components:
            self._forward(target, message)

    def _log_message(self, message: dict[str, Any]) -> None:
        if "recorder" not in self.components:
            return
        log_message = {
            "sender": self.NAME,
            "target": "recorder",
            "topic": "communication",
            "sent_at": time.time(),
            "payload": message,
        }
        self._forward("recorder", log_message)

    def _forward(self, target: str, message: dict[str, Any]) -> None:
        endpoint = self.components.get(target)
        if endpoint is None:
            return
        try:
            with socket.create_connection(endpoint, timeout=self.socket_timeout) as connection:
                encoded = json.dumps(message, sort_keys=True).encode("utf-8")
                connection.sendall(encoded + b"\n")
        except OSError as error:
            self.last_error = f"Could not forward to {target}: {error}"
