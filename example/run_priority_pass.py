"""Run or dry-run the FEDORA Priority Pass pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fedora_platform.communication import InMemoryMessageBus
from fedora_platform.priority_pass import (  # noqa: E402
    DEFAULT_VIENNA_INTERSECTIONS,
    MicroscopicTrafficSumoSimulator,
    PriorityPassConfig,
    PriorityPassControlParameters,
    PriorityPassTrafficOptimizer,
    ViennaPilot,
)
from fedora_platform.storage import SQLiteInteractionStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run SUMO to completion.")
    parser.add_argument("--sumo-binary", default=None, help="SUMO executable path.")
    parser.add_argument(
        "--sqlite-path",
        default="fedora_interactions.sqlite3",
        help="Local SQLite file used to store records and message interactions.",
    )
    parser.add_argument("--gui", action="store_true", help="Use SUMO GUI binary.")
    parser.add_argument("--flow", type=int, default=200, help="Traffic flow in veh/h.")
    parser.add_argument("--tau", type=float, default=0.4, help="Priority trade-off.")
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.2,
        help="Share of vehicles eligible for Priority Pass.",
    )
    args = parser.parse_args()

    storage = SQLiteInteractionStore(args.sqlite_path)
    bus = InMemoryMessageBus(interaction_store=storage)
    control = PriorityPassControlParameters(tau=args.tau)
    config = PriorityPassConfig(
        flow_vehicles_per_hour=args.flow,
        gamma_priority_share=args.gamma,
        sumo_binary=args.sumo_binary,
        use_gui=args.gui,
    )
    optimizer = PriorityPassTrafficOptimizer(control, bus=bus)
    simulator = MicroscopicTrafficSumoSimulator(config, bus=bus)
    pilot = ViennaPilot(optimizer, simulator, storage, bus=bus)

    if not args.run:
        optimizer.configure()
        optimization = optimizer.optimize(
            {"intersections": DEFAULT_VIENNA_INTERSECTIONS}
        )
        simulator.configure({"tl_control": optimization["tl_control"]})
        pilot.configure()
        pilot.accept_traffic_light_control(optimization["tl_control"])
        preview = {
            "mode": "dry_run",
            "simulator_state": simulator.state.value,
            "pilot_sensor_snapshot": pilot.provide_sensor_data(),
            "sumo_binary": simulator.settings.sumo_location,
            "sumo_config_file": simulator.settings.sumo_config_file,
            "intersections": list(simulator.settings.tl_control.keys()),
            "sample_controller": simulator.settings.tl_control["J25"],
        }
        print(json.dumps(preview, indent=2))
        return 0

    results = pilot.run()
    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
