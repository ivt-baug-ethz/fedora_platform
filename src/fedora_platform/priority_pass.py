"""Priority Pass implementation on top of the FEDORA component model."""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import asdict, dataclass, replace
from enum import IntEnum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Optional

from fedora_platform.components import (
    ComponentState,
    DataStorage,
    Message,
    MessageBus,
    OptimizationModule,
    PilotSystem,
    SimulatorModule,
)


DEFAULT_VIENNA_INTERSECTIONS = (
    "J25",
    "J26",
    "J27",
    "J28",
    "J29",
    "J30",
    "J31",
    "J32",
    "J33",
)


class PriorityPassControllerState(IntEnum):
    """Finite states used by the Priority Pass traffic-light controller."""

    READY_FOR_AUCTION = 0
    CHANGING_SIGNAL = 1
    WAIT_MIN_GREEN_TIME = 2
    WAIT_FOR_NEXT_AUCTION = 3


PRIORITY_PASS_CONTROLLER_TRANSITIONS = {
    PriorityPassControllerState.READY_FOR_AUCTION: (
        PriorityPassControllerState.WAIT_FOR_NEXT_AUCTION,
        PriorityPassControllerState.CHANGING_SIGNAL,
    ),
    PriorityPassControllerState.CHANGING_SIGNAL: (
        PriorityPassControllerState.WAIT_MIN_GREEN_TIME,
    ),
    PriorityPassControllerState.WAIT_MIN_GREEN_TIME: (
        PriorityPassControllerState.READY_FOR_AUCTION,
    ),
    PriorityPassControllerState.WAIT_FOR_NEXT_AUCTION: (
        PriorityPassControllerState.READY_FOR_AUCTION,
    ),
}


@dataclass(frozen=True)
class PriorityPassControlParameters:
    """Parameters of the Priority Pass signal controller."""

    tau: float = 0.4
    min_green: int = 3
    auction_suspend: int = 4
    transition_duration: int = 3
    max_green: int = 60


@dataclass(frozen=True)
class PriorityPassConfig:
    """Configuration for the SUMO-based Priority Pass pilot."""

    flow_vehicles_per_hour: int = 200
    gamma_priority_share: float = 0.2
    network_name: str = "Vienna"
    model_root: Optional[Path] = None
    sumo_binary: Optional[str] = None
    use_gui: bool = False
    random_seed: int = 42
    spawn_horizon: int = 600 + 3600
    recording_interval: tuple[int, int] = (600, 600 + 3600)
    label: str = "priority_pass"
    wait_seconds: float = 0.0
    intersections: Optional[tuple[str, ...]] = None


