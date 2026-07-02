"""Evaluation package for the FEDORA Platform.

Provides standard traffic-engineering metrics (VKT, VHT, flow, density, speed,
travel time variance, average delay, delay variance) computed from environment run logs.

For controller-specific analysis (e.g. Priority Pass priority vs. regular vehicle
comparison), see the ``post_processing`` package in the repository root.
"""

from evaluation.config import ALL_METRICS, EvaluationConfig
from evaluation.evaluator import Evaluator

__all__ = ["ALL_METRICS", "EvaluationConfig", "Evaluator"]
