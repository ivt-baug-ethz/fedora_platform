"""Unit tests for EvaluationConfig."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evaluation.config import ALL_METRICS, EvaluationConfig


class TestEvaluationConfig(unittest.TestCase):
    """Test EvaluationConfig.from_dict() input handling."""

    def test_from_dict_empty_enables_all(self) -> None:
        """An empty dict enables all metrics and sets enabled=True."""
        cfg = EvaluationConfig.from_dict({})
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.metrics, ALL_METRICS)

    def test_from_dict_enabled_false(self) -> None:
        """enabled=False is preserved."""
        cfg = EvaluationConfig.from_dict({"enabled": False})
        self.assertFalse(cfg.enabled)

    def test_from_dict_empty_metrics_list_enables_all(self) -> None:
        """An explicit empty metrics list enables all metrics."""
        cfg = EvaluationConfig.from_dict({"metrics": []})
        self.assertEqual(cfg.metrics, ALL_METRICS)

    def test_from_dict_specific_metrics(self) -> None:
        """A non-empty metrics list enables only the listed metrics."""
        cfg = EvaluationConfig.from_dict({"metrics": ["vht", "flow"]})
        self.assertEqual(cfg.metrics, frozenset({"vht", "flow"}))

    def test_from_dict_unknown_metric_raises(self) -> None:
        """An unrecognised metric name raises ValueError."""
        with self.assertRaises(ValueError):
            EvaluationConfig.from_dict({"metrics": ["vht", "not_a_metric"]})

    def test_from_dict_defaults_enabled_true(self) -> None:
        """Missing 'enabled' key defaults to True."""
        cfg = EvaluationConfig.from_dict({"metrics": ["vkt"]})
        self.assertTrue(cfg.enabled)


if __name__ == "__main__":
    unittest.main()
