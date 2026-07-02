"""Test the standard evaluator (src/evaluation package)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evaluation import Evaluator
from evaluation.plots import PlotGenerator


def _write_vehicle_log(path: Path, events: list[dict]) -> None:
    """Write a vehicle_log.jsonl fixture with a run_meta header."""
    with path.open("w") as f:
        run_meta = {"type": "run_meta", "scenario": "test", "traffic_lights": []}
        f.write(json.dumps(run_meta) + "\n")
        for e in events:
            f.write(json.dumps(e) + "\n")


_EVENTS_3 = [
    {"vehicle_id": "v_0", "event_type": "arrival", "time": 10.0, "priority": 0},
    {"vehicle_id": "v_0", "event_type": "departure", "time": 15.0, "priority": 0},
    {"vehicle_id": "v_1", "event_type": "arrival", "time": 11.0, "priority": 1},
    {"vehicle_id": "v_1", "event_type": "departure", "time": 18.0, "priority": 1},
    {"vehicle_id": "v_2", "event_type": "arrival", "time": 12.0, "priority": 0},
    {"vehicle_id": "v_2", "event_type": "departure", "time": 20.0, "priority": 0},
]


class TestEvaluator(unittest.TestCase):
    """Test standard evaluator end-to-end pipeline."""

    def test_load_and_evaluate_vehicle_log(self) -> None:
        """evaluate_and_report() returns correct aggregate travel-time stats."""
        import matplotlib

        matplotlib.use("Agg")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            _write_vehicle_log(tmpdir_path / "vehicle_log.jsonl", _EVENTS_3)

            output_dir = tmpdir_path / "results"
            stats = Evaluator(tmpdir_path, output_dir).evaluate_and_report()

            self.assertEqual(stats["total_vehicles"], 3)
            self.assertEqual(stats["vehicles_with_travel_time"], 3)
            # travel times: v_0=5, v_1=7, v_2=8 → mean ≈ 6.667
            self.assertAlmostEqual(stats["overall_avg_travel_time"], 6.667, places=2)
            self.assertAlmostEqual(stats["overall_min_travel_time"], 5.0, places=1)
            self.assertAlmostEqual(stats["overall_max_travel_time"], 8.0, places=1)
            # standard metrics also present
            self.assertIn("vht", stats)
            self.assertIn("flow", stats)
            # evaluation_stats.json written to output_dir
            self.assertTrue((output_dir / "evaluation_stats.json").exists())

    def test_plot_vehicle_counts_saves_file(self) -> None:
        """evaluate_and_report() creates vehicle_counts.png in the output directory."""
        import matplotlib

        matplotlib.use("Agg")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            _write_vehicle_log(tmpdir_path / "vehicle_log.jsonl", _EVENTS_3)

            output_dir = tmpdir_path / "results"
            Evaluator(tmpdir_path, output_dir).evaluate_and_report()

            self.assertTrue((output_dir / "vehicle_counts.png").exists())

    def test_plot_vehicle_counts_series_values(self) -> None:
        """PlotGenerator.plot_vehicle_counts() sorts by departure and writes PNG."""
        import matplotlib

        matplotlib.use("Agg")

        vehicle_records = [
            {
                "vehicle_id": "v_0",
                "arrival": 10.0,
                "departure": 15.0,
                "priority": 0,
                "route_distance_m": None,
            },
            {
                "vehicle_id": "v_1",
                "arrival": 11.0,
                "departure": 18.0,
                "priority": 1,
                "route_distance_m": None,
            },
            {
                "vehicle_id": "v_2",
                "arrival": 12.0,
                "departure": 20.0,
                "priority": 0,
                "route_distance_m": None,
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "counts.png"
            PlotGenerator(vehicle_records).plot_vehicle_counts(out)
            self.assertTrue(out.exists())

        # verify sort order: 3 vehicles, last departure at t=20
        sorted_records = sorted(vehicle_records, key=lambda r: r["departure"])
        self.assertEqual(len(sorted_records), 3)
        self.assertEqual(sorted_records[-1]["departure"], 20.0)
        self.assertEqual(sorted_records[0]["departure"], 15.0)


if __name__ == "__main__":
    unittest.main()
