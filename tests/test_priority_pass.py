from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fedora_platform.priority_pass import (
    MicroscopicTrafficSumoSimulator,
    PRIORITY_PASS_CONTROLLER_TRANSITIONS,
    PriorityPassConfig,
    PriorityPassControllerState,
    PriorityPassControlParameters,
    PriorityPassTrafficOptimizer,
    ViennaPilot,
)


class PriorityPassTests(unittest.TestCase):
    def test_optimizer_generates_priority_pass_controller_settings(self) -> None:
        optimizer = PriorityPassTrafficOptimizer(
            PriorityPassControlParameters(tau=0.25, min_green=5)
        )

        result = optimizer.optimize({"intersections": ("J25", "J26")})

        self.assertEqual(set(result["tl_control"].keys()), {"J25", "J26"})
        self.assertEqual(result["tl_control"]["J25"]["type"], "priority_pass")
        self.assertEqual(result["tl_control"]["J25"]["trade_off"], 0.25)
        self.assertEqual(result["tl_control"]["J25"]["min_green_duration"], 5)

    def test_sumo_simulator_can_build_legacy_settings_without_running_sumo(
        self,
    ) -> None:
        config = PriorityPassConfig(
            model_root=ROOT / "models" / "pilot_vienna",
            intersections=("J25", "J26"),
            sumo_binary="sumo",
        )
        simulator = MicroscopicTrafficSumoSimulator(config)
        control = PriorityPassTrafficOptimizer().optimize(
            {"intersections": ("J25", "J26")}
        )

        simulator.configure({"tl_control": control["tl_control"]})

        self.assertEqual(set(simulator.settings.tl_control.keys()), {"J25", "J26"})
        self.assertTrue(simulator.settings.sumo_config_file.endswith("config.sumocfg"))
        self.assertEqual(
            simulator.settings.spawn_entrances_probabilities["0"],
            config.flow_vehicles_per_hour / 60 / 60,
        )

    def test_vienna_pilot_accepts_control_and_returns_sensor_snapshot(self) -> None:
        config = PriorityPassConfig(
            model_root=ROOT / "models" / "pilot_vienna",
            intersections=("J25", "J26"),
            sumo_binary="sumo",
        )
        optimizer = PriorityPassTrafficOptimizer()
        simulator = MicroscopicTrafficSumoSimulator(config)
        pilot = ViennaPilot(optimizer, simulator)
        control = optimizer.optimize({"intersections": ("J25", "J26")})

        pilot.configure()
        pilot.accept_traffic_light_control(control["tl_control"])
        snapshot = pilot.provide_sensor_data()

        self.assertEqual(snapshot["network"], "Vienna")
        self.assertEqual(snapshot["controlled_intersections"], ["J25", "J26"])

    def test_priority_pass_controller_fsm_states_are_exposed(self) -> None:
        self.assertEqual(PriorityPassControllerState.READY_FOR_AUCTION.value, 0)
        self.assertEqual(PriorityPassControllerState.CHANGING_SIGNAL.value, 1)
        self.assertIn(
            PriorityPassControllerState.CHANGING_SIGNAL,
            PRIORITY_PASS_CONTROLLER_TRANSITIONS[
                PriorityPassControllerState.READY_FOR_AUCTION
            ],
        )

    def test_vienna_model_folder_contains_no_python_runtime_files(self) -> None:
        python_files = list((ROOT / "models" / "pilot_vienna").rglob("*.py"))

        self.assertEqual(python_files, [])


if __name__ == "__main__":
    unittest.main()