class PriorityPassTrafficOptimizer(OptimizationModule):
    """Builds Priority Pass traffic-light controller settings."""

    def __init__(
        self,
        control_parameters: PriorityPassControlParameters | None = None,
        component_id: str = "optimizer.priority_pass",
        bus: Optional[MessageBus] = None,
    ) -> None:
        super().__init__(component_id, bus)
        self.control_parameters = control_parameters or PriorityPassControlParameters()

    def optimize(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        intersections = tuple(
            context.get("intersections") or DEFAULT_VIENNA_INTERSECTIONS
        )
        control = {
            tl_id: self._controller_settings()
            for tl_id in intersections
        }
        return {
            "controller_type": "priority_pass",
            "parameters": asdict(self.control_parameters),
            "tl_control": control,
        }

    def step(self) -> None:
        for message in self.receive(["priority_pass.optimization.requested"]):
            result = self.optimize(message.payload)
            self.publish(
                "priority_pass.control.generated",
                result,
                receiver=message.sender,
                correlation_id=message.correlation_id,
            )

    def _controller_settings(self) -> dict[str, Any]:
        params = self.control_parameters
        return {
            "type": "priority_pass",
            "transition_duration": params.transition_duration,
            "bidding_strategy": "phase_queue_length",
            "auction_winner": "highest_bid",
            "min_green_duration": params.min_green,
            "max_green_duration": params.max_green,
            "auction_suspend_duration": params.auction_suspend,
            "trade_off": params.tau,
        }


class MicroscopicTrafficSumoSimulator(SimulatorModule):
    """Adapter around the SUMO Priority Pass microscopic traffic simulator."""

    def __init__(
        self,
        config: PriorityPassConfig | None = None,
        component_id: str = "simulator.priority_pass_sumo",
        bus: Optional[MessageBus] = None,
    ) -> None:
        super().__init__(component_id, bus)
        self.config = config or PriorityPassConfig()
        self.settings: Optional[SimpleNamespace] = None
        self._legacy_simulator: Any = None
        self._last_results: Mapping[str, Any] = {}

    def configure(self, configuration: Optional[Mapping[str, Any]] = None) -> None:
        configuration = dict(configuration or {})
        tl_control = configuration.pop("tl_control", None)
        self.settings = self.build_settings(tl_control=tl_control)
        super().configure(configuration)
        self.publish(
            "priority_pass.simulator.configured",
            {
                "network": self.config.network_name,
                "intersections": list(self.settings.tl_control.keys()),
            },
        )

    def build_settings(
        self,
        tl_control: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ) -> SimpleNamespace:
        model_path = self._resolve_sumo_model_path()
        if not model_path.exists():
            raise FileNotFoundError(f"Priority Pass SUMO model not found: {model_path}")

        phase_bidder_lanes = self._load_json(model_path / "Phase_BidderLanes.json")
        phase_leaver_lanes = self._load_json(model_path / "Phase_ExitLanes.json")
        intersections = self.config.intersections or tuple(phase_bidder_lanes.keys())

        settings = SimpleNamespace()
        settings.sumo_location = self._resolve_sumo_binary()
        settings.sumo_config_file = str(model_path / "Configuration.sumocfg")
        settings.random_seed = self.config.random_seed
        settings.spawn_horizon = self.config.spawn_horizon
        settings.recording_settings = {
            "recording_interval": list(self.config.recording_interval),
            "phase_wait_time": True,
            "phase_queue_length": True,
            "emissions": False,
            "phase_throughput": True,
            "vehicle_travel_time": True,
        }
        settings.spawn_entrances_probabilities = self._spawn_probabilities(
            self.config.flow_vehicles_per_hour
        )
        settings.spawn_entrances_routes_probabilities = self._load_json(
            model_path / "Route_Probabilities.json"
        )
        settings.vot_spawn_probabilities = {
            0: 1 - self.config.gamma_priority_share,
            1: self.config.gamma_priority_share,
        }
        settings.vot_upp_spawn_probabilities = {0: 0.0, 1: 1.0}
        settings.route_min_possible_travel_time = self._load_json(
            model_path / "Route_Durations.json"
        )
        settings.route_recording_start_edge = self._load_json(
            model_path / "Route_StartEdges.json"
        )
        settings.route_recording_completion_edge = self._load_json(
            model_path / "Route_EndEdges.json"
        )
        settings.route_length = self._load_json(model_path / "Route_Distances.json")
        settings.phase_bidder_lanes = {
            tl_id: phase_bidder_lanes[tl_id]
            for tl_id in intersections
            if tl_id in phase_bidder_lanes
        }
        settings.phase_leaver_lanes = {
            tl_id: phase_leaver_lanes[tl_id]
            for tl_id in intersections
            if tl_id in phase_leaver_lanes
        }
        settings.sensor = {"max_distance_from_intersection": 100}
        settings.color_upp = (30, 111, 192, 255)
        settings.color_npp = (110, 110, 110, 255)
        settings.tl_control = dict(tl_control or {})
        if not settings.tl_control:
            control = PriorityPassTrafficOptimizer().optimize(
                {"intersections": tuple(settings.phase_bidder_lanes.keys())}
            )
            settings.tl_control = dict(control["tl_control"])
        return settings

    def start(self) -> None:
        if self.state == ComponentState.CREATED:
            self.configure()
        if self.state == ComponentState.CONFIGURED:
            self.transition_to(ComponentState.READY)
        if self.settings is None:
            raise RuntimeError("Priority Pass simulator has no settings")

        simulator_module = self._load_legacy_module("Simulator")
        self._legacy_simulator = simulator_module.Simulator(
            self.settings,
            label=self.config.label,
        )
        self._legacy_simulator.open_simulation()
        self.transition_to(ComponentState.RUNNING)
        self.publish(
            "priority_pass.simulation.started",
            {"label": self.config.label, "network": self.config.network_name},
        )

    def step(self) -> None:
        for message in self.receive():
            self.handle_message(message)
        if self.state != ComponentState.RUNNING:
            return

        if self._legacy_simulator._criterion_to_abort():
            self.stop()
            return
        self._legacy_simulator.run_simulation_step(wait=self.config.wait_seconds)

    def run_until_complete(self) -> Mapping[str, Any]:
        self.start()
        while self.state == ComponentState.RUNNING:
            self.step()
        return self.collect_results()

    def stop(self) -> None:
        results: Mapping[str, Any] = self._last_results
        if self._legacy_simulator is not None:
            results = self.collect_results()
            self._legacy_simulator.close_simulation()
            self._legacy_simulator = None
        if self.state != ComponentState.STOPPED:
            super().stop()
        self.publish("priority_pass.simulation.completed", results)

    def collect_results(self) -> Mapping[str, Any]:
        if self._legacy_simulator is None:
            return self._last_results
        tools_module = self._load_legacy_module("SimulationTools")
        self._last_results = tools_module.analyse_experiment_PriorityPass(
            self.settings,
            self._legacy_simulator.recorder,
        )
        return self._last_results

    def handle_message(self, message: Message) -> None:
        if message.topic == "priority_pass.control.generated":
            tl_control = message.payload.get("tl_control")
            if tl_control and self.state in {
                ComponentState.CREATED,
                ComponentState.CONFIGURED,
                ComponentState.READY,
            }:
                self.configure({"tl_control": tl_control})

    def _load_legacy_module(self, module_name: str) -> Any:
        return importlib.import_module(
            f"fedora_platform.traffic_model_sumo.{module_name}"
        )

    def _resolve_model_root(self) -> Path:
        if self.config.model_root is not None:
            return Path(self.config.model_root).resolve()

        candidates = [
            Path.cwd() / "models" / "pilot_vienna",
            Path(__file__).resolve().parents[2] / "models" / "pilot_vienna",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError("Could not locate models/pilot_vienna")

    def _resolve_sumo_model_path(self) -> Path:
        model_root = self._resolve_model_root()
        if (model_root / "Configuration.sumocfg").exists():
            return model_root
        return model_root / "sumo"

    def _resolve_sumo_binary(self) -> str:
        if self.config.sumo_binary:
            return self.config.sumo_binary
        env_key = "SUMO_GUI_BINARY" if self.config.use_gui else "SUMO_BINARY"
        if os.environ.get(env_key):
            return os.environ[env_key]
        return "sumo-gui" if self.config.use_gui else "sumo"

    @staticmethod
    def _spawn_probabilities(flow_vehicles_per_hour: int) -> dict[str, float]:
        return {str(index): flow_vehicles_per_hour / 60 / 60 for index in range(12)}

    @staticmethod
    def _load_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


class ViennaPilot(PilotSystem):
    """Dummy Vienna pilot backed by a SUMO simulation.

    The pilot represents the field side of the architecture: it publishes sensor
    snapshots and accepts traffic-light control plans. For local experiments the
    field side is another SUMO simulator, while later deployments can replace it
    with a real roadside or traffic-management integration.
    """

    def __init__(
        self,
        optimizer: PriorityPassTrafficOptimizer,
        simulator: MicroscopicTrafficSumoSimulator,
        storage: Optional[DataStorage] = None,
        field_simulator: Optional[MicroscopicTrafficSumoSimulator] = None,
        component_id: str = "pilot.vienna",
        bus: Optional[MessageBus] = None,
    ) -> None:
        super().__init__(component_id, bus)
        self.optimizer = optimizer
        self.simulator = simulator
        self.field_simulator = field_simulator or MicroscopicTrafficSumoSimulator(
            replace(simulator.config, label="vienna_field_pilot"),
            component_id="pilot.vienna.sumo_field",
            bus=bus,
        )
        self.storage = storage
        self._last_results: Mapping[str, Any] = {}
        self._current_tl_control: Mapping[str, Mapping[str, Any]] = {}

    def configure(self, configuration: Optional[Mapping[str, Any]] = None) -> None:
        super().configure(configuration)
        if self.bus is not None:
            for component in (
                self.optimizer,
                self.simulator,
                self.field_simulator,
                self.storage,
            ):
                if component is not None and component.bus is not self.bus:
                    component.attach_bus(self.bus)
            self.bus.subscribe("priority_pass.control.generated", self.component_id)
            self.bus.subscribe("priority_pass.simulation.completed", self.component_id)
            self.bus.subscribe("traffic.control.command", self.component_id)
            self.bus.subscribe("sensor.snapshot.requested", self.component_id)

    def run(self) -> Mapping[str, Any]:
        if self.state == ComponentState.CREATED:
            self.configure()
        self.start()

        intersections = self.simulator.config.intersections or DEFAULT_VIENNA_INTERSECTIONS
        optimization = self.optimizer.optimize({"intersections": intersections})
        self.publish("priority_pass.control.generated", optimization)
        self.accept_traffic_light_control(optimization["tl_control"])
        self.simulator.configure({"tl_control": optimization["tl_control"]})

        if self.storage is not None:
            self.storage.write(
                "vienna_priority_pass/configuration",
                {
                    "simulator": _jsonable_dataclass(self.simulator.config),
                    "field_simulator": _jsonable_dataclass(self.field_simulator.config),
                    "optimizer": asdict(self.optimizer.control_parameters),
                },
            )
            self.storage.write(
                "vienna_priority_pass/sensor_snapshot",
                self.provide_sensor_data(),
            )

        self._last_results = self.simulator.run_until_complete()
        if self.storage is not None:
            self.storage.write("vienna_priority_pass/results", self._last_results)
        self.stop()
        return self._last_results

    def step(self) -> None:
        for message in self.receive():
            self.handle_message(message)
        if self.field_simulator.state == ComponentState.RUNNING:
            self.field_simulator.step()
            self.publish("vienna_pilot.sensor.snapshot", self.provide_sensor_data())

    def handle_message(self, message: Message) -> None:
        if message.topic == "priority_pass.simulation.completed":
            self._last_results = message.payload
        elif message.topic in {
            "priority_pass.control.generated",
            "traffic.control.command",
        }:
            tl_control = message.payload.get("tl_control", message.payload)
            self.accept_traffic_light_control(tl_control)
        elif message.topic == "sensor.snapshot.requested":
            self.publish(
                "vienna_pilot.sensor.snapshot",
                self.provide_sensor_data(),
                receiver=message.sender,
                correlation_id=message.correlation_id,
            )

    def accept_traffic_light_control(
        self,
        tl_control: Mapping[str, Mapping[str, Any]],
    ) -> None:
        """Accept a traffic-light control plan from an optimizer or TMC."""

        self._current_tl_control = dict(tl_control)
        if self.field_simulator.state in {
            ComponentState.CREATED,
            ComponentState.CONFIGURED,
            ComponentState.READY,
        }:
            self.field_simulator.configure({"tl_control": self._current_tl_control})
        self.publish(
            "vienna_pilot.control.accepted",
            {"intersections": list(self._current_tl_control.keys())},
        )

    def provide_sensor_data(self) -> Mapping[str, Any]:
        """Return the latest dummy field sensor snapshot."""

        snapshot: dict[str, Any] = {
            "source": "vienna_sumo_dummy_pilot",
            "network": self.field_simulator.config.network_name,
            "state": self.field_simulator.state.value,
            "flow_vehicles_per_hour": self.field_simulator.config.flow_vehicles_per_hour,
            "controlled_intersections": list(self._current_tl_control.keys()),
        }

        legacy_simulator = self.field_simulator._legacy_simulator
        if legacy_simulator is not None:
            vehicle_lanes = getattr(legacy_simulator, "vehicle_lanes", {})
            lane_vehicle_counts: dict[str, int] = {}
            for lane in vehicle_lanes.values():
                lane_vehicle_counts[lane] = lane_vehicle_counts.get(lane, 0) + 1
            snapshot.update(
                {
                    "simulation_time": getattr(legacy_simulator, "time", None),
                    "vehicle_count": len(getattr(legacy_simulator, "vehicle_ids", [])),
                    "lane_vehicle_counts": lane_vehicle_counts,
                }
            )

        return snapshot


def _jsonable_dataclass(value: Any) -> dict[str, Any]:
    data = asdict(value)
    for key, item in list(data.items()):
        if isinstance(item, Path):
            data[key] = str(item)
    return data
