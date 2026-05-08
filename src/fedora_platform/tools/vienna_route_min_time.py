"""Utility for estimating free-flow route times for the Vienna SUMO model.

This is a preparation helper, not part of the runtime pilot loop. It is kept in
``src`` so model folders remain data/configuration only.
"""

from __future__ import annotations

from pathlib import Path

import traci


def calculate_route_min_times(
    sumo_binary: str,
    sumo_config_file: str | Path,
) -> dict[str, float]:
    """Run each route once and return its minimum simulated travel time."""

    sumo_cmd = [
        sumo_binary,
        "-c",
        str(sumo_config_file),
        "--start",
        "--quit-on-end",
        "--time-to-teleport",
        "-1",
    ]

    traci.start(sumo_cmd, label="route_min_time_routes")
    routes = traci.route.getIDList()
    traci.close()

    durations: dict[str, float] = {}
    for route in routes:
        traci.start(sumo_cmd, label=f"route_min_time_{route}")
        traci.vehicle.add("v_id", route)
        traci.simulationStep()
        while traci.vehicle.getIDList():
            traci.simulationStep()
        durations[route] = traci.simulation.getTime()
        traci.close()

    return durations
