"""Unit tests for VehicleLogLoader."""

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

from evaluation.loader import VehicleLogLoader


def _write_log(path: Path, lines: list[dict]) -> None:
    """Write JSONL lines to a log file."""
    with path.open("w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


class TestVehicleLogLoader(unittest.TestCase):
    """Test VehicleLogLoader.load() under various log formats."""

    def test_load_basic_events(self) -> None:
        """Arrival + departure for one vehicle returns one completed record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "vehicle_log.jsonl"
            _write_log(
                log_path,
                [
                    {
                        "vehicle_id": "v_0",
                        "event_type": "arrival",
                        "time": 5.0,
                        "priority": 0,
                    },
                    {
                        "vehicle_id": "v_0",
                        "event_type": "departure",
                        "time": 10.0,
                        "priority": 0,
                    },
                ],
            )
            _, records = VehicleLogLoader(log_path).load()

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["vehicle_id"], "v_0")
            self.assertAlmostEqual(records[0]["arrival"], 5.0)
            self.assertAlmostEqual(records[0]["departure"], 10.0)
            self.assertEqual(records[0]["priority"], 0)

    def test_load_run_meta_skipped(self) -> None:
        """run_meta lines are not returned as vehicle records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "vehicle_log.jsonl"
            _write_log(
                log_path,
                [
                    {"type": "run_meta", "scenario": "demo", "traffic_lights": []},
                    {
                        "vehicle_id": "v_0",
                        "event_type": "arrival",
                        "time": 1.0,
                        "priority": 0,
                    },
                    {
                        "vehicle_id": "v_0",
                        "event_type": "departure",
                        "time": 3.0,
                        "priority": 0,
                    },
                ],
            )
            run_meta, records = VehicleLogLoader(log_path).load()

            self.assertEqual(run_meta.get("type"), "run_meta")
            self.assertEqual(len(records), 1)

    def test_load_vehicle_never_departed(self) -> None:
        """A vehicle with only an arrival event is excluded from records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "vehicle_log.jsonl"
            _write_log(
                log_path,
                [
                    {
                        "vehicle_id": "v_0",
                        "event_type": "arrival",
                        "time": 5.0,
                        "priority": 0,
                    },
                    {
                        "vehicle_id": "v_0",
                        "event_type": "departure",
                        "time": 10.0,
                        "priority": 0,
                    },
                    {
                        "vehicle_id": "v_1",
                        "event_type": "arrival",
                        "time": 7.0,
                        "priority": 0,
                    },
                    # v_1 never departs
                ],
            )
            _, records = VehicleLogLoader(log_path).load()

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["vehicle_id"], "v_0")

    def test_load_route_distance_m_present(self) -> None:
        """A departure event with route_distance_m populates the field in the record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "vehicle_log.jsonl"
            _write_log(
                log_path,
                [
                    {
                        "vehicle_id": "v_0",
                        "event_type": "arrival",
                        "time": 1.0,
                        "priority": 0,
                    },
                    {
                        "vehicle_id": "v_0",
                        "event_type": "departure",
                        "time": 5.0,
                        "priority": 0,
                        "route_distance_m": 850.5,
                    },
                ],
            )
            _, records = VehicleLogLoader(log_path).load()

            self.assertEqual(len(records), 1)
            self.assertAlmostEqual(records[0]["route_distance_m"], 850.5)

    def test_load_route_distance_m_absent(self) -> None:
        """A departure event without route_distance_m yields None in the record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "vehicle_log.jsonl"
            _write_log(
                log_path,
                [
                    {
                        "vehicle_id": "v_0",
                        "event_type": "arrival",
                        "time": 1.0,
                        "priority": 0,
                    },
                    {
                        "vehicle_id": "v_0",
                        "event_type": "departure",
                        "time": 5.0,
                        "priority": 0,
                    },
                ],
            )
            _, records = VehicleLogLoader(log_path).load()

            self.assertIsNone(records[0]["route_distance_m"])

    def test_load_total_lane_length_m_in_meta(self) -> None:
        """run_meta with total_lane_length_m is returned in the metadata dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "vehicle_log.jsonl"
            _write_log(
                log_path,
                [
                    {
                        "type": "run_meta",
                        "scenario": "demo",
                        "total_lane_length_m": 5000.0,
                    },
                    {
                        "vehicle_id": "v_0",
                        "event_type": "arrival",
                        "time": 1.0,
                        "priority": 0,
                    },
                    {
                        "vehicle_id": "v_0",
                        "event_type": "departure",
                        "time": 3.0,
                        "priority": 0,
                    },
                ],
            )
            run_meta, _ = VehicleLogLoader(log_path).load()

            self.assertAlmostEqual(run_meta["total_lane_length_m"], 5000.0)

    def test_load_file_not_found(self) -> None:
        """FileNotFoundError is raised when the log file does not exist."""
        loader = VehicleLogLoader(Path("/nonexistent/vehicle_log.jsonl"))
        with self.assertRaises(FileNotFoundError):
            loader.load()


if __name__ == "__main__":
    unittest.main()
