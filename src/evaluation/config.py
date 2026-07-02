"""Evaluation configuration dataclass for the FEDORA Platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALL_METRICS: frozenset[str] = frozenset(
    {
        "travel_time",
        "travel_time_variance",
        "vht",
        "vkt",
        "flow",
        "speed",
        "density",
    }
)


@dataclass
class EvaluationConfig:
    """Settings that control which post-run metrics are computed and whether to run at all.

    Attributes:
        enabled: Whether to run evaluation after the environment run completes.
        metrics: Set of metric names to compute. Contains all metrics when constructed
            from an empty or absent list (the default).
    """

    enabled: bool = True
    metrics: frozenset[str] = field(default_factory=lambda: ALL_METRICS)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationConfig":
        """Build an EvaluationConfig from the JSON 'evaluation' config block.

        An empty or absent ``metrics`` list enables all standard metrics.

        Args:
            data: The ``evaluation`` sub-dict from the scenario JSON config.

        Returns:
            Configured EvaluationConfig instance.

        Raises:
            ValueError: If any metric name in the list is not recognised.
        """
        enabled = bool(data.get("enabled", True))
        metrics_list: list[str] = list(data.get("metrics", []))
        if not metrics_list:
            metrics = ALL_METRICS
        else:
            unknown = frozenset(metrics_list) - ALL_METRICS
            if unknown:
                raise ValueError(
                    f"Unknown evaluation metrics: {sorted(unknown)}. "
                    f"Valid options: {sorted(ALL_METRICS)}"
                )
            metrics = frozenset(metrics_list)
        return cls(enabled=enabled, metrics=metrics)
