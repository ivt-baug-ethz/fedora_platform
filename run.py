"""Load simple_b configuration and launch the TCP FSM components."""

from __future__ import annotations

import json
import time
from pathlib import Path

from connector import Connector
from controller_fixed_cycle import FixedCycleController
from controller_max_pressure import MaxPressureController
from controller_priority_pass import PriorityPassController
from recorder import Recorder
from simulation_sumo import Simulation


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
    # TODO: add headless option through CLI
    # TODO: add visualization option through CLI

    # load the configuration file
    # TODO: replace this through CLI argument
    config_file = "configurations/sumo_priority_pass_demo_config.json"
    with Path(config_file).open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

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

    recorder = Recorder(with_endpoint(config["recorder"], "recorder", communication))
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
    except KeyboardInterrupt:
        simulation.stop()
    finally:
        for component in reversed(components):
            component.stop()


if __name__ == "__main__":
    main()
