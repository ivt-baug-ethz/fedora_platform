"""Evaluation component — loads simulation logs and computes travel time statistics."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


class Evaluator:
    """Read simulation logs and evaluate performance metrics like vehicle travel time."""

    def __init__(
        self,
        logs_dir: str | Path,
        output_dir: str | Path | None = None,
        show_priority: bool = True,
    ) -> None:
        """Initialize the evaluator from a logs directory.

        Args:
            logs_dir: Directory containing the vehicle_log.jsonl file.
            output_dir: Directory for output plots and stats (default: logs_dir/evaluation).
            show_priority: If False, omit the priority-vehicle series from travel time plots.
        """
        # resolve directories, defaulting output to a sub-folder of logs
        self.logs_dir = Path(logs_dir)
        self.output_dir = (
            Path(output_dir) if output_dir else self.logs_dir / "evaluation"
        )
        self.show_priority = show_priority
        self.vehicle_log_path = self.logs_dir / "vehicle_log.jsonl"

        # populated by load_vehicle_log() and calculate_travel_times()
        self.vehicle_data: dict[str, dict[str, Any]] = {}
        self.delays: dict[str, float] = {}
        self.regular_delays: list[float] = []
        self.priority_delays: list[float] = []

    def load_vehicle_log(self) -> None:
        """Load vehicle arrival and departure events from the JSONL log file."""
        if not self.vehicle_log_path.exists():
            raise FileNotFoundError(f"Vehicle log not found: {self.vehicle_log_path}")

        with self.vehicle_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    vehicle_id = event["vehicle_id"]

                    # create an entry on first encounter; subsequent events fill the timestamps
                    if vehicle_id not in self.vehicle_data:
                        self.vehicle_data[vehicle_id] = {
                            "priority": event["priority"],
                            "arrival": None,
                            "departure": None,
                        }
                    if event["event_type"] == "arrival":
                        self.vehicle_data[vehicle_id]["arrival"] = event["time"]
                    elif event["event_type"] == "departure":
                        self.vehicle_data[vehicle_id]["departure"] = event["time"]

    def calculate_travel_times(self) -> None:
        """Calculate travel time for each vehicle from its arrival to departure."""
        for vehicle_id, data in self.vehicle_data.items():
            # skip vehicles that never departed (still in the network at simulation end)
            if data["arrival"] is not None and data["departure"] is not None:
                travel_time = data["departure"] - data["arrival"]
                self.delays[vehicle_id] = travel_time

                # bucket into priority or regular for per-group statistics
                if data["priority"] == 1:
                    self.priority_delays.append(travel_time)
                else:
                    self.regular_delays.append(travel_time)

    def get_statistics(self) -> dict[str, Any]:
        """Compute summary statistics over all recorded travel times.

        Returns:
            Dict containing counts and average/median/min/max travel times by vehicle type.
        """
        all_travel_times = list(self.delays.values())

        # counts always present; time statistics only if there are observations
        stats: dict[str, Any] = {
            "total_vehicles": len(self.vehicle_data),
            "vehicles_with_travel_time": len(self.delays),
            "regular_vehicles": len(self.regular_delays),
            "priority_vehicles": len(self.priority_delays),
        }

        if all_travel_times:
            stats["overall_avg_travel_time"] = statistics.mean(all_travel_times)
            stats["overall_median_travel_time"] = statistics.median(all_travel_times)
            stats["overall_min_travel_time"] = min(all_travel_times)
            stats["overall_max_travel_time"] = max(all_travel_times)

        # per-group stats — set to None when the group has no observations
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

    def plot_travel_time_distribution(
        self, output_path: str | Path | None = None
    ) -> None:
        """Plot travel time histograms for regular and priority vehicles side by side.

        Args:
            output_path: If given, save the figure to this path; otherwise display it.
        """
        # two side-by-side subplots: regular vehicles on left, priority on right
        _, axes = plt.subplots(1, 2, figsize=(14, 5))

        if self.regular_delays:
            axes[0].hist(self.regular_delays, bins=20, alpha=0.7, color="blue")
            axes[0].axvline(
                statistics.mean(self.regular_delays),
                color="red",
                linestyle="--",
                label=f"Mean: {statistics.mean(self.regular_delays):.2f}s",
            )
            axes[0].set_xlabel("Travel Time (seconds)")
            axes[0].set_ylabel("Number of Vehicles")
            axes[0].set_title("Regular Vehicle Travel Time Distribution")
            axes[0].legend()
        else:
            axes[0].text(0.5, 0.5, "No regular vehicles", ha="center", va="center")
            axes[0].set_title("Regular Vehicle Travel Time Distribution")

        # show_priority is False for controllers that don't use priority vehicles
        if self.priority_delays and self.show_priority:
            axes[1].hist(self.priority_delays, bins=20, alpha=0.7, color="green")
            axes[1].axvline(
                statistics.mean(self.priority_delays),
                color="red",
                linestyle="--",
                label=f"Mean: {statistics.mean(self.priority_delays):.2f}s",
            )
            axes[1].set_xlabel("Travel Time (seconds)")
            axes[1].set_ylabel("Number of Vehicles")
            axes[1].set_title("Priority Vehicle Travel Time Distribution")
            axes[1].legend()
        else:
            axes[1].text(0.5, 0.5, "No priority vehicles", ha="center", va="center")
            axes[1].set_title("Priority Vehicle Travel Time Distribution")

        plt.tight_layout()

        # save to file if a path was given, otherwise display interactively
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150)
            print(f"Saved delay distribution plot to {output_path}")
        else:
            plt.show()

        plt.close()

    def plot_vehicle_counts(self, output_path: str | Path | None = None) -> None:
        """Plot cumulative vehicle counts over simulation time by vehicle type.

        Counts only vehicles whose travel time was measured (both arrival and
        departure recorded), matching the population used by all other metrics.

        Args:
            output_path: If given, save the figure to this path; otherwise display it.
        """
        # sort by departure time so counts accumulate chronologically
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
            ax.plot(
                times, count_regular_series, label="Regular Vehicles", linewidth=2
            )
        # show_priority is False for controllers that don't use priority vehicles
        if count_priority_series and self.show_priority:
            ax.plot(
                times, count_priority_series, label="Priority Vehicles", linewidth=2
            )
        ax.plot(
            times, count_total_series, label="Total", linewidth=2, linestyle="--"
        )

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Number of Vehicles")
        ax.set_title("Cumulative Vehicle Count with Measured Travel Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        # save to file if a path was given, otherwise display interactively
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150)
            print(f"Saved vehicle count plot to {output_path}")
        else:
            plt.show()

        plt.close()

    def plot_average_travel_time(self, output_path: str | Path | None = None) -> None:
        """Plot cumulative average travel time over simulation time by vehicle type.

        Args:
            output_path: If given, save the figure to this path; otherwise display it.
        """
        # sort by departure time so the cumulative averages accumulate chronologically
        sorted_vehicles = sorted(
            self.vehicle_data.items(),
            key=lambda x: (
                x[1]["departure"] if x[1]["departure"] is not None else float("inf")
            ),
        )

        # accumulators for running cumulative averages per group
        times: list[float] = []
        avg_travel_time_regular: list[float] = []
        avg_travel_time_priority: list[float] = []
        avg_travel_time_total: list[float] = []

        sum_regular = 0.0
        sum_priority = 0.0
        sum_total = 0.0
        count_regular = 0
        count_priority = 0

        for _, data in sorted_vehicles:
            if data["arrival"] is None or data["departure"] is None:
                continue
            travel_time = data["departure"] - data["arrival"]

            # update per-group running sums
            if data["priority"] == 1:
                sum_priority += travel_time
                count_priority += 1
            else:
                sum_regular += travel_time
                count_regular += 1

            sum_total += travel_time
            count_total = count_regular + count_priority

            # append one data point per vehicle departure
            times.append(data["departure"])
            avg_travel_time_total.append(
                sum_total / count_total if count_total > 0 else 0.0
            )
            avg_travel_time_regular.append(
                sum_regular / count_regular if count_regular > 0 else 0.0
            )
            avg_travel_time_priority.append(
                sum_priority / count_priority if count_priority > 0 else 0.0
            )

        _, ax = plt.subplots(figsize=(12, 6))
        if avg_travel_time_regular:
            ax.plot(
                times, avg_travel_time_regular, label="Regular Vehicles", linewidth=2
            )
        # show_priority is False for controllers that don't use priority vehicles
        if avg_travel_time_priority and self.show_priority:
            ax.plot(
                times, avg_travel_time_priority, label="Priority Vehicles", linewidth=2
            )
        ax.plot(
            times, avg_travel_time_total, label="Overall", linewidth=2, linestyle="--"
        )

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Average Travel Time (seconds)")
        ax.set_title(
            "Average Vehicle Travel Time Over Time (Normalized by Vehicle Count)"
        )
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        # save to file if a path was given, otherwise display interactively
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150)
            print(f"Saved average delay plot to {output_path}")
        else:
            plt.show()

        plt.close()

    def evaluate_and_report(self) -> dict[str, Any]:
        """Run the full evaluation pipeline and save plots and statistics to disk.

        Returns:
            Statistics dict as returned by get_statistics().
        """
        # load logs and compute travel times before generating any output
        self.load_vehicle_log()
        self.calculate_travel_times()
        stats = self.get_statistics()

        # print a human-readable summary to stdout
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        print(f"Total vehicles: {stats['total_vehicles']}")
        print(
            f"Vehicles with measured travel time: {stats['vehicles_with_travel_time']}"
        )
        print(f"Regular vehicles: {stats['regular_vehicles']}")
        print(f"Priority vehicles: {stats['priority_vehicles']}")
        print()

        if stats.get("overall_avg_travel_time") is not None:
            print(
                f"Overall Average Travel Time: {stats['overall_avg_travel_time']:.2f}s"
            )
            print(
                f"Overall Median Travel Time: {stats['overall_median_travel_time']:.2f}s"
            )
            min_t = stats["overall_min_travel_time"]
            max_t = stats["overall_max_travel_time"]
            print(f"Travel Time Range: {min_t:.2f}s - {max_t:.2f}s")
            print()

        if stats.get("regular_avg_travel_time") is not None:
            print(
                f"Regular Vehicles Average Travel Time: {stats['regular_avg_travel_time']:.2f}s"
            )
            print(
                f"Regular Vehicles Median Travel Time: {stats['regular_median_travel_time']:.2f}s"
            )

        if stats.get("priority_avg_travel_time") is not None:
            print(
                f"Priority Vehicles Average Travel Time: {stats['priority_avg_travel_time']:.2f}s"
            )
            print(
                f"Priority Vehicles Median Travel Time: {stats['priority_median_travel_time']:.2f}s"
            )

        print("=" * 60 + "\n")

        # save plots and JSON statistics to the output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plot_travel_time_distribution(
            self.output_dir / "travel_time_distribution.png"
        )
        self.plot_average_travel_time(self.output_dir / "average_travel_time.png")
        self.plot_vehicle_counts(self.output_dir / "vehicle_counts.png")

        with (self.output_dir / "evaluation_stats.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(stats, f, indent=2)
        print(
            f"Evaluation stats saved to {self.output_dir / 'evaluation_stats.json'}\n"
        )

        return stats
