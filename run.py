"""Start the FEDORA platform via the Orchestrator.

The Orchestrator reads the configuration file and initialises all other components
(Recorder, LogicModule, Environment).  run.py is intentionally thin: it only
handles CLI arguments, starts the Orchestrator, and runs the post-run
Evaluator.

Examples:
    python run.py
    python run.py configurations/demo_sumo_baseline_config.json
    python run.py configurations/demo_sumo_fixed_cycle_config.json
    python run.py configurations/demo_sumo_max_pressure_config.json
    python run.py configurations/demo_sumo_priority_pass_config.json
    python run.py configurations/demo_sumo_priority_pass_full_state_config.json
    python run.py configurations/vienna_sumo_baseline_config.json
    python run.py configurations/vienna_sumo_fixed_cycle_config.json
    python run.py configurations/vienna_sumo_max_pressure_config.json
    python run.py configurations/vienna_sumo_priority_pass_config.json
    python run.py configurations/demo_sumo_priority_pass_config.json --skip-evaluation
    python run.py configurations/demo_sumo_priority_pass_config.json --headless
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from orchestrator import Orchestrator
from evaluation import Evaluator
from evaluation.config import EvaluationConfig


def main() -> None:
    # default config; overridden by a positional CLI argument
    config_file = "configurations/demo_sumo_baseline_config.json"
    skip_evaluation = False
    headless = False

    for arg in sys.argv[1:]:
        if arg in ("--help", "-h"):
            # print usage info and exit immediately without running the platform
            print("Usage: python run.py [CONFIG_FILE] [OPTIONS]")
            print("  CONFIG_FILE: Path to JSON config file")
            print("               (default: demo_sumo_priority_pass_config.json)")
            print("\nOptions:")
            print(
                "  --skip-evaluation: Skip evaluation after the run"
                " (overrides evaluation.enabled in config)"
            )
            print(
                "  --headless:        Use headless SUMO binary (binary_headless from config)"
                " instead of sumo-gui; required for CI and server environments"
            )
            print("\nAvailable demo configs:")
            print(
                "  - configurations/demo_sumo_baseline_config.json (no controller — SUMO defaults)"
            )
            print(
                "  - configurations/demo_sumo_fixed_cycle_config.json (configurable fixed-cycle)"
            )
            print("  - configurations/demo_sumo_max_pressure_config.json")
            print("  - configurations/demo_sumo_priority_pass_config.json")
            print(
                "  - configurations/demo_sumo_priority_pass_full_state_config.json"
                " (all state fields logged — for debugging / validation)"
            )
            print("\nAvailable Vienna pilot configs:")
            print(
                "  - configurations/vienna_sumo_baseline_config.json (no controller — SUMO defaults)"
            )
            print(
                "  - configurations/vienna_sumo_fixed_cycle_config.json (configurable fixed-cycle)"
            )
            print("  - configurations/vienna_sumo_max_pressure_config.json")
            print("  - configurations/vienna_sumo_priority_pass_config.json")
            sys.exit(0)
        elif arg == "--skip-evaluation":
            skip_evaluation = True
        elif arg == "--headless":
            headless = True
        elif not arg.startswith("--"):
            config_file = arg

    # load the full platform configuration from JSON
    with Path(config_file).open("r", encoding="utf-8") as f:
        config = json.load(f)

    # override SUMO binary with the headless variant when --headless is passed
    if headless:
        settings = config["environment"]["settings"]
        settings["binary"] = settings.get("binary_headless", "sumo")

    # extract names used for result directory paths
    scenario = str(config["scenario"])
    logic_modules = list(config.get("logic_modules", []))
    logic_module_name = str(logic_modules[0]["type"]) if logic_modules else "baseline"

    # determine whether evaluation should run:
    # --skip-evaluation CLI flag always overrides the config setting
    eval_cfg_dict: dict[str, Any] = config.get("evaluation", {})
    config_enabled = bool(eval_cfg_dict.get("enabled", True))
    run_evaluation = not skip_evaluation and config_enabled

    orchestrator = Orchestrator(config)

    try:
        orchestrator.start()
        orchestrator.wait_until_done()
        if run_evaluation:
            logs_dir = Path(config["recorder"]["logs_dir"])
            output_dir = Path("results") / scenario / logic_module_name
            try:
                eval_config = EvaluationConfig.from_dict(eval_cfg_dict)
                evaluator = Evaluator(logs_dir, output_dir, eval_config)
                evaluator.evaluate_and_report()
            except FileNotFoundError as error:
                print(f"Warning: Evaluation skipped — {error}")
            except ValueError as error:
                print(f"Warning: Invalid evaluation config — {error}")
    except KeyboardInterrupt:
        pass
    finally:
        # always stop the orchestrator so the environment and sockets are released cleanly
        orchestrator.stop()


if __name__ == "__main__":
    main()
