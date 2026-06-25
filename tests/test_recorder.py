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
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
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
                msg = {"sender": "s", "target": "recorder", "topic": "t",
                       "sent_at": time.time(), "payload": {"i": i}}
                conn.sendall(json.dumps(msg, sort_keys=True).encode("utf-8") + b"\n")
            time.sleep(0.15)
            conn.close()

            rec.stop()

            log_path = Path(tmpdir) / "communication_log.txt"
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
