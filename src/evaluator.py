"""Evaluation component for analyzing simulation results and calculating delays."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


class Evaluator:
    """Read simulation logs and evaluate performance metrics like delay."""

    def __init__(
        self,
        logs_dir: str | Path,
        output_dir: str | Path | None = None,
    ) -> None:
        """Initialize the evaluator with a logs directory and optional output directory."""
        self.logs_dir = Path(logs_dir)
        self.output_dir = Path(output_dir) if output_dir else self.logs_dir / "evaluation"
        self.vehicle_log_path = self.logs_dir / "vehicle_log.jsonl"
        self.vehicle_data: dict[str, dict[str, Any]] = {}
        self.delays: dict[str, float] = {}
        self.regular_delays: list[float] = []
        self.priority_delays: list[float] = []

    def load_vehicle_log(self) -> None:
        """Load vehicle events from the vehicle log file."""
        if not self.vehicle_log_path.exists():
            raise FileNotFoundError(f"Vehicle log not found: {self.vehicle_log_path}")

        with self.vehicle_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    vehicle_id = event["vehicle_id"]
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
        """Calculate travel time for each vehicle (time from arrival to departure)."""
        for vehicle_id, data in self.vehicle_data.items():
            if data["arrival"] is not None and data["departure"] is not None:
                travel_time = data["departure"] - data["arrival"]
                self.delays[vehicle_id] = travel_time
                if data["priority"] == 1:
                    self.priority_delays.append(travel_time)
                else:
                    self.regular_delays.append(travel_time)

    def get_statistics(self) -> dict[str, Any]:
        """Get travel time statistics."""
        all_travel_times = list(self.delays.values())
        stats = {
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

        if self.regular_delays:
            stats["regular_avg_travel_time"] = statistics.mean(self.regular_delays)
            stats["regular_median_travel_time"] = statistics.median(self.regular_delays)
        else:
            stats["regular_avg_travel_time"] = None
            stats["regular_median_travel_time"] = None

        if self.priority_delays:
            stats["priority_avg_travel_time"] = statistics.mean(self.priority_delays)
            stats["priority_median_travel_time"] = statistics.median(self.priority_delays)
        else:
            stats["priority_avg_travel_time"] = None
            stats["priority_median_travel_time"] = None

        return stats

    def plot_travel_time_distribution(
        self, output_path: str | Path | None = None
    ) -> None:
        """Plot travel time distribution for regular and priority vehicles."""
        if plt is None:
            print("Warning: matplotlib not installed. Skipping visualization.")
            return

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

        if self.priority_delays:
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

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150)
            print(f"Saved delay distribution plot to {output_path}")
        else:
            plt.show()

    def plot_average_travel_time(self, output_path: str | Path | None = None) -> None:
        """Plot average travel time over time, normalized by vehicle count."""
        if plt is None:
            print("Warning: matplotlib not installed. Skipping visualization.")
            return

        sorted_vehicles = sorted(
            self.vehicle_data.items(),
            key=lambda x: (
                x[1]["departure"]
                if x[1]["departure"] is not None
                else float("inf")
            ),
        )

        times = []
        avg_travel_time_regular = []
        avg_travel_time_priority = []
        avg_travel_time_total = []

        sum_regular = 0.0
        sum_priority = 0.0
        sum_total = 0.0
        count_regular = 0
        count_priority = 0

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
            ax.plot(times, avg_travel_time_regular, label="Regular Vehicles", linewidth=2)
        if avg_travel_time_priority:
            ax.plot(times, avg_travel_time_priority, label="Priority Vehicles", linewidth=2)
        ax.plot(
            times, avg_travel_time_total, label="Overall", linewidth=2, linestyle="--"
        )

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Average Travel Time (seconds)")
        ax.set_title("Average Vehicle Travel Time Over Time (Normalized by Vehicle Count)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150)
            print(f"Saved average delay plot to {output_path}")
        else:
            plt.show()

    def evaluate_and_report(self) -> dict[str, Any]:
        """Run full evaluation and generate reports."""
        self.load_vehicle_log()
        self.calculate_travel_times()
        stats = self.get_statistics()

        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        print(f"Total vehicles: {stats['total_vehicles']}")
        print(f"Vehicles with measured travel time: {stats['vehicles_with_travel_time']}")
        print(f"Regular vehicles: {stats['regular_vehicles']}")
        print(f"Priority vehicles: {stats['priority_vehicles']}")
        print()

        if stats["overall_avg_travel_time"] is not None:
            print(f"Overall Average Travel Time: {stats['overall_avg_travel_time']:.2f}s")
            print(f"Overall Median Travel Time: {stats['overall_median_travel_time']:.2f}s")
            min_t = stats["overall_min_travel_time"]
            max_t = stats["overall_max_travel_time"]
            print(f"Travel Time Range: {min_t:.2f}s - {max_t:.2f}s")
            print()

        if stats["regular_avg_travel_time"] is not None:
            print(
                f"Regular Vehicles Average Travel Time: {stats['regular_avg_travel_time']:.2f}s"
            )
            print(
                f"Regular Vehicles Median Travel Time: {stats['regular_median_travel_time']:.2f}s"
            )

        if stats["priority_avg_travel_time"] is not None:
            print(
                f"Priority Vehicles Average Travel Time: {stats['priority_avg_travel_time']:.2f}s"
            )
            print(
                f"Priority Vehicles Median Travel Time: {stats['priority_median_travel_time']:.2f}s"
            )

        print("=" * 60 + "\n")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.plot_travel_time_distribution(self.output_dir / "travel_time_distribution.png")
        self.plot_average_travel_time(self.output_dir / "average_travel_time.png")

        with (self.output_dir / "evaluation_stats.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(stats, f, indent=2)
        print(f"Evaluation stats saved to {self.output_dir / 'evaluation_stats.json'}\n")

        return stats
