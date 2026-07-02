# pylint: disable=duplicate-code
"""Priority Pass post-processing: compare regular vs. priority vehicle metrics.

This module is NOT part of the standard evaluation pipeline. Run it manually
after collecting logs from Priority Pass controller runs to analyse the
difference in travel times between regular and priority (UPP) vehicles.

The standard ``Evaluator`` in ``src/evaluation`` computes controller-agnostic
aggregate metrics. This script adds the per-group breakdown that is specific
to the Priority Pass controller.

Example usage::

    from pathlib import Path
    from post_processing.priority_pass_analysis import PriorityPassAnalysis

    analysis = PriorityPassAnalysis(
        logs_dir=Path("logs/demo_priority_pass"),
        output_dir=Path("results/demo/controller_priority_pass/pp_analysis"),
    )
    analysis.run()
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


class PriorityPassAnalysis:
    """Priority Pass-specific post-processing: compare regular vs. priority vehicle metrics.

    Reads ``vehicle_log.jsonl`` from a completed Priority Pass environment run and
    produces per-group statistics and plots (regular vehicles vs. priority/UPP vehicles).

    Args:
        logs_dir: Directory containing the ``vehicle_log.jsonl`` file.
        output_dir: Directory for output plots and ``pp_analysis_stats.json``.
    """

    def __init__(self, logs_dir: Path | str, output_dir: Path | str) -> None:
        """Initialise the analysis with log and output directories."""
        self.logs_dir = Path(logs_dir)
        self.output_dir = Path(output_dir)
        self.vehicle_log_path = self.logs_dir / "vehicle_log.jsonl"

        # populated by load()
        self.vehicle_data: dict[str, dict[str, Any]] = {}
        self.regular_delays: list[float] = []
        self.priority_delays: list[float] = []

    def load(self) -> None:
        """Load vehicle arrival and departure events from the JSONL log file.

        Raises:
            FileNotFoundError: If ``vehicle_log.jsonl`` does not exist.
        """
        if not self.vehicle_log_path.exists():
            raise FileNotFoundError(f"Vehicle log not found: {self.vehicle_log_path}")

        with self.vehicle_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    event: dict[str, Any] = json.loads(line)
                    if event.get("type") == "run_meta":
                        continue
                    vehicle_id: str = event["vehicle_id"]

                    if vehicle_id not in self.vehicle_data:
                        self.vehicle_data[vehicle_id] = {
                            "priority": int(event.get("priority", 0)),
                            "arrival": None,
                            "departure": None,
                        }
                    if event["event_type"] == "arrival":
                        self.vehicle_data[vehicle_id]["arrival"] = float(event["time"])
                    elif event["event_type"] == "departure":
                        self.vehicle_data[vehicle_id]["departure"] = float(
                            event["time"]
                        )

        for data in self.vehicle_data.values():
            if data["arrival"] is not None and data["departure"] is not None:
                travel_time = data["departure"] - data["arrival"]
                if data["priority"] == 1:
                    self.priority_delays.append(travel_time)
                else:
                    self.regular_delays.append(travel_time)

    def compute_group_stats(self) -> dict[str, Any]:
        """Compute travel-time statistics for regular, priority, and overall groups.

        Returns:
            Dict with counts, and mean/median travel times for each group.
        """
        all_delays = self.regular_delays + self.priority_delays
        stats: dict[str, Any] = {
            "total_vehicles": len(self.vehicle_data),
            "vehicles_with_travel_time": len(all_delays),
            "regular_vehicles": len(self.regular_delays),
            "priority_vehicles": len(self.priority_delays),
        }

        if all_delays:
            stats["overall_avg_travel_time"] = statistics.mean(all_delays)
            stats["overall_median_travel_time"] = statistics.median(all_delays)
            stats["overall_min_travel_time"] = min(all_delays)
            stats["overall_max_travel_time"] = max(all_delays)

        if self.regular_delays:
            stats["regular_avg_travel_time"] = statistics.mean(self.regular_delays)
            stats["regular_median_travel_time"] = statistics.median(self.regular_delays)
        else:
            stats["regular_avg_travel_time"] = None
            stats["regular_median_travel_time"] = None

        if self.priority_delays:
            stats["priority_avg_travel_time"] = statistics.mean(self.priority_delays)
            stats["priority_median_travel_time"] = statistics.median(
                self.priority_delays
            )
        else:
            stats["priority_avg_travel_time"] = None
            stats["priority_median_travel_time"] = None

        return stats

    def plot_travel_time_by_group(self, output_path: Path | None = None) -> None:
        """Save side-by-side travel time histograms for regular and priority vehicles.

        Args:
            output_path: Destination PNG file path. Defaults to
                ``output_dir/pp_travel_time_distribution.png``.
        """
        if output_path is None:
            output_path = self.output_dir / "pp_travel_time_distribution.png"

        _, axes = plt.subplots(1, 2, figsize=(14, 5))

        if self.regular_delays:
            axes[0].hist(self.regular_delays, bins=20, alpha=0.7, color="blue")
            axes[0].axvline(
                statistics.mean(self.regular_delays),
                color="red",
                linestyle="--",
                label=f"Mean: {statistics.mean(self.regular_delays):.2f}s",
            )
            axes[0].legend()
        else:
            axes[0].text(0.5, 0.5, "No regular vehicles", ha="center", va="center")
        axes[0].set_xlabel("Travel Time (seconds)")
        axes[0].set_ylabel("Number of Vehicles")
        axes[0].set_title("Regular Vehicle Travel Time Distribution")

        if self.priority_delays:
            axes[1].hist(self.priority_delays, bins=20, alpha=0.7, color="green")
            axes[1].axvline(
                statistics.mean(self.priority_delays),
                color="red",
                linestyle="--",
                label=f"Mean: {statistics.mean(self.priority_delays):.2f}s",
            )
            axes[1].legend()
        else:
            axes[1].text(0.5, 0.5, "No priority vehicles", ha="center", va="center")
        axes[1].set_xlabel("Travel Time (seconds)")
        axes[1].set_ylabel("Number of Vehicles")
        axes[1].set_title("Priority Vehicle Travel Time Distribution")

        plt.tight_layout()
        self._save(output_path)

    def plot_vehicle_counts_by_group(self, output_path: Path | None = None) -> None:
        """Save cumulative vehicle counts by group over run time.

        Args:
            output_path: Destination PNG file path. Defaults to
                ``output_dir/pp_vehicle_counts.png``.
        """
        if output_path is None:
            output_path = self.output_dir / "pp_vehicle_counts.png"

        sorted_vehicles = sorted(
            (
                (vid, d)
                for vid, d in self.vehicle_data.items()
                if d["arrival"] is not None and d["departure"] is not None
            ),
            key=lambda x: x[1]["departure"],
        )

        times: list[float] = []
        count_regular_series: list[int] = []
        count_priority_series: list[int] = []
        count_total_series: list[int] = []
        count_regular = 0
        count_priority = 0

        for _, data in sorted_vehicles:
            if data["priority"] == 1:
                count_priority += 1
            else:
                count_regular += 1
            times.append(data["departure"])
            count_regular_series.append(count_regular)
            count_priority_series.append(count_priority)
            count_total_series.append(count_regular + count_priority)

        _, ax = plt.subplots(figsize=(12, 6))
        if count_regular_series:
            ax.plot(times, count_regular_series, label="Regular Vehicles", linewidth=2)
        if count_priority_series:
            ax.plot(
                times, count_priority_series, label="Priority Vehicles", linewidth=2
            )
        ax.plot(times, count_total_series, label="Total", linewidth=2, linestyle="--")

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Number of Vehicles")
        ax.set_title("Cumulative Vehicle Count with Measured Travel Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        self._save(output_path)

    def plot_average_travel_time_by_group(
        self, output_path: Path | None = None
    ) -> None:
        """Save cumulative average travel time per group over run time.

        Args:
            output_path: Destination PNG file path. Defaults to
                ``output_dir/pp_average_travel_time.png``.
        """
        if output_path is None:
            output_path = self.output_dir / "pp_average_travel_time.png"

        times, avg_regular, avg_priority, avg_total = self._build_avg_series()

        _, ax = plt.subplots(figsize=(12, 6))
        if avg_regular:
            ax.plot(times, avg_regular, label="Regular Vehicles", linewidth=2)
        if avg_priority:
            ax.plot(times, avg_priority, label="Priority Vehicles", linewidth=2)
        ax.plot(times, avg_total, label="Overall", linewidth=2, linestyle="--")

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Average Travel Time (seconds)")
        ax.set_title(
            "Average Vehicle Travel Time Over Time (Normalized by Vehicle Count)"
        )
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        self._save(output_path)

    def _build_avg_series(
        self,
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        """Build cumulative average travel time series per group, sorted by departure time.

        Returns:
            Tuple of (times, avg_regular, avg_priority, avg_total) lists.
        """
        sorted_vehicles = sorted(
            self.vehicle_data.items(),
            key=lambda x: (
                x[1]["departure"] if x[1]["departure"] is not None else float("inf")
            ),
        )

        times: list[float] = []
        avg_regular: list[float] = []
        avg_priority: list[float] = []
        avg_total: list[float] = []
        sum_regular, sum_priority, sum_total = 0.0, 0.0, 0.0
        count_regular, count_priority = 0, 0

        for _, data in sorted_vehicles:
            if data["arrival"] is None or data["departure"] is None:
                continue
            travel_time = data["departure"] - data["arrival"]
            if data["priority"] == 1:
                sum_priority += travel_time
                count_priority += 1
            else:
                sum_regular += travel_time
                count_regular += 1
            sum_total += travel_time
            count_total = count_regular + count_priority
            times.append(data["departure"])
            avg_total.append(sum_total / count_total if count_total > 0 else 0.0)
            avg_regular.append(
                sum_regular / count_regular if count_regular > 0 else 0.0
            )
            avg_priority.append(
                sum_priority / count_priority if count_priority > 0 else 0.0
            )

        return times, avg_regular, avg_priority, avg_total

    def run(self) -> dict[str, Any]:
        """Run the full Priority Pass analysis: load → stats → plots → write JSON.

        Returns:
            Group statistics dict (same content as ``pp_analysis_stats.json``).

        Raises:
            FileNotFoundError: If ``vehicle_log.jsonl`` does not exist.
        """
        self.load()
        stats = self.compute_group_stats()

        print("\n" + "=" * 60)
        print("PRIORITY PASS ANALYSIS RESULTS")
        print("=" * 60)
        print(f"Total vehicles:              {stats['total_vehicles']}")
        print(f"Vehicles with travel time:   {stats['vehicles_with_travel_time']}")
        print(f"Regular vehicles:            {stats['regular_vehicles']}")
        print(f"Priority vehicles:           {stats['priority_vehicles']}")

        if stats.get("overall_avg_travel_time") is not None:
            print(
                f"\nOverall avg travel time:     {stats['overall_avg_travel_time']:.2f}s"
            )
        if stats.get("regular_avg_travel_time") is not None:
            print(
                f"Regular avg travel time:     {stats['regular_avg_travel_time']:.2f}s"
            )
        if stats.get("priority_avg_travel_time") is not None:
            print(
                f"Priority avg travel time:    {stats['priority_avg_travel_time']:.2f}s"
            )
        print("=" * 60 + "\n")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plot_travel_time_by_group()
        self.plot_vehicle_counts_by_group()
        self.plot_average_travel_time_by_group()

        stats_path = self.output_dir / "pp_analysis_stats.json"
        with stats_path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        print(f"Priority Pass analysis stats saved to {stats_path}\n")

        return stats

    def _save(self, output_path: Path) -> None:
        """Save the current figure to disk and close it.

        Args:
            output_path: Destination PNG file path; parent dirs are created if needed.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150)
        print(f"Saved plot to {output_path}")
        plt.close()
