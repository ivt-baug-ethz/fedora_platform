"""Standard evaluation plot generation for the FEDORA Platform."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


class PlotGenerator:
    """Generate standard evaluation plots from completed vehicle records.

    All plots are aggregate (controller-agnostic) with no priority/regular split.
    For Priority Pass-specific per-group plots, use ``PriorityPassAnalysis`` in
    the ``post_processing`` package.

    Args:
        vehicle_records: List of completed-vehicle dicts from ``VehicleLogLoader``.
    """

    def __init__(self, vehicle_records: list[dict[str, Any]]) -> None:
        """Initialise with parsed, completed vehicle records."""
        self.vehicle_records = vehicle_records

    def plot_travel_time_distribution(self, output_path: Path) -> None:
        """Save a histogram of all completed vehicle travel times.

        Args:
            output_path: Destination PNG file path.
        """
        travel_times = [
            rec["departure"] - rec["arrival"] for rec in self.vehicle_records
        ]

        _, ax = plt.subplots(figsize=(10, 5))
        if travel_times:
            ax.hist(travel_times, bins=20, alpha=0.7, color="steelblue")
            mean_tt = statistics.mean(travel_times)
            ax.axvline(
                mean_tt,
                color="red",
                linestyle="--",
                label=f"Mean: {mean_tt:.2f}s",
            )
            ax.legend()
        else:
            ax.text(0.5, 0.5, "No completed vehicles", ha="center", va="center")

        ax.set_xlabel("Travel Time (seconds)")
        ax.set_ylabel("Number of Vehicles")
        ax.set_title("Vehicle Travel Time Distribution")
        plt.tight_layout()
        self._save(output_path)

    def plot_vehicle_counts(self, output_path: Path) -> None:
        """Save a cumulative completed-vehicle count over run time.

        Args:
            output_path: Destination PNG file path.
        """
        sorted_records = sorted(self.vehicle_records, key=lambda r: r["departure"])

        times = [rec["departure"] for rec in sorted_records]
        cumulative = list(range(1, len(times) + 1))

        _, ax = plt.subplots(figsize=(12, 6))
        if times:
            ax.plot(times, cumulative, label="Total Vehicles", linewidth=2)

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Number of Vehicles")
        ax.set_title("Cumulative Vehicle Count with Measured Travel Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        self._save(output_path)

    def plot_average_travel_time(self, output_path: Path) -> None:
        """Save a cumulative average travel time over run time.

        Args:
            output_path: Destination PNG file path.
        """
        sorted_records = sorted(self.vehicle_records, key=lambda r: r["departure"])

        times: list[float] = []
        avg_series: list[float] = []
        running_sum = 0.0

        for i, rec in enumerate(sorted_records, start=1):
            running_sum += rec["departure"] - rec["arrival"]
            times.append(rec["departure"])
            avg_series.append(running_sum / i)

        _, ax = plt.subplots(figsize=(12, 6))
        if times:
            ax.plot(times, avg_series, label="Overall", linewidth=2, linestyle="--")

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Average Travel Time (seconds)")
        ax.set_title(
            "Average Vehicle Travel Time Over Time (Normalized by Vehicle Count)"
        )
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        self._save(output_path)

    def _save(self, output_path: Path) -> None:
        """Save the current figure to disk and close it.

        Args:
            output_path: Destination PNG file path; parent dirs are created if needed.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150)
        print(f"Saved plot to {output_path}")
        plt.close()
