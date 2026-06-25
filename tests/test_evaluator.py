"""Test the evaluator component."""

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

from evaluator import Evaluator


class TestEvaluator(unittest.TestCase):
    """Test evaluator functionality."""

    def test_load_and_evaluate_vehicle_log(self) -> None:
        """Test loading vehicle log and calculating delays."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            vehicle_log = tmpdir_path / "vehicle_log.jsonl"
            with vehicle_log.open("w") as f:
                f.write(
                    json.dumps(
                        {
                            "vehicle_id": "v_0",
                            "event_type": "arrival",
                            "time": 10.0,
                            "priority": 0,
                        }
                    )
                    + "\n"
                )
                f.write(
                    json.dumps(
                        {
                            "vehicle_id": "v_0",
                            "event_type": "departure",
                            "time": 15.0,
                            "priority": 0,
                        }
                    )
                    + "\n"
                )
                f.write(
                    json.dumps(
                        {
                            "vehicle_id": "v_1",
                            "event_type": "arrival",
                            "time": 11.0,
                            "priority": 1,
                        }
                    )
                    + "\n"
                )
                f.write(
                    json.dumps(
                        {
                            "vehicle_id": "v_1",
                            "event_type": "departure",
                            "time": 18.0,
                            "priority": 1,
                        }
                    )
                    + "\n"
                )
                f.write(
                    json.dumps(
                        {
                            "vehicle_id": "v_2",
                            "event_type": "arrival",
                            "time": 12.0,
                            "priority": 0,
                        }
                    )
                    + "\n"
                )
                f.write(
                    json.dumps(
                        {
                            "vehicle_id": "v_2",
                            "event_type": "departure",
                            "time": 20.0,
                            "priority": 0,
                        }
                    )
                    + "\n"
                )

            evaluator = Evaluator(tmpdir_path)
            evaluator.load_vehicle_log()
            evaluator.calculate_travel_times()
            stats = evaluator.get_statistics()

            self.assertEqual(stats["total_vehicles"], 3)
            self.assertEqual(stats["vehicles_with_travel_time"], 3)
            self.assertEqual(stats["regular_vehicles"], 2)
            self.assertEqual(stats["priority_vehicles"], 1)

            self.assertAlmostEqual(stats["overall_avg_travel_time"], 6.667, places=2)
            self.assertAlmostEqual(stats["regular_avg_travel_time"], 6.5, places=1)
            self.assertAlmostEqual(stats["priority_avg_travel_time"], 7.0, places=1)

    def test_plot_vehicle_counts_saves_file(self) -> None:
        """Test that plot_vehicle_counts creates a PNG at the specified path."""
        import matplotlib
        matplotlib.use("Agg")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            vehicle_log = tmpdir_path / "vehicle_log.jsonl"
            events = [
                {"vehicle_id": "v_0", "event_type": "arrival", "time": 10.0, "priority": 0},
                {"vehicle_id": "v_0", "event_type": "departure", "time": 15.0, "priority": 0},
                {"vehicle_id": "v_1", "event_type": "arrival", "time": 11.0, "priority": 1},
                {"vehicle_id": "v_1", "event_type": "departure", "time": 18.0, "priority": 1},
                {"vehicle_id": "v_2", "event_type": "arrival", "time": 12.0, "priority": 0},
                {"vehicle_id": "v_2", "event_type": "departure", "time": 20.0, "priority": 0},
            ]
            with vehicle_log.open("w") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")

            evaluator = Evaluator(tmpdir_path)
            evaluator.load_vehicle_log()
            evaluator.calculate_travel_times()

            out = tmpdir_path / "vehicle_counts.png"
            evaluator.plot_vehicle_counts(out)
            self.assertTrue(out.exists())

    def test_plot_vehicle_counts_series_values(self) -> None:
        """Test cumulative count series logic directly without file I/O."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            vehicle_log = tmpdir_path / "vehicle_log.jsonl"
            # v_0 departs at 15 (regular), v_1 at 18 (priority), v_2 at 20 (regular)
            events = [
                {"vehicle_id": "v_0", "event_type": "arrival", "time": 10.0, "priority": 0},
                {"vehicle_id": "v_0", "event_type": "departure", "time": 15.0, "priority": 0},
                {"vehicle_id": "v_1", "event_type": "arrival", "time": 11.0, "priority": 1},
                {"vehicle_id": "v_1", "event_type": "departure", "time": 18.0, "priority": 1},
                {"vehicle_id": "v_2", "event_type": "arrival", "time": 12.0, "priority": 0},
                {"vehicle_id": "v_2", "event_type": "departure", "time": 20.0, "priority": 0},
                # v_3 has no departure — must not appear in counts
                {"vehicle_id": "v_3", "event_type": "arrival", "time": 5.0, "priority": 0},
            ]
            with vehicle_log.open("w") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")

            evaluator = Evaluator(tmpdir_path)
            evaluator.load_vehicle_log()
            evaluator.calculate_travel_times()

            # replicate the series-building logic from plot_vehicle_counts
            sorted_vehicles = sorted(
                (
                    (vid, d)
                    for vid, d in evaluator.vehicle_data.items()
                    if d["arrival"] is not None and d["departure"] is not None
                ),
                key=lambda x: x[1]["departure"],
            )

            count_r, count_p = 0, 0
            totals: list[int] = []
            for _, data in sorted_vehicles:
                if data["priority"] == 1:
                    count_p += 1
                else:
                    count_r += 1
                totals.append(count_r + count_p)

            # after all 3 completed vehicles: 2 regular + 1 priority = 3 total
            self.assertEqual(len(totals), 3)
            self.assertEqual(totals[-1], 3)
            self.assertEqual(count_r, 2)
            self.assertEqual(count_p, 1)


if __name__ == "__main__":
    unittest.main()
