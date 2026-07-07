"""Unit tests for the Recorder component."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from recorder import Recorder


class TestRecorderFSM(unittest.TestCase):
    """FSM lifecycle and state transitions for Recorder."""

    def _make_recorder(self, tmpdir: str) -> Recorder:
        return Recorder({"port": 0, "logs_dir": tmpdir, "log_type": "txt"})

    def test_initial_state_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            self.assertEqual(rec.state, Recorder.STATE_CREATED)

    def test_configure_transitions_to_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            rec.configure()
            self.assertEqual(rec.state, Recorder.STATE_CONFIGURED)

    def test_configure_sets_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            rec.configure()
            self.assertEqual(rec.log_path, Path(tmpdir) / "communication_log.txt")

    def test_configure_creates_logs_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = str(Path(tmpdir) / "subdir" / "logs")
            rec = Recorder({"port": 0, "logs_dir": nested, "log_type": "txt"})
            rec.configure()
            self.assertTrue(Path(nested).exists())

    def test_stop_from_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            rec.stop()
            self.assertEqual(rec.state, Recorder.STATE_STOPPED)

    def test_stop_from_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            rec.configure()
            rec.stop()
            self.assertEqual(rec.state, Recorder.STATE_STOPPED)

    def test_stop_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            rec.stop()
            rec.stop()  # should not raise
            self.assertEqual(rec.state, Recorder.STATE_STOPPED)

    def test_fail_transitions_to_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            rec.fail("disk full")
            self.assertEqual(rec.state, Recorder.STATE_FAILED)
            self.assertEqual(rec.last_error, "disk full")

    def test_invalid_transition_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = self._make_recorder(tmpdir)
            with self.assertRaises(RuntimeError):
                rec._transition("start")  # cannot start from CREATED

    def test_unsupported_log_type_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder({"port": 0, "logs_dir": tmpdir, "log_type": "sqlite"})
            with self.assertRaises(ValueError):
                rec.configure()

    def test_missing_logs_dir_raises(self) -> None:
        rec = Recorder({"port": 0, "log_type": "txt"})
        with self.assertRaises(ValueError):
            rec.configure()


class TestRecorderCommunication(unittest.TestCase):
    """End-to-end TCP communication and log file writing for Recorder."""

    def test_start_and_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder({"port": 0, "logs_dir": tmpdir, "log_type": "txt"})
            rec.start()
            self.assertEqual(rec.state, Recorder.STATE_RUNNING)
            rec.stop()
            self.assertEqual(rec.state, Recorder.STATE_STOPPED)

    def test_records_message_via_tcp(self) -> None:
        """Send a JSON-line message over TCP and verify it appears in the log file."""
        import socket as sock_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder({"port": 0, "logs_dir": tmpdir, "log_type": "txt"})
            rec.start()

            # Discover the port the recorder bound to
            assert rec.server_socket is not None
            actual_port = rec.server_socket.getsockname()[1]

            message = {
                "sender": "test",
                "target": "recorder",
                "topic": "communication",
                "sent_at": time.time(),
                "payload": {"data": "hello"},
            }
            encoded = json.dumps(message, sort_keys=True).encode("utf-8") + b"\n"

            conn = sock_mod.create_connection(("127.0.0.1", actual_port), timeout=2.0)
            conn.sendall(encoded)
            time.sleep(0.1)  # let the recorder write to disk
            conn.close()

            rec.stop()

            log_path = Path(tmpdir) / "communication_log.txt"
            self.assertTrue(log_path.exists())
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            # line 0 is always the run_meta header; line 1 is the message
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0]).get("type"), "run_meta")
            record = json.loads(lines[1])
            self.assertIn("logged_at", record)
            self.assertEqual(record["message"]["topic"], "communication")
            self.assertEqual(record["message"]["payload"]["data"], "hello")

    def test_records_multiple_messages(self) -> None:
        """Multiple messages sent on the same persistent connection all get logged."""
        import socket as sock_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder({"port": 0, "logs_dir": tmpdir, "log_type": "txt"})
            rec.start()

            assert rec.server_socket is not None
            actual_port = rec.server_socket.getsockname()[1]

            conn = sock_mod.create_connection(("127.0.0.1", actual_port), timeout=2.0)
            for i in range(3):
                msg = {
                    "sender": "s",
                    "target": "recorder",
                    "topic": "t",
                    "sent_at": time.time(),
                    "payload": {"i": i},
                }
                conn.sendall(json.dumps(msg, sort_keys=True).encode("utf-8") + b"\n")
            time.sleep(0.15)
            conn.close()

            rec.stop()

            log_path = Path(tmpdir) / "communication_log.txt"
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            # run_meta header + 3 messages
            self.assertEqual(len(lines), 4)


class TestRecorderConfigurableLogging(unittest.TestCase):
    """Tests for the configurable logging features: enabled flag, topic filter, run_meta."""

    def _send_messages(self, port: int, messages: list[dict]) -> None:
        """Helper to send a list of JSON-line messages to a TCP port."""
        import socket as sock_mod

        conn = sock_mod.create_connection(("127.0.0.1", port), timeout=2.0)
        for msg in messages:
            conn.sendall(json.dumps(msg, sort_keys=True).encode("utf-8") + b"\n")
        time.sleep(0.15)
        conn.close()

    def test_run_meta_is_first_line(self) -> None:
        """First line of the log must be a run_meta record with expected fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder(
                {
                    "port": 0,
                    "logs_dir": tmpdir,
                    "log_type": "txt",
                    "scenario": "test_scenario",
                    "logic_module_types": ["controller_fixed_cycle"],
                }
            )
            rec.start()
            rec.stop()

            lines = (
                (Path(tmpdir) / "communication_log.txt")
                .read_text()
                .strip()
                .splitlines()
            )
            self.assertGreater(len(lines), 0)
            meta = json.loads(lines[0])
            self.assertEqual(meta.get("type"), "run_meta")
            self.assertEqual(meta.get("scenario"), "test_scenario")
            self.assertIn("logged_topics", meta)
            self.assertIn("vehicle_log_enabled", meta)

    def test_topic_filter_allows_only_listed_topics(self) -> None:
        """Only messages whose inner payload topic is in the allowlist are written."""
        import socket as sock_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder(
                {
                    "port": 0,
                    "logs_dir": tmpdir,
                    "log_type": "txt",
                    "topics": ["traffic_state"],
                }
            )
            rec.start()
            assert rec.server_socket is not None
            port = rec.server_socket.getsockname()[1]

            messages = [
                {
                    "sender": "env",
                    "target": "orch",
                    "topic": "comm",
                    "sent_at": time.time(),
                    "payload": {"topic": "traffic_state", "step": 1},
                },
                {
                    "sender": "ctrl",
                    "target": "orch",
                    "topic": "comm",
                    "sent_at": time.time(),
                    "payload": {"topic": "logic_command", "step": 1},
                },
                {
                    "sender": "env",
                    "target": "orch",
                    "topic": "comm",
                    "sent_at": time.time(),
                    "payload": {"topic": "traffic_state", "step": 2},
                },
            ]
            self._send_messages(port, messages)
            rec.stop()

            lines = (
                (Path(tmpdir) / "communication_log.txt")
                .read_text()
                .strip()
                .splitlines()
            )
            # run_meta + 2 traffic_state messages (logic_command filtered out)
            self.assertEqual(len(lines), 3)
            # verify both data lines are traffic_state
            for line in lines[1:]:
                record = json.loads(line)
                self.assertEqual(record["message"]["payload"]["topic"], "traffic_state")

    def test_topic_filter_empty_logs_all(self) -> None:
        """An empty topics list means no filtering — all messages are logged."""
        import socket as sock_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder(
                {
                    "port": 0,
                    "logs_dir": tmpdir,
                    "log_type": "txt",
                    "topics": [],
                }
            )
            rec.start()
            assert rec.server_socket is not None
            port = rec.server_socket.getsockname()[1]

            messages = [
                {
                    "sender": "a",
                    "target": "b",
                    "topic": "x",
                    "sent_at": time.time(),
                    "payload": {"topic": "topic_a"},
                },
                {
                    "sender": "a",
                    "target": "b",
                    "topic": "x",
                    "sent_at": time.time(),
                    "payload": {"topic": "topic_b"},
                },
            ]
            self._send_messages(port, messages)
            rec.stop()

            lines = (
                (Path(tmpdir) / "communication_log.txt")
                .read_text()
                .strip()
                .splitlines()
            )
            # run_meta + 2 messages
            self.assertEqual(len(lines), 3)


