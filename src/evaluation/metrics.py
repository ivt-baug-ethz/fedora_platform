"""Standard traffic-engineering metric computation for the FEDORA Platform."""

from __future__ import annotations

import statistics
from typing import Any


class MetricsComputer:  # pylint: disable=too-few-public-methods
    """Compute standard traffic-engineering metrics from completed vehicle records.

    All computation is pure (no I/O). Metrics that require data not present in the
    log (e.g. ``route_distance_m`` for VKT) emit ``None`` rather than raising.

    Args:
        vehicle_records: List of completed-vehicle dicts from ``VehicleLogLoader``.
        run_meta: The run_meta dict from ``VehicleLogLoader`` (may be empty).
    """

    def __init__(
        self,
        vehicle_records: list[dict[str, Any]],
        run_meta: dict[str, Any],
    ) -> None:
        """Initialise with parsed vehicle records and run metadata."""
        self.vehicle_records = vehicle_records
        self.run_meta = run_meta

    def compute(self, enabled_metrics: frozenset[str]) -> dict[str, Any]:
        """Compute all enabled metrics and return a flat result dict.

        Keys always present:
            ``total_vehicles``, ``vehicles_with_travel_time``

        Additional keys are present when the corresponding metric is enabled.
        Keys whose required data is absent are present but set to ``None``.

        Args:
            enabled_metrics: Set of metric names to compute.

        Returns:
            Dict mapping metric names to computed values (float, int, or None).
        """
        n = len(self.vehicle_records)
        result: dict[str, Any] = {
            "total_vehicles": n,
            "vehicles_with_travel_time": n,
        }

        if n == 0:
            return result

        travel_times = self._travel_times()

        if "travel_time" in enabled_metrics:
            result["overall_avg_travel_time"] = statistics.mean(travel_times)
            result["overall_median_travel_time"] = statistics.median(travel_times)
            result["overall_min_travel_time"] = min(travel_times)
            result["overall_max_travel_time"] = max(travel_times)

        if "travel_time_variance" in enabled_metrics:
            result["travel_time_variance"] = self._compute_variance(travel_times)

        if "vht" in enabled_metrics:
            result["vht"] = self._compute_vht(travel_times)

        vkt: float | None = None
        if "vkt" in enabled_metrics:
            vkt = self._compute_vkt()
            result["vkt"] = vkt
        elif "speed" in enabled_metrics or "density" in enabled_metrics:
            # vkt needed internally even if not a requested output
            vkt = self._compute_vkt()

        if "flow" in enabled_metrics:
            run_duration_s = self._run_duration_s()
            result["flow"] = (
                self._compute_flow(n, run_duration_s) if run_duration_s else None
            )

        if "speed" in enabled_metrics:
            vht = self._compute_vht(travel_times)
            result["space_mean_speed"] = self._compute_space_mean_speed(vkt, vht)

        if "density" in enabled_metrics:
            vht = self._compute_vht(travel_times)
            run_duration_s = self._run_duration_s()
            result["density"] = (
                self._compute_density(vht, run_duration_s) if run_duration_s else None
            )

        return result

    def _travel_times(self) -> list[float]:
        """Return list of travel times (departure - arrival) for all completed vehicles."""
        return [rec["departure"] - rec["arrival"] for rec in self.vehicle_records]

    def _run_duration_s(self) -> float | None:
        """Return run duration in seconds as the latest observed departure time."""
        if not self.vehicle_records:
            return None

        return max(rec["departure"] for rec in self.vehicle_records)

    def _compute_vht(self, travel_times: list[float]) -> float:
        """Vehicle Hours Traveled = sum of travel times converted to hours."""
        return sum(travel_times) / 3600.0

    def _compute_vkt(self) -> float | None:
        """Vehicle Kilometers Traveled = sum of route distances converted to km.

        Returns None when no vehicle records contain ``route_distance_m``.
        """
        distances = [
            rec["route_distance_m"]
            for rec in self.vehicle_records
            if rec.get("route_distance_m") is not None
        ]

        if not distances:
            return None

        return sum(distances) / 1000.0

    def _compute_flow(self, n: int, run_duration_s: float) -> float | None:
        """Aggregate flow in vehicles per hour."""
        if run_duration_s <= 0:
            return None

        return n / (run_duration_s / 3600.0)

    def _compute_space_mean_speed(self, vkt: float | None, vht: float) -> float | None:
        """Space mean speed in km/h = VKT / VHT."""
        if vkt is None or vht == 0:
            return None
        return vkt / vht

    def _compute_density(self, vht: float, run_duration_s: float) -> float | None:
        """Average network density in veh/km using the fundamental traffic relation.

        density = VHT / (run_duration_h × total_road_length_km)

        Returns None when ``total_lane_length_m`` is absent from run_meta.
        """
        total_lane_length_m = self.run_meta.get("total_lane_length_m")
        if total_lane_length_m is None:
            return None

        total_road_length_km = float(total_lane_length_m) / 1000.0
        run_duration_h = run_duration_s / 3600.0
        if total_road_length_km <= 0 or run_duration_h <= 0:
            return None

        return vht / (run_duration_h * total_road_length_km)

    def _compute_variance(self, values: list[float]) -> float | None:
        """Sample variance; returns None when fewer than 2 observations."""
        if len(values) < 2:
            return None

        return statistics.variance(values)
