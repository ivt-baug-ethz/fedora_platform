"""Unit tests for fixed-cycle, max-pressure, and priority-pass controllers."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from controller_fixed_cycle import FixedCycleController
from controller_max_pressure import MaxPressureController
from controller_priority_pass import PriorityPassController


def _fixed_cycle_cfg(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid FixedCycleController configuration."""
    cfg: dict[str, Any] = {
        "host": "127.0.0.1",
        "port": 0,
        "orchestrator": {"host": "127.0.0.1", "port": 0},
        "traffic_lights": ["TL1"],
        "random_seed": 0,
        "fixed_cycle": {
            "phase_durations": [30, 30],
            "transition_duration": 3,
            "time_delays": {},
            "default_time_delay": 0,
        },
    }
    cfg.update(overrides)
    return cfg


def _max_pressure_cfg(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid MaxPressureController configuration."""
    cfg: dict[str, Any] = {
        "host": "127.0.0.1",
        "port": 0,
        "orchestrator": {"host": "127.0.0.1", "port": 0},
        "traffic_lights": ["TL1"],
        "random_seed": 0,
        "max_pressure": {
            "bidding_strategy": "phase_queue_length",
            "auction_winner": "highest_bid",
            "min_green_duration": 5,
            "max_green_duration": 20,
            "auction_suspend_duration": 3,
            "transition_duration": 2,
        },
    }
    cfg.update(overrides)
    return cfg


def _priority_pass_cfg(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid PriorityPassController configuration."""
    cfg: dict[str, Any] = {
        "host": "127.0.0.1",
        "port": 0,
        "orchestrator": {"host": "127.0.0.1", "port": 0},
        "traffic_lights": ["TL1"],
        "random_seed": 0,
        "priority_pass": {
            "bidding_strategy": "phase_queue_length",
            "auction_winner": "highest_bid",
            "min_green_duration": 5,
            "max_green_duration": 20,
            "auction_suspend_duration": 3,
            "transition_duration": 2,
            "trade_off": 0.5,
        },
    }
    cfg.update(overrides)
    return cfg


class TestFixedCycleFSM(unittest.TestCase):
    """FSM lifecycle and state transitions for FixedCycleController."""

    def test_initial_state_is_created(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        self.assertEqual(ctrl.state, FixedCycleController.STATE_CREATED)

    def test_configure_transitions_to_configured(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        ctrl.configure()
        self.assertEqual(ctrl.state, FixedCycleController.STATE_CONFIGURED)

    def test_configure_sets_attributes(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        ctrl.configure()
        self.assertEqual(ctrl.port, 0)
        self.assertEqual(ctrl.traffic_lights, ["TL1"])
        self.assertIn("phase_durations", ctrl.control)

    def test_stop_from_created(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        ctrl.stop()
        self.assertEqual(ctrl.state, FixedCycleController.STATE_STOPPED)

    def test_stop_from_configured(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        ctrl.configure()
        ctrl.stop()
        self.assertEqual(ctrl.state, FixedCycleController.STATE_STOPPED)

    def test_fail_records_error(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        ctrl.fail("something broke")
        self.assertEqual(ctrl.state, FixedCycleController.STATE_FAILED)
        self.assertEqual(ctrl.last_error, "something broke")

    def test_invalid_transition_raises(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        with self.assertRaises(RuntimeError):
            ctrl._transition("start")  # cannot start from CREATED

    def test_get_required_measurements_is_empty(self) -> None:
        ctrl = FixedCycleController(_fixed_cycle_cfg())
        self.assertEqual(ctrl.get_required_measurements(), [])


class TestFixedCycleLogic(unittest.TestCase):
    """Phase-progression logic for FixedCycleController."""

    def _make_ctrl(
        self,
        phase_durations: list[int],
        transition_duration: int = 2,
        time_delays: dict | None = None,
    ) -> FixedCycleController:
        cfg = _fixed_cycle_cfg()
        cfg["fixed_cycle"]["phase_durations"] = phase_durations
        cfg["fixed_cycle"]["transition_duration"] = transition_duration
        cfg["fixed_cycle"]["time_delays"] = time_delays or {}
        ctrl = FixedCycleController(cfg)
        ctrl.configure()
        return ctrl

    def test_new_light_state_no_delay_starts_green(self) -> None:
        ctrl = self._make_ctrl([10, 10])
        state = ctrl.light_states["TL1"]
        self.assertEqual(state["cycle_state"], FixedCycleController.CYCLE_GREEN)
        self.assertEqual(state["phase"], 0)
        self.assertEqual(state["phase_signal"], 0)

    def test_new_light_state_with_delay_starts_in_delay(self) -> None:
        ctrl = self._make_ctrl([10, 10], time_delays={"TL1": 5})
        state = ctrl.light_states["TL1"]
        self.assertEqual(state["cycle_state"], FixedCycleController.CYCLE_DELAY)
        self.assertEqual(state["timer"], 5)

    def test_phase_duration(self) -> None:
        ctrl = self._make_ctrl([10, 20])
        self.assertEqual(ctrl._phase_duration(0), 10)
        self.assertEqual(ctrl._phase_duration(1), 20)
        # wraps around
        self.assertEqual(ctrl._phase_duration(2), 10)

    def test_step_counts_down_timer(self) -> None:
        ctrl = self._make_ctrl([3, 3])
        state = ctrl.light_states["TL1"]
        initial_timer = state["timer"]
        signal = ctrl._step_light(state)
        self.assertEqual(state["timer"], initial_timer - 1)
        self.assertEqual(signal, 0)

    def test_green_expires_to_transition(self) -> None:
        ctrl = self._make_ctrl([2, 2], transition_duration=1)
        state = ctrl.light_states["TL1"]
        # Run until timer reaches 0 (green expires)
        while state["timer"] > 0:
            ctrl._step_light(state)
        # Next step triggers green → transition
        ctrl._step_light(state)
        self.assertEqual(state["cycle_state"], FixedCycleController.CYCLE_TRANSITION)
        # Odd phase signal = transition
        self.assertEqual(state["phase_signal"] % 2, 1)

    def test_transition_expires_to_next_phase(self) -> None:
        # phase_durations=[1,1]: timer starts at 0, so each step fires immediately.
        # Step 1: timer=0, CYCLE_GREEN fires → enters CYCLE_TRANSITION (timer=0)
        # Step 2: timer=0, CYCLE_TRANSITION fires → enters CYCLE_GREEN at phase 1
        ctrl = self._make_ctrl([1, 1], transition_duration=1)
        state = ctrl.light_states["TL1"]
        ctrl._step_light(state)  # CYCLE_GREEN → CYCLE_TRANSITION
        ctrl._step_light(state)  # CYCLE_TRANSITION → CYCLE_GREEN at phase 1
        self.assertEqual(state["cycle_state"], FixedCycleController.CYCLE_GREEN)
        self.assertEqual(state["phase"], 1)
        self.assertEqual(state["phase_signal"], 2)  # phase 1 → signal 2

    def test_build_commands_returns_phase_signal(self) -> None:
        ctrl = self._make_ctrl([10, 10])
        traffic_state = {"traffic_lights": {"TL1": {}}}
        commands = ctrl._build_commands(traffic_state)
        self.assertIn("TL1", commands)
        self.assertIsInstance(commands["TL1"], int)

    def test_build_commands_auto_registers_new_lights(self) -> None:
        ctrl = self._make_ctrl([10, 10])
        traffic_state = {"traffic_lights": {"TL_NEW": {}}}
        commands = ctrl._build_commands(traffic_state)
        self.assertIn("TL_NEW", commands)
        self.assertIn("TL_NEW", ctrl.light_states)


class TestMaxPressureFSM(unittest.TestCase):
    """FSM lifecycle and state transitions for MaxPressureController."""

    def test_initial_state_is_created(self) -> None:
        ctrl = MaxPressureController(_max_pressure_cfg())
        self.assertEqual(ctrl.state, MaxPressureController.STATE_CREATED)

    def test_configure_transitions_to_configured(self) -> None:
        ctrl = MaxPressureController(_max_pressure_cfg())
        ctrl.configure()
        self.assertEqual(ctrl.state, MaxPressureController.STATE_CONFIGURED)

    def test_configure_sets_control_params(self) -> None:
        ctrl = MaxPressureController(_max_pressure_cfg())
        ctrl.configure()
        self.assertIn("min_green_duration", ctrl.control)
        self.assertEqual(ctrl.control["min_green_duration"], 5)

    def test_stop_from_created(self) -> None:
        ctrl = MaxPressureController(_max_pressure_cfg())
        ctrl.stop()
        self.assertEqual(ctrl.state, MaxPressureController.STATE_STOPPED)

    def test_fail_records_error(self) -> None:
        ctrl = MaxPressureController(_max_pressure_cfg())
        ctrl.fail(ValueError("oops"))
        self.assertEqual(ctrl.state, MaxPressureController.STATE_FAILED)
        self.assertIn("oops", ctrl.last_error)

    def test_invalid_transition_raises(self) -> None:
        ctrl = MaxPressureController(_max_pressure_cfg())
        with self.assertRaises(RuntimeError):
            ctrl._transition("start")

    def test_get_required_measurements_unweighted(self) -> None:
        ctrl = MaxPressureController(_max_pressure_cfg())
        self.assertEqual(ctrl.get_required_measurements(), ["queue_lengths"])

    def test_get_required_measurements_weighted(self) -> None:
        cfg = _max_pressure_cfg()
        cfg["max_pressure"]["bidding_strategy"] = "phase_weighted_queue_length"
        ctrl = MaxPressureController(cfg)
        self.assertEqual(ctrl.get_required_measurements(), ["weighted_queue_lengths"])


class TestMaxPressureLogic(unittest.TestCase):
    """Auction logic for MaxPressureController."""

    def _make_ctrl(self) -> MaxPressureController:
        ctrl = MaxPressureController(_max_pressure_cfg())
        ctrl.configure()
        return ctrl

    def test_determine_auction_winner_picks_highest(self) -> None:
        ctrl = self._make_ctrl()
        self.assertEqual(ctrl._determine_auction_winner([1.0, 5.0, 3.0]), 1)
        self.assertEqual(ctrl._determine_auction_winner([0.0, 0.0, 7.0]), 2)

    def test_determine_auction_winner_tie_break(self) -> None:
        ctrl = self._make_ctrl()
        # Seeded RNG — just verify result is one of the tied indices
        winner = ctrl._determine_auction_winner([5.0, 5.0, 5.0])
        self.assertIn(winner, [0, 1, 2])

    def test_get_phase_bids_unweighted(self) -> None:
        ctrl = self._make_ctrl()
        metrics = {"queue_lengths": [3.0, 1.0, 2.0]}
        bids = ctrl._get_phase_bids(metrics)
        self.assertEqual(bids, [3.0, 1.0, 2.0])

    def test_get_phase_bids_weighted(self) -> None:
        cfg = _max_pressure_cfg()
        cfg["max_pressure"]["bidding_strategy"] = "phase_weighted_queue_length"
        ctrl = MaxPressureController(cfg)
        ctrl.configure()
        metrics = {"weighted_queue_lengths": [4.0, 2.0]}
        bids = ctrl._get_phase_bids(metrics)
        self.assertEqual(bids, [4.0, 2.0])

    def test_get_phase_bids_empty_returns_zero(self) -> None:
        ctrl = self._make_ctrl()
        bids = ctrl._get_phase_bids({})
        self.assertEqual(bids, [0.0])

    def test_build_commands_winner_phase_applied(self) -> None:
        ctrl = self._make_ctrl()
        # Phase 1 has by far the highest queue length → auction picks phase 1
        traffic_state = {
            "traffic_lights": {
                "TL1": {
                    "number_phases": 2,
                    "queue_lengths": [0.0, 100.0],
                }
            }
        }
        # Auction fires from AUCTION_READY on step 1
        commands = ctrl._build_commands(traffic_state)
        self.assertIn("TL1", commands)

    def test_new_light_state_starts_at_auction_ready(self) -> None:
        ctrl = self._make_ctrl()
        state = ctrl._new_light_state()
        self.assertEqual(state["auction_state"], MaxPressureController.AUCTION_READY)
        self.assertEqual(state["phase"], 0)

    def test_auction_transition_valid(self) -> None:
        ctrl = self._make_ctrl()
        state = ctrl._new_light_state()
        ctrl._auction_transition(state, "new_phase")
        self.assertEqual(
            state["auction_state"], MaxPressureController.AUCTION_CHANGING_SIGNAL
        )

    def test_auction_transition_invalid_raises(self) -> None:
        ctrl = self._make_ctrl()
        state = ctrl._new_light_state()
        with self.assertRaises(RuntimeError):
            ctrl._auction_transition(
                state, "min_green_done"
            )  # invalid from AUCTION_READY


class TestPriorityPassFSM(unittest.TestCase):
    """FSM lifecycle and state transitions for PriorityPassController."""

    def test_initial_state_is_created(self) -> None:
        ctrl = PriorityPassController(_priority_pass_cfg())
        self.assertEqual(ctrl.state, PriorityPassController.STATE_CREATED)

    def test_configure_transitions_to_configured(self) -> None:
        ctrl = PriorityPassController(_priority_pass_cfg())
        ctrl.configure()
        self.assertEqual(ctrl.state, PriorityPassController.STATE_CONFIGURED)

    def test_configure_sets_control_params(self) -> None:
        ctrl = PriorityPassController(_priority_pass_cfg())
        ctrl.configure()
        self.assertIn("trade_off", ctrl.control)
        self.assertAlmostEqual(float(ctrl.control["trade_off"]), 0.5)

    def test_stop_from_created(self) -> None:
        ctrl = PriorityPassController(_priority_pass_cfg())
        ctrl.stop()
        self.assertEqual(ctrl.state, PriorityPassController.STATE_STOPPED)

    def test_fail_transitions_to_failed(self) -> None:
        ctrl = PriorityPassController(_priority_pass_cfg())
        ctrl.fail("bad input")
        self.assertEqual(ctrl.state, PriorityPassController.STATE_FAILED)
        self.assertEqual(ctrl.last_error, "bad input")

    def test_invalid_transition_raises(self) -> None:
        ctrl = PriorityPassController(_priority_pass_cfg())
        with self.assertRaises(RuntimeError):
            ctrl._transition("start")

    def test_get_required_measurements_unweighted(self) -> None:
        ctrl = PriorityPassController(_priority_pass_cfg())
        measurements = ctrl.get_required_measurements()
        self.assertIn("queue_lengths", measurements)
        self.assertIn("upp_bids", measurements)

    def test_get_required_measurements_weighted(self) -> None:
        cfg = _priority_pass_cfg()
        cfg["priority_pass"]["bidding_strategy"] = "phase_weighted_queue_length"
        ctrl = PriorityPassController(cfg)
        measurements = ctrl.get_required_measurements()
        self.assertIn("weighted_queue_lengths", measurements)
        self.assertIn("upp_bids", measurements)


class TestPriorityPassLogic(unittest.TestCase):
    """Bid-blending logic for PriorityPassController."""

    def _make_ctrl(self, trade_off: float = 0.5) -> PriorityPassController:
        cfg = _priority_pass_cfg()
        cfg["priority_pass"]["trade_off"] = trade_off
        ctrl = PriorityPassController(cfg)
        ctrl.configure()
        return ctrl

    def test_bid_blending_formula(self) -> None:
        # tau = 0.5, queue_bids = [4, 2], upp_bids = [0, 8]
        # phase 0: 0.5*4 + 0.5*0 = 2.0
        # phase 1: 0.5*2 + 0.5*8 = 5.0
        ctrl = self._make_ctrl(trade_off=0.5)
        metrics = {"queue_lengths": [4.0, 2.0], "upp_bids": [0.0, 8.0]}
        bids = ctrl._get_priority_pass_bids(metrics)
        self.assertAlmostEqual(bids[0], 2.0)
        self.assertAlmostEqual(bids[1], 5.0)

    def test_bid_blending_tau_zero_ignores_upp(self) -> None:
        ctrl = self._make_ctrl(trade_off=0.0)
        metrics = {"queue_lengths": [3.0, 1.0], "upp_bids": [100.0, 100.0]}
        bids = ctrl._get_priority_pass_bids(metrics)
        self.assertAlmostEqual(bids[0], 3.0)
        self.assertAlmostEqual(bids[1], 1.0)

    def test_bid_blending_tau_one_ignores_queue(self) -> None:
        ctrl = self._make_ctrl(trade_off=1.0)
        metrics = {"queue_lengths": [100.0, 100.0], "upp_bids": [5.0, 2.0]}
        bids = ctrl._get_priority_pass_bids(metrics)
        self.assertAlmostEqual(bids[0], 5.0)
        self.assertAlmostEqual(bids[1], 2.0)

    def test_bid_blending_missing_upp_defaults_to_zero(self) -> None:
        ctrl = self._make_ctrl(trade_off=0.5)
        # No upp_bids in metrics
        metrics = {"queue_lengths": [4.0, 2.0]}
        bids = ctrl._get_priority_pass_bids(metrics)
        self.assertAlmostEqual(bids[0], 2.0)  # 0.5*4 + 0.5*0
        self.assertAlmostEqual(bids[1], 1.0)  # 0.5*2 + 0.5*0

    def test_determine_auction_winner_picks_highest(self) -> None:
        ctrl = self._make_ctrl()
        self.assertEqual(ctrl._determine_auction_winner([1.0, 9.0, 3.0]), 1)

    def test_build_commands_returns_dict_for_known_lights(self) -> None:
        ctrl = self._make_ctrl()
        traffic_state = {
            "traffic_lights": {
                "TL1": {
                    "number_phases": 2,
                    "queue_lengths": [1.0, 2.0],
                    "upp_bids": [0.0, 0.0],
                }
            }
        }
        commands = ctrl._build_commands(traffic_state)
        self.assertIn("TL1", commands)
        self.assertIsInstance(commands["TL1"], int)

    def test_weighted_bid_strategy(self) -> None:
        cfg = _priority_pass_cfg()
        cfg["priority_pass"]["bidding_strategy"] = "phase_weighted_queue_length"
        cfg["priority_pass"]["trade_off"] = 0.0
        ctrl = PriorityPassController(cfg)
        ctrl.configure()
        metrics = {
            "weighted_queue_lengths": [6.0, 2.0],
            "upp_bids": [0.0, 0.0],
        }
        bids = ctrl._get_priority_pass_bids(metrics)
        self.assertAlmostEqual(bids[0], 6.0)
        self.assertAlmostEqual(bids[1], 2.0)


class TestPriorityPassMaxPressureEquivalence(unittest.TestCase):
    """Regression tests for Priority Pass behaving like Max-Pressure at tau=0."""

    def test_tau_zero_matches_max_pressure_phase_sequence(self) -> None:
        max_cfg = _max_pressure_cfg()
        priority_cfg = _priority_pass_cfg()
        priority_cfg["priority_pass"].update(
            {
                key: value
                for key, value in max_cfg["max_pressure"].items()
                if key != "auction_winner"
            }
        )
        priority_cfg["priority_pass"]["auction_winner"] = max_cfg["max_pressure"][
            "auction_winner"
        ]
        priority_cfg["priority_pass"]["trade_off"] = 0.0

        max_ctrl = MaxPressureController(max_cfg)
        priority_ctrl = PriorityPassController(priority_cfg)
        max_ctrl.configure()
        priority_ctrl.configure()

        traffic_states = [
            {"number_phases": 3, "queue_lengths": [0.0, 7.0, 1.0]},
            {"number_phases": 3, "queue_lengths": [9.0, 2.0, 1.0]},
            {"number_phases": 3, "queue_lengths": [3.0, 3.0, 3.0]},
            {"number_phases": 3, "queue_lengths": [1.0, 0.0, 8.0]},
        ]

        for step in range(20):
            metrics = dict(traffic_states[step % len(traffic_states)])
            priority_metrics = dict(metrics)
            priority_metrics["upp_bids"] = [99.0, 0.0, 99.0]
            max_commands = max_ctrl._build_commands(
                {"traffic_lights": {"TL1": metrics}}
            )
            priority_commands = priority_ctrl._build_commands(
                {"traffic_lights": {"TL1": priority_metrics}}
            )

            self.assertEqual(priority_commands, max_commands)
            self.assertEqual(
                priority_ctrl.light_states["TL1"], max_ctrl.light_states["TL1"]
            )

    def test_priority_pass_configs_share_max_pressure_auction_timing(self) -> None:
        compared_fields = [
            "transition_duration",
            "bidding_strategy",
            "auction_winner",
            "min_green_duration",
            "max_green_duration",
            "auction_suspend_duration",
        ]

        for scenario in ("demo", "vienna"):
            with self.subTest(scenario=scenario):
                max_config_path = (
                    ROOT
                    / "configurations"
                    / f"{scenario}_sumo_max_pressure_config.json"
                )
                priority_config_path = (
                    ROOT
                    / "configurations"
                    / f"{scenario}_sumo_priority_pass_config.json"
                )
                max_config = json.loads(max_config_path.read_text(encoding="utf-8"))
                priority_config = json.loads(
                    priority_config_path.read_text(encoding="utf-8")
                )
                max_control = max_config["logic_modules"][0]["max_pressure"]
                priority_control = priority_config["logic_modules"][0]["priority_pass"]

                for field in compared_fields:
                    self.assertEqual(priority_control[field], max_control[field])


class TestOrchestratorBaselineMode(unittest.TestCase):
    """Verify the Orchestrator handles zero logic modules (baseline mode)."""

    def _make_bare_orchestrator(self):
        """Return an Orchestrator stub with no logic modules configured."""
        from orchestrator import Orchestrator

        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.host = "127.0.0.1"
        orchestrator.port = 0
        orchestrator.logic_modules = []
        orchestrator._logic_module_names = []
        return orchestrator

    def test_configure_logic_modules_empty_list(self) -> None:
        from orchestrator import Orchestrator

        orchestrator = self._make_bare_orchestrator()
        communication = {"ports": {}}
        setup = {"random_seed": 42, "traffic_lights": []}
        orchestrator._configure_logic_modules(communication, setup, [])
        self.assertEqual(orchestrator.logic_modules, [])
        self.assertEqual(orchestrator._logic_module_names, [])

    def test_baseline_required_measurements_is_empty(self) -> None:
        from orchestrator import Orchestrator

        orchestrator = self._make_bare_orchestrator()
        communication = {"ports": {}}
        setup = {"random_seed": 42, "traffic_lights": []}
        orchestrator._configure_logic_modules(communication, setup, [])
        required: list[str] = []
        for module in orchestrator.logic_modules:
            for m in module.get_required_measurements():
                if m not in required:
                    required.append(m)
        self.assertEqual(required, [])


class TestOrchestratorControllerInstantiation(unittest.TestCase):
    """Verify the Orchestrator creates the correct controller class for each type string."""

    def _make_orchestrator_for_type(self, controller_type: str):
        """Build a minimal Orchestrator and call _configure_logic_modules directly."""
        from orchestrator import Orchestrator

        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.host = "127.0.0.1"
        orchestrator.port = 0
        orchestrator.logic_modules = []
        orchestrator._logic_module_names = []

        communication = {"ports": {"logic_module": 0}}
        setup = {"random_seed": 42, "traffic_lights": []}

        ctrl_section: dict[str, Any] = {"type": controller_type}
        if controller_type == "controller_fixed_cycle":
            ctrl_section["fixed_cycle"] = {
                "phase_durations": [10],
                "transition_duration": 2,
                "time_delays": {},
                "default_time_delay": 0,
            }
        elif controller_type == "controller_max_pressure":
            ctrl_section["max_pressure"] = {
                "bidding_strategy": "phase_queue_length",
                "min_green_duration": 5,
                "max_green_duration": 20,
                "auction_suspend_duration": 3,
                "transition_duration": 2,
            }
        elif controller_type == "controller_priority_pass":
            ctrl_section["priority_pass"] = {
                "bidding_strategy": "phase_queue_length",
                "min_green_duration": 5,
                "max_green_duration": 20,
                "auction_suspend_duration": 3,
                "transition_duration": 2,
                "trade_off": 0.5,
            }

        orchestrator._configure_logic_modules(communication, setup, [ctrl_section])
        return orchestrator.logic_modules[0]

    def test_fixed_cycle_instantiation(self) -> None:
        ctrl = self._make_orchestrator_for_type("controller_fixed_cycle")
        self.assertIsInstance(ctrl, FixedCycleController)

    def test_max_pressure_instantiation(self) -> None:
        ctrl = self._make_orchestrator_for_type("controller_max_pressure")
        self.assertIsInstance(ctrl, MaxPressureController)

    def test_priority_pass_instantiation(self) -> None:
        ctrl = self._make_orchestrator_for_type("controller_priority_pass")
        self.assertIsInstance(ctrl, PriorityPassController)

    def test_controller_receives_orchestrator_endpoint(self) -> None:
        ctrl = self._make_orchestrator_for_type("controller_priority_pass")
        assert isinstance(ctrl, PriorityPassController)
        # orchestrator endpoint is injected as ("127.0.0.1", 0) before configure()
        # it will be populated when configure() is called
        self.assertIsNotNone(ctrl.configuration.get("orchestrator"))


if __name__ == "__main__":
    unittest.main()