class TestRecorderVehicleLog(unittest.TestCase):
    """Tests for the dedicated vehicle log sink fed via the orchestrator."""

    def _send_messages(self, port: int, messages: list[dict]) -> None:
        """Helper to send a list of JSON-line messages to a TCP port."""
        import socket as sock_mod

        conn = sock_mod.create_connection(("127.0.0.1", port), timeout=2.0)
        for msg in messages:
            conn.sendall(json.dumps(msg, sort_keys=True).encode("utf-8") + b"\n")
        time.sleep(0.15)
        conn.close()

    def _vehicle_log_message(self, payload: dict) -> dict:
        """Wrap a vehicle-log payload in the orchestrator envelope."""
        return {
            "sender": "orchestrator",
            "target": "recorder",
            "topic": "vehicle_log",
            "sent_at": time.time(),
            "payload": payload,
        }

    def test_vehicle_log_written_verbatim(self) -> None:
        """vehicle_log messages are written to vehicle_log.jsonl, not the comm log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder(
                {
                    "port": 0,
                    "logs_dir": tmpdir,
                    "log_type": "txt",
                    "vehicle_log_enabled": True,
                }
            )
            rec.start()
            assert rec.server_socket is not None
            port = rec.server_socket.getsockname()[1]

            meta = {"type": "run_meta", "scenario": "s", "total_lane_length_m": 100.0}
            arrival = {
                "vehicle_id": "v_0",
                "event_type": "arrival",
                "time": 1.0,
                "priority": 0,
            }
            departure = {
                "vehicle_id": "v_0",
                "event_type": "departure",
                "time": 5.0,
                "priority": 0,
                "route_distance_m": 42.0,
            }
            self._send_messages(
                port,
                [
                    self._vehicle_log_message(meta),
                    self._vehicle_log_message(arrival),
                    self._vehicle_log_message(departure),
                ],
            )
            rec.stop()

            vehicle_log = Path(tmpdir) / "vehicle_log.jsonl"
            self.assertTrue(vehicle_log.exists())
            lines = vehicle_log.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[0]), meta)
            self.assertEqual(json.loads(lines[1]), arrival)
            self.assertEqual(json.loads(lines[2]), departure)

            # vehicle-log messages must not leak into the communication log
            comm_lines = (
                (Path(tmpdir) / "communication_log.txt")
                .read_text(encoding="utf-8")
                .strip()
                .splitlines()
            )
            self.assertEqual(len(comm_lines), 1)  # only the run_meta header

    def test_vehicle_log_preserves_key_order(self) -> None:
        """Vehicle-log records are written in received key order (not alphabetically sorted).

        This keeps vehicle_log.jsonl byte-identical to the format the environment used to
        write directly, so downstream tooling that relies on the exact layout is unaffected.
        """
        import socket as sock_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder(
                {
                    "port": 0,
                    "logs_dir": tmpdir,
                    "log_type": "txt",
                    "vehicle_log_enabled": True,
                }
            )
            rec.start()
            assert rec.server_socket is not None
            port = rec.server_socket.getsockname()[1]

            # schema key order as produced by the environment (deliberately non-alphabetical)
            departure = {
                "vehicle_id": "v_7",
                "event_type": "departure",
                "time": 5.0,
                "priority": 1,
                "route_distance_m": 42.0,
            }
            msg = self._vehicle_log_message(departure)

            # send WITHOUT sort_keys, exactly as the orchestrator forwards vehicle-log messages
            conn = sock_mod.create_connection(("127.0.0.1", port), timeout=2.0)
            conn.sendall(json.dumps(msg).encode("utf-8") + b"\n")
            time.sleep(0.15)
            conn.close()
            rec.stop()

            line = (
                (Path(tmpdir) / "vehicle_log.jsonl")
                .read_text(encoding="utf-8")
                .strip()
                .splitlines()[0]
            )
            parsed = json.loads(line)
            self.assertEqual(list(parsed.keys()), list(departure.keys()))

    def test_vehicle_log_disabled_writes_no_file(self) -> None:
        """With vehicle_log_enabled False, no vehicle_log.jsonl is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = Recorder(
                {
                    "port": 0,
                    "logs_dir": tmpdir,
                    "log_type": "txt",
                    "vehicle_log_enabled": False,
                }
            )
            rec.start()
            assert rec.server_socket is not None
            port = rec.server_socket.getsockname()[1]

            self._send_messages(
                port,
                [self._vehicle_log_message({"type": "run_meta", "scenario": "s"})],
            )
            rec.stop()

            self.assertFalse((Path(tmpdir) / "vehicle_log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
