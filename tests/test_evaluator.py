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


if __name__ == "__main__":
    unittest.main()
