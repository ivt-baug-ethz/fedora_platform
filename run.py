"""Load configuration and launch the TCP FSM components.

Examples:
    python run.py
    python run.py configurations/demo_sumo_fixed_cycle_config.json
    python run.py configurations/demo_sumo_max_pressure_config.json
    python run.py configurations/demo_sumo_priority_pass_config.json
    python run.py configurations/vienna_sumo_fixed_cycle_config.json
    python run.py configurations/vienna_sumo_max_pressure_config.json
    python run.py configurations/vienna_sumo_priority_pass_config.json
    python run.py configurations/demo_sumo_priority_pass_config.json --skip-evaluation
"""

from __future__ import annotations

import sys
import json
import time
from pathlib import Path

from connector import Connector
from controller_fixed_cycle import FixedCycleController
from controller_max_pressure import MaxPressureController
from controller_priority_pass import PriorityPassController
from recorder import Recorder
from simulation_sumo import Simulation
from evaluator import Evaluator


def with_endpoint(
    configuration: dict,
    component_name: str,
    communication: dict,
) -> dict:
    """Return component config enriched with host/port and connector endpoint."""
    host = str(communication.get("host", "127.0.0.1"))
    ports = dict(communication["ports"])
    enriched = dict(configuration)
    enriched["host"] = host
    enriched["port"] = int(ports[component_name])
    if component_name != "connector":
        enriched["connector"] = {
            "host": host,
            "port": int(ports["connector"]),
        }
    return enriched


def build_connector_configuration(communication: dict) -> dict:
    """Build connector config from one central communication block."""
    host = str(communication.get("host", "127.0.0.1"))
    ports = dict(communication["ports"])
    return {
        "host": host,
        "port": int(ports["connector"]),
        "socket_timeout": float(communication.get("socket_timeout", 2.0)),
        "components": {
            name: {
                "host": host,
                "port": int(port),
            }
            for name, port in ports.items()
            if name != "connector"
        },
    }


def main() -> None:
    # parse command-line arguments
    config_file = "configurations/demo_sumo_priority_pass_config.json"
    skip_evaluation = False

    for arg in sys.argv[1:]:
        if arg in ("--help", "-h"):
            print("Usage: python run.py [CONFIG_FILE] [OPTIONS]")
            print("  CONFIG_FILE: Path to JSON config file")
            print("               (default: demo_sumo_priority_pass_config.json)")
            print("\nOptions:")
            print("  --skip-evaluation: Skip evaluation and visualization after simulation")
            print("\nAvailable demo configs:")
            print("  - configurations/demo_sumo_fixed_cycle_config.json")
            print("  - configurations/demo_sumo_max_pressure_config.json")
            print("  - configurations/demo_sumo_priority_pass_config.json")
            print("\nAvailable Vienna pilot configs:")
            print("  - configurations/vienna_sumo_fixed_cycle_config.json")
            print("  - configurations/vienna_sumo_max_pressure_config.json")
            print("  - configurations/vienna_sumo_priority_pass_config.json")
            sys.exit(0)
        elif arg == "--skip-evaluation":
            skip_evaluation = True
        elif not arg.startswith("--"):
            config_file = arg

    # load the configuration file
    with Path(config_file).open("r", encoding="utf-8") as f:
        config = json.load(f)

    communication = dict(config["communication"])
    setup = dict(config.get("setup", {}))
    random_seed = int(setup.get("random_seed", 42))
    traffic_lights = list(setup.get("traffic_lights", []))
    controller_types = {
        "fixed_cycle": FixedCycleController,
        "max_pressure": MaxPressureController,
        "priority_pass": PriorityPassController,
    }
    controller_type = str(config["controller"].get("type", "priority_pass"))
    controller_class = controller_types[controller_type]

    # Extract scenario and controller info for evaluation output directory
    config_path = Path(config_file)
    config_stem = config_path.stem
    scenario_parts = config_stem.split("_sumo_")
    scenario = scenario_parts[0] if scenario_parts else "unknown"
    controller_name = scenario_parts[1] if len(scenario_parts) > 1 else controller_type

    recorder_config = with_endpoint(config["recorder"], "recorder", communication)
    recorder = Recorder(recorder_config)
    controller_configuration = with_endpoint(
        config["controller"],
        "controller",
        communication,
    )
    controller_configuration["random_seed"] = random_seed
    controller_configuration["traffic_lights"] = traffic_lights
    controller = controller_class(controller_configuration)
    connector = Connector(build_connector_configuration(communication))
    simulation_configuration = with_endpoint(
        config["simulation"],
        "simulation",
        communication,
    )
    simulation_configuration["setup"] = setup
    simulation_configuration["network"] = {
        "traffic_lights": traffic_lights,
    }
    simulation_configuration["controller_response_timeout_seconds"] = float(
        setup.get("controller_response_timeout_seconds", 0.05)
    )
    simulation_configuration["sumo_details"] = dict(
        simulation_configuration["sumo_details"]
    )
    simulation_configuration["sumo_details"]["random_seed"] = random_seed
    simulation_configuration["logs_dir"] = str(recorder_config["logs_dir"])
    simulation = Simulation(
        simulation_configuration, scenario_path=Path(config["scenario_path"])
    )
    components = [recorder, controller, connector, simulation]
    startup_pause_seconds = float(setup.get("startup_pause_seconds", 0.2))

    try:
        for component in components:
            component.start()
            time.sleep(startup_pause_seconds)
        simulation.wait_until_done()

        # Run evaluation after simulation completes
        if not skip_evaluation:
            logs_dir = Path(config["recorder"]["logs_dir"])
            output_dir = Path("results") / scenario / controller_name
            try:
                evaluator = Evaluator(logs_dir, output_dir)
                evaluator.evaluate_and_report()
            except FileNotFoundError as error:
                print(f"Warning: Evaluation skipped - {error}")
    except KeyboardInterrupt:
        simulation.stop()
    finally:
        for component in reversed(components):
            component.stop()


if __name__ == "__main__":
    main()
