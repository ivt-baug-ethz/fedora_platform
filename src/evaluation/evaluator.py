"""Evaluation facade for the FEDORA Platform."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.config import ALL_METRICS, EvaluationConfig
from evaluation.loader import VehicleLogLoader
from evaluation.metrics import MetricsComputer
from evaluation.plots import PlotGenerator


class Evaluator:  # pylint: disable=too-few-public-methods
    """Post-run analysis: load vehicle log, compute standard metrics, produce plots.

    Wires together ``VehicleLogLoader``, ``MetricsComputer``, and ``PlotGenerator``
    into a single callable pipeline. All metrics are controller-agnostic aggregates.

    For controller-specific analysis (e.g. Priority Pass priority vs. regular vehicle
    breakdown), use ``PriorityPassAnalysis`` in the ``post_processing`` package.

    Args:
        logs_dir: Directory containing ``vehicle_log.jsonl``.
        output_dir: Directory for output plots and ``evaluation_stats.json``.
        config: Evaluation settings. If ``None``, all standard metrics are computed.
    """

    def __init__(
        self,
        logs_dir: Path | str,
        output_dir: Path | str,
        config: EvaluationConfig | None = None,
    ) -> None:
        """Initialise the evaluator."""
        self.logs_dir = Path(logs_dir)
        self.output_dir = Path(output_dir)
        self.config = (
            config if config is not None else EvaluationConfig(metrics=ALL_METRICS)
        )
        self.vehicle_log_path = self.logs_dir / "vehicle_log.jsonl"

    def evaluate_and_report(self) -> dict[str, Any]:
        """Run the full evaluation pipeline and write outputs to disk.

        Loads the vehicle log, computes all enabled standard metrics, generates
        three plots, and writes ``evaluation_stats.json`` to ``output_dir``.

        Returns:
            The computed metrics dict (same content as ``evaluation_stats.json``).

        Raises:
            FileNotFoundError: If ``vehicle_log.jsonl`` does not exist in ``logs_dir``.
        """
        loader = VehicleLogLoader(self.vehicle_log_path)
        run_meta, vehicle_records = loader.load()

        computer = MetricsComputer(vehicle_records, run_meta)
        stats = computer.compute(self.config.metrics)

        self._print_summary(stats)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        plotter = PlotGenerator(vehicle_records)
        plotter.plot_travel_time_distribution(
            self.output_dir / "travel_time_distribution.png"
        )
        plotter.plot_average_travel_time(self.output_dir / "average_travel_time.png")
        plotter.plot_vehicle_counts(self.output_dir / "vehicle_counts.png")

        stats_path = self.output_dir / "evaluation_stats.json"
        with stats_path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        print(f"Evaluation stats saved to {stats_path}\n")

        return stats

    @staticmethod
    def _print_summary(stats: dict[str, Any]) -> None:
        """Print a human-readable summary of computed metrics to stdout.

        Args:
            stats: Metrics dict as returned by ``MetricsComputer.compute``.
        """
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        print(f"Total vehicles:                  {stats['total_vehicles']}")
        print(f"Vehicles with travel time:       {stats['vehicles_with_travel_time']}")

        if stats.get("overall_avg_travel_time") is not None:
            print(
                f"\nAverage travel time:             {stats['overall_avg_travel_time']:.2f} s"
            )
            print(
                f"Median travel time:              {stats['overall_median_travel_time']:.2f} s"
            )
            print(
                f"Travel time range:               "
                f"{stats['overall_min_travel_time']:.2f}s"
                f" – {stats['overall_max_travel_time']:.2f}s"
            )

        if stats.get("travel_time_variance") is not None:
            print(
                f"Travel time variance:            {stats['travel_time_variance']:.2f} s²"
            )

        if stats.get("vht") is not None:
            print(f"\nVHT (Vehicle Hours Traveled):    {stats['vht']:.4f} veh·h")

        if stats.get("vkt") is not None:
            print(f"VKT (Vehicle Km Traveled):       {stats['vkt']:.4f} veh·km")

        if stats.get("flow") is not None:
            print(f"Flow:                            {stats['flow']:.2f} veh/h")

        if stats.get("space_mean_speed") is not None:
            print(
                f"Space mean speed:                {stats['space_mean_speed']:.2f} km/h"
            )

        if stats.get("density") is not None:
            print(f"Density:                         {stats['density']:.4f} veh/km")

        print("=" * 60 + "\n")
