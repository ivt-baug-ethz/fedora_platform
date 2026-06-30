"""Start the FEDORA platform via the Orchestrator.

The Orchestrator reads the configuration file and initialises all other components
(Recorder, LogicModule, Simulation).  run.py is intentionally thin: it only
handles CLI arguments, starts the Orchestrator, and runs the post-simulation
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
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from orchestrator import Orchestrator
from evaluator import Evaluator


def main() -> None:
    # default config; overridden by a positional CLI argument
    config_file = "configurations/demo_sumo_baseline_config.json"
    skip_evaluation = False

    for arg in sys.argv[1:]:
        if arg in ("--help", "-h"):
            # print usage info and exit immediately without running the simulation
            print("Usage: python run.py [CONFIG_FILE] [OPTIONS]")
            print("  CONFIG_FILE: Path to JSON config file")
            print("               (default: demo_sumo_priority_pass_config.json)")
            print("\nOptions:")
            print(
                "  --skip-evaluation: Skip evaluation and visualization after simulation"
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
        elif not arg.startswith("--"):
            config_file = arg

    # load the full platform configuration from JSON
    with Path(config_file).open("r", encoding="utf-8") as f:
        config = json.load(f)

    # extract names used for result directory paths and priority-plot visibility
    scenario = str(config["scenario"])
    logic_modules = list(config.get("logic_modules", []))
    logic_module_name = str(logic_modules[0]["type"]) if logic_modules else "baseline"
    show_priority = any(
        m.get("type") == "controller_priority_pass" for m in logic_modules
    )

    orchestrator = Orchestrator(config)

    try:
        orchestrator.start()
        orchestrator.wait_until_done()
        if not skip_evaluation:
            # resolve log and output directories, then run post-simulation analysis
            logs_dir = Path(config["recorder"]["logs_dir"])
            output_dir = Path("results") / scenario / logic_module_name
            try:
                evaluator = Evaluator(logs_dir, output_dir, show_priority=show_priority)
                evaluator.evaluate_and_report()
            except FileNotFoundError as error:
                print(f"Warning: Evaluation skipped - {error}")
    except KeyboardInterrupt:
        pass
    finally:
        # always stop the orchestrator so SUMO and sockets are released cleanly
        orchestrator.stop()


if __name__ == "__main__":
    main()
