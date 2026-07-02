"""Unit tests for MetricsComputer."""

from __future__ import annotations

import statistics
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evaluation.config import ALL_METRICS
from evaluation.metrics import MetricsComputer


def _records(
    travel_times: list[float],
    distances: list[float | None] | None = None,
) -> list[dict]:
    """Build minimal vehicle records for a given list of travel times."""
    if distances is None:
        distances = [None] * len(travel_times)
    records = []
    for i, (tt, dist) in enumerate(zip(travel_times, distances)):
        records.append(
            {
                "vehicle_id": f"v_{i}",
                "arrival": 10.0,
                "departure": 10.0 + tt,
                "priority": 0,
                "route_distance_m": dist,
            }
        )
    return records


class TestMetricsComputer(unittest.TestCase):
    """Test MetricsComputer.compute() for each standard metric."""

    def _compute(
        self,
        travel_times: list[float],
        distances: list[float | None] | None = None,
        run_meta: dict | None = None,
        metrics: frozenset[str] | None = None,
    ) -> dict:
        recs = _records(travel_times, distances)
        meta = run_meta or {}
        enabled = metrics if metrics is not None else ALL_METRICS
        return MetricsComputer(recs, meta).compute(enabled)

    def test_vht_computation(self) -> None:
        """VHT = sum of travel times / 3600."""
        result = self._compute([5.0, 7.0, 8.0])
        expected = (5.0 + 7.0 + 8.0) / 3600.0
        self.assertAlmostEqual(result["vht"], expected, places=8)

    def test_flow_computation(self) -> None:
        """Flow = n / (max_departure / 3600)."""
        result = self._compute([5.0, 7.0, 8.0])
        # max departure = 10 + 8 = 18; flow = 3 / (18/3600)
        expected = 3.0 / (18.0 / 3600.0)
        self.assertAlmostEqual(result["flow"], expected, places=4)

    def test_travel_time_variance_computation(self) -> None:
        """Travel time variance = statistics.variance of travel times."""
        result = self._compute([5.0, 7.0, 8.0])
        expected = statistics.variance([5.0, 7.0, 8.0])
        self.assertAlmostEqual(result["travel_time_variance"], expected, places=6)

    def test_vkt_none_when_no_distances(self) -> None:
        """VKT is None when no departure events include route_distance_m."""
        result = self._compute([5.0, 7.0])
        self.assertIsNone(result["vkt"])

    def test_vkt_with_distances(self) -> None:
        """VKT = sum of route distances / 1000."""
        result = self._compute([5.0, 7.0], distances=[1000.0, 2000.0])
        self.assertAlmostEqual(result["vkt"], 3.0, places=6)

    def test_space_mean_speed_none_when_vkt_none(self) -> None:
        """Space mean speed is None when VKT cannot be computed."""
        result = self._compute([5.0, 7.0])
        self.assertIsNone(result["space_mean_speed"])

    def test_space_mean_speed_with_vkt(self) -> None:
        """Space mean speed = VKT / VHT in km/h."""
        # VKT = 3 km, VHT = 20/3600 h → speed = 3 / (20/3600) = 540 km/h
        result = self._compute([10.0, 10.0], distances=[1500.0, 1500.0])
        vkt = 3.0
        vht = 20.0 / 3600.0
        self.assertAlmostEqual(result["space_mean_speed"], vkt / vht, places=4)

    def test_density_none_when_no_total_lane_length(self) -> None:
        """Density is None when total_lane_length_m is absent from run_meta."""
        result = self._compute([5.0, 7.0])
        self.assertIsNone(result["density"])

    def test_density_computation(self) -> None:
        """Density = VHT / (sim_duration_h × total_road_length_km)."""
        # v_0: arrival=0, departure=3600 → travel_time=3600s=1h
        # v_1: arrival=1800, departure=7200 → travel_time=5400s=1.5h
        # VHT = (3600 + 5400) / 3600 = 2.5h
        # sim_duration_h = max(departure) / 3600 = 7200 / 3600 = 2h
        # total_road_length_km = 10000 / 1000 = 10 km
        # density = 2.5 / (2 * 10) = 0.125 veh/km
        recs = [
            {
                "vehicle_id": "v_0",
                "arrival": 0.0,
                "departure": 3600.0,
                "priority": 0,
                "route_distance_m": None,
            },
            {
                "vehicle_id": "v_1",
                "arrival": 1800.0,
                "departure": 7200.0,
                "priority": 0,
                "route_distance_m": None,
            },
        ]
        meta = {"total_lane_length_m": 10000.0}
        result = MetricsComputer(recs, meta).compute(ALL_METRICS)
        self.assertAlmostEqual(result["density"], 0.125, places=6)

    def test_metric_allowlist_filters(self) -> None:
        """Only requested metrics appear in the result (plus always-present counts)."""
        result = self._compute([5.0, 7.0], metrics=frozenset({"vht"}))
        self.assertIn("vht", result)
        self.assertNotIn("vkt", result)
        self.assertNotIn("flow", result)
        self.assertIn("total_vehicles", result)
        self.assertIn("vehicles_with_travel_time", result)

    def test_single_vehicle_no_variance(self) -> None:
        """Variance metrics return None when only one vehicle is present."""
        result = self._compute([5.0])
        self.assertIsNone(result["travel_time_variance"])

    def test_no_vehicles_returns_counts_only(self) -> None:
        """Empty record list returns zeros for counts without raising."""
        result = MetricsComputer([], {}).compute(ALL_METRICS)
        self.assertEqual(result["total_vehicles"], 0)
        self.assertEqual(result["vehicles_with_travel_time"], 0)
        self.assertNotIn("overall_avg_travel_time", result)


if __name__ == "__main__":
    unittest.main()
