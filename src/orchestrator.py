"""TCP orchestrator FSM — sole orchestrator of the FEDORA platform."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Any

from controller_fixed_cycle import FixedCycleController
from controller_max_pressure import MaxPressureController
from controller_priority_pass import PriorityPassController
from recorder import Recorder
from simulation_sumo import Simulation

_AnyLogicModule = FixedCycleController | MaxPressureController | PriorityPassController


class Orchestrator:
    """Sole orchestrator of the FEDORA platform: creates all sub-components and drives the simulation loop.

    Reads the full JSON configuration, instantiates Recorder, LogicModule, and Simulation,
    then injects step and apply_and_advance signals to advance the simulation one step at a time.
    """

    NAME = "orchestrator"
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
        STATE_READY: {
            "start": STATE_RUNNING,
            "stop": STATE_STOPPED,
            "fail": STATE_FAILED,
        },
        STATE_RUNNING: {"stop": STATE_STOPPED, "fail": STATE_FAILED},
        STATE_STOPPED: {"configure": STATE_CONFIGURED, "fail": STATE_FAILED},
        STATE_FAILED: {"stop": STATE_STOPPED},
    }

    _LOGIC_MODULE_TYPES: dict[str, type] = {
        "controller_fixed_cycle": FixedCycleController,
        "controller_max_pressure": MaxPressureController,
        "controller_priority_pass": PriorityPassController,
    }

    def __init__(self, configuration: dict[str, Any]):
        """Initialize the orchestrator in the CREATED state.

        Args:
            configuration: Full platform configuration dict (loaded from JSON).
        """
        self.configuration = configuration
        self.state = self.STATE_CREATED

        # network endpoint for the orchestrator's own TCP listener
        self.host = "127.0.0.1"
        self.port = 0
        self.socket_timeout = 2.0
        self.startup_pause_seconds = 0.2

        # component registry: name → (host, port); populated in configure()
        self.components: dict[str, tuple[str, int]] = {}
        self.recorder: Recorder | None = None
        self.logic_module: _AnyLogicModule | None = None
        self.simulation: Simulation | None = None

        # set to True once simulation_started is received; back to False on simulation_stopped
        self.simulation_running: bool = False

        # TCP server for receiving messages from all sub-components
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.done_event = threading.Event()
        self.last_error: str | None = None

        # persistent outgoing connections keyed by component name
        self._connections: dict[str, socket.socket | None] = {}
        self._connections_lock = threading.Lock()

    def configure(self) -> "Orchestrator":
        """Read the full config, build all sub-component objects, and enter CONFIGURED.

        Returns:
            self, for method chaining.
        """
        self._transition("configure")

        # extract the top-level config sections used throughout configuration
        communication = dict(self.configuration["communication"])
        setup = dict(self.configuration.get("setup", {}))

        # own TCP endpoint and tuning parameters
        self.host = str(communication.get("host", "127.0.0.1"))
        self.port = int(communication["ports"]["orchestrator"])
        self.socket_timeout = float(communication.get("socket_timeout", 2.0))
        self.startup_pause_seconds = float(setup.get("startup_pause_seconds", 0.2))

        # register all sub-component endpoints (all ports except the orchestrator's own)
        ports = dict(communication["ports"])
        self.components = {
            name: (self.host, int(port))
            for name, port in ports.items()
            if name != "orchestrator"
        }

        # build recorder with its dedicated TCP port and log directory
        recorder_cfg = dict(self.configuration["recorder"])
        recorder_cfg["host"] = self.host
        recorder_cfg["port"] = int(communication["ports"]["recorder"])
        self.recorder = Recorder(recorder_cfg)

        self._configure_logic_module(
            communication, setup, dict(self.configuration["logic_module"])
        )

        # ask the logic module which measurements it needs, then pass them to the simulation
        required = self.logic_module.get_required_measurements()  # type: ignore[union-attr]
        sim_cfg = dict(self.configuration["simulation"])
        sim_cfg["_scenario_path"] = str(self.configuration["scenario_path"])
        sim_cfg["_logs_dir"] = str(self.configuration["recorder"]["logs_dir"])
        self._configure_simulation(communication, setup, sim_cfg, required)
        return self

    def start(self) -> None:
        """Open the TCP listener, start sub-components in order, and enter RUNNING."""
        if self.state == self.STATE_CREATED:
            self.configure()
        if self.state == self.STATE_CONFIGURED:
            self._open_server()
            self._transition("prepare")
        self._transition("start")
        assert self.recorder is not None
        assert self.logic_module is not None
        assert self.simulation is not None

        # start in order: recorder first so no messages are lost, then logic_module, then simulation
        self.recorder.start()
        time.sleep(self.startup_pause_seconds)
        self.logic_module.start()
        time.sleep(self.startup_pause_seconds)

        # simulation start triggers SUMO and fires simulation_started, which kicks off the loop
        self.simulation.start()

    def stop(self) -> None:
        """Stop all sub-components, close the TCP server, and enter STOPPED."""
        if self.state == self.STATE_STOPPED:
            return

        # signal all server threads to exit
        self.stop_event.set()

        # stop in reverse startup order: simulation first so no new messages arrive
        for component in (self.simulation, self.logic_module, self.recorder):
            if component is not None:
                component.stop()

        # close all persistent outgoing connections
        with self._connections_lock:
            for conn in self._connections.values():
                if conn is not None:
                    try:
                        conn.close()
                    except OSError:
                        pass
            self._connections.clear()

        if self.server_socket is not None:
            self.server_socket.close()
        self._transition("stop")

    def wait_until_done(self) -> None:
        """Block the calling thread until the simulation signals completion."""
        self.done_event.wait()
        if self.simulation is not None:
            self.simulation.wait_until_done()

    def fail(self, error: Exception | str) -> None:
        """Record an unrecoverable error and enter FAILED.

        Args:
            error: The exception or message describing the failure.
        """
        self.last_error = str(error)
        if self.state != self.STATE_FAILED:
            self._transition("fail")

    # ------------------------------------------------------------------
    # Sub-component construction
    # ------------------------------------------------------------------

    def _configure_logic_module(
        self,
        communication: dict,
        setup: dict,
        logic_module_cfg: dict,
    ) -> None:
        """Instantiate the correct logic module type from configuration.

        Args:
            communication: Communication section of the top-level config.
            setup: Setup section of the top-level config.
            logic_module_cfg: Logic module section of the top-level config.
        """
        cfg = dict(logic_module_cfg)

        # inject network and shared setup fields before passing to the logic module
        cfg["host"] = self.host
        cfg["port"] = int(communication["ports"]["logic_module"])
        cfg["orchestrator"] = {"host": self.host, "port": self.port}
        cfg["random_seed"] = int(setup.get("random_seed", 42))
        cfg["traffic_lights"] = list(setup.get("traffic_lights", []))

        # look up logic module class by type string (e.g. "controller_priority_pass")
        logic_module_type = str(logic_module_cfg.get("type"))
        cls = self._LOGIC_MODULE_TYPES[logic_module_type]
        self.logic_module = cls(cfg)

    def _configure_simulation(
        self,
        communication: dict,
        setup: dict,
        sim_cfg: dict,
        required_measurements: list[str],
    ) -> None:
        """Assemble the simulation configuration and instantiate the Simulation object.

        Args:
            communication: Communication section of the top-level config.
            setup: Setup section of the top-level config.
            sim_cfg: Simulation section dict (modified in-place).
            required_measurements: Lane measurement types requested by the logic module.
        """
        # pop internal transport keys added by configure() before passing the dict to Simulation
        scenario_path = str(sim_cfg.pop("_scenario_path"))
        logs_dir = str(sim_cfg.pop("_logs_dir"))
        cfg = sim_cfg

        # inject network, orchestrator endpoint, and measurement requirements
        cfg["host"] = self.host
        cfg["port"] = int(communication["ports"]["simulation"])
        cfg["orchestrator"] = {"host": self.host, "port": self.port}
        cfg["setup"] = setup
        cfg["network"] = {"traffic_lights": list(setup.get("traffic_lights", []))}
        cfg["controller_response_timeout_seconds"] = float(
            setup.get("controller_response_timeout_seconds", 0.05)
        )

        # copy sumo_details so we don't mutate the original config
        cfg["sumo_details"] = dict(cfg["sumo_details"])
        cfg["sumo_details"]["random_seed"] = int(setup.get("random_seed", 42))
        cfg["logs_dir"] = logs_dir
        cfg["lane_measurements_enabled"] = required_measurements
        self.simulation = Simulation(cfg, scenario_path=Path(scenario_path))

    # ------------------------------------------------------------------
    # TCP server
    # ------------------------------------------------------------------

    def _transition(self, event: str) -> None:
        """Apply a lifecycle event and advance the FSM state.

        Args:
            event: Transition event name (e.g. "configure", "start", "stop").
        """
        next_state = self.TRANSITIONS.get(self.state, {}).get(event)
        if next_state is None:
            raise RuntimeError(f"Orchestrator cannot {event} from {self.state}")

        # set the new state
        self.state = next_state

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
                        self._route(json.loads(line))

    # ------------------------------------------------------------------
    # Routing and orchestration
    # ------------------------------------------------------------------

    def _route(self, message: dict[str, Any]) -> None:
        """Route an incoming message and hook into key topics to orchestrate the loop.

        Args:
            message: Decoded JSON message dict.
        """
        # stamp arrival time and extract routing fields
        message.setdefault("received_at", time.time())
        sender = str(message.get("sender", "unknown"))
        target = str(message.get("target", "broadcast"))
        topic = str(message.get("topic", ""))

        # log everything except messages already destined for the recorder
        if target != "recorder":
            self._log_message(message)

        # orchestration hooks — intercept key topics to drive the step/apply loop
        if topic == "simulation_started":
            self.simulation_running = True
            self._send_step_to_simulation()
            return

        if topic == "traffic_light_command" and sender == "logic_module":
            # apply controller decisions then request the next measurement step
            commands = dict(message.get("payload", {}).get("commands", {}))
            self._send_apply_and_advance(commands)
            if self.simulation_running:
                self._send_step_to_simulation()
            return

        if topic == "simulation_stopped":
            self.simulation_running = False
            self.done_event.set()
            return

        # normal routing: forward to the named target or all components if broadcast
        if target == "broadcast":
            for component in self.components:
                if component != sender:
                    self._forward(component, message)
            return

        if target in self.components:
            self._forward(target, message)

    def _log_message(self, message: dict[str, Any]) -> None:
        """Forward a copy of the message to the recorder as a communication log entry.

        Args:
            message: The message to log.
        """
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

    def _send_step_to_simulation(self) -> None:
        """Tell the simulation to begin its next measurement-collection iteration."""
        self._forward(
            "simulation",
            {
                "sender": self.NAME,
                "target": "simulation",
                "topic": "step",
                "sent_at": time.time(),
                "payload": {},
            },
        )

    def _send_apply_and_advance(self, commands: dict[str, Any]) -> None:
        """Tell the simulation to apply the given signal commands and advance one SUMO step.

        Args:
            commands: Dict mapping traffic-light ID to the target phase signal index.
        """
        self._forward(
            "simulation",
            {
                "sender": self.NAME,
                "target": "simulation",
                "topic": "apply_and_advance",
                "sent_at": time.time(),
                "payload": {"commands": commands},
            },
        )

    def _forward(self, target: str, message: dict[str, Any]) -> None:
        """Send a message to a target component over its persistent TCP connection.

        Args:
            target: Destination component name (e.g. "simulation", "logic_module").
            message: Message dict to serialize and send.
        """
        endpoint = self.components.get(target)
        if endpoint is None:
            return

        encoded = json.dumps(message, sort_keys=True).encode("utf-8") + b"\n"
        with self._connections_lock:
            conn = self._connections.get(target)
            try:
                # lazily create and cache the connection on first use
                if conn is None:
                    conn = socket.create_connection(
                        endpoint, timeout=self.socket_timeout
                    )
                    conn.settimeout(None)
                    self._connections[target] = conn
                conn.sendall(encoded)

            except OSError as error:
                self.last_error = f"Could not forward to {target}: {error}"
                # invalidate the cached connection so the next call reconnects
                try:
                    if conn is not None:
                        conn.close()
                except OSError:
                    pass
                self._connections[target] = None
