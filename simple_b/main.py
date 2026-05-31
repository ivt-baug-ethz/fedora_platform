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
from simulation import Simulation


config_path = Path(__file__).resolve().parent / "config.json"
with config_path.open("r", encoding="utf-8") as config_file:
    config = json.load(config_file)

controller_types = {
    "fixed_cycle": FixedCycleController,
    "max_pressure": MaxPressureController,
    "priority_pass": PriorityPassController,
}
controller_type = str(config["controller"].get("type", "priority_pass"))
controller_class = controller_types[controller_type]

recorder = Recorder(config["recorder"])
controller = controller_class(config["controller"])
connector = Connector(config["connector"])
simulation = Simulation(config["simulation"])
components = [recorder, controller, connector, simulation]
startup_pause_seconds = float(config.get("startup_pause_seconds", 0.2))

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
