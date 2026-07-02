"""Vehicle log loader for the FEDORA Platform evaluation package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class VehicleLogLoader:  # pylint: disable=too-few-public-methods
    """Parse a ``vehicle_log.jsonl`` file into structured per-vehicle records.

    The loader reads arrival and departure events, pairs them by vehicle ID, and
    returns only vehicles that completed their trip (both timestamps present).
    Vehicles still in the network at the end of the run are excluded.
    """

    def __init__(self, log_path: Path) -> None:
        """Initialise the loader for a given log file path.

        Args:
            log_path: Path to the ``vehicle_log.jsonl`` file to parse.
        """
        self.log_path = log_path

    def load(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Read the log file and return parsed run metadata and vehicle records.

        Returns:
            A tuple of ``(run_meta, vehicle_records)`` where:

            - ``run_meta`` is the dict from the first ``run_meta`` line, or ``{}``
              if none is present.
            - ``vehicle_records`` is a list of dicts, one per completed vehicle,
              with keys ``vehicle_id`` (str), ``arrival`` (float), ``departure``
              (float), ``priority`` (int), and ``route_distance_m`` (float | None).

        Raises:
            FileNotFoundError: If ``log_path`` does not exist.
        """
        if not self.log_path.exists():
            raise FileNotFoundError(f"Vehicle log not found: {self.log_path}")

        run_meta: dict[str, Any] = {}
        raw: dict[str, dict[str, Any]] = {}

        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event: dict[str, Any] = json.loads(line)

                if event.get("type") == "run_meta":
                    run_meta = event
                    continue

                vehicle_id: str = event["vehicle_id"]
                if vehicle_id not in raw:
                    raw[vehicle_id] = {
                        "vehicle_id": vehicle_id,
                        "priority": int(event.get("priority", 0)),
                        "arrival": None,
                        "departure": None,
                        "route_distance_m": None,
                    }

                event_type: str = event["event_type"]
                if event_type == "arrival":
                    raw[vehicle_id]["arrival"] = float(event["time"])
                elif event_type == "departure":
                    raw[vehicle_id]["departure"] = float(event["time"])
                    dist = event.get("route_distance_m")
                    if dist is not None:
                        raw[vehicle_id]["route_distance_m"] = float(dist)

        # keep only vehicles with both timestamps (trip completed)
        vehicle_records = [
            rec
            for rec in raw.values()
            if rec["arrival"] is not None and rec["departure"] is not None
        ]
        return run_meta, vehicle_records
