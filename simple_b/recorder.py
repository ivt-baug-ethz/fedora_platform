"""Recorder FSM that stores routed simple_b communication in a text log."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Any, TextIO


class Recorder:
    """Listen on TCP and append every received message to a JSON-lines txt file."""

    NAME = "recorder"
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
        """Create the recorder in the CREATED state."""
        self.configuration = configuration
        self.state = self.STATE_CREATED
        self.host = "127.0.0.1"
        self.port = 0
        self.log_path = Path("communication_log.txt")
        self.log_file: TextIO | None = None
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.write_lock = threading.Lock()
        self.last_error: str | None = None

    def configure(self) -> "Recorder":
        """Load the TCP endpoint and log path, then enter CONFIGURED."""
        self._transition("configure")
        self.host = str(self.configuration.get("host", "127.0.0.1"))
        self.port = int(self.configuration["port"])
        log_path = Path(str(self.configuration.get("log_path", "communication_log.txt")))
        if not log_path.is_absolute():
            log_path = Path(__file__).resolve().parent / log_path
        self.log_path = log_path
        return self

    def start(self) -> None:
        """Open the log file and TCP listener, then enter RUNNING."""
        if self.state == self.STATE_CREATED:
            self.configure()
        if self.state == self.STATE_CONFIGURED:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_path.open("a", encoding="utf-8")
            self._open_server()
            self._transition("prepare")
        self._transition("start")

    def stop(self) -> None:
        """Stop the listener, close the log file, and enter STOPPED."""
        if self.state == self.STATE_STOPPED:
            return
        self.stop_event.set()
        if self.server_socket is not None:
            self.server_socket.close()
        if self.log_file is not None:
            self.log_file.close()
        self._transition("stop")

    def fail(self, error: Exception | str) -> None:
        """Record an unrecoverable error and enter FAILED."""
        self.last_error = str(error)
        if self.state != self.STATE_FAILED:
            self._transition("fail")

    def _transition(self, event: str) -> None:
        next_state = self.TRANSITIONS.get(self.state, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"Recorder cannot {event} from {self.state}")
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
                self._record(json.loads(line))

    def _record(self, message: dict[str, Any]) -> None:
        record = {"logged_at": time.time(), "message": message}
        with self.write_lock:
            if self.log_file is None:
                return
            self.log_file.write(json.dumps(record, sort_keys=True) + "\n")
            self.log_file.flush()
