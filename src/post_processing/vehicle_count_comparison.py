"""Cross-controller post-processing: compare vehicle counts over time.

This module is NOT part of the standard evaluation pipeline. Run it manually to
overlay the cumulative vehicle count of several logic modules (e.g. baseline,
fixed-cycle, max-pressure, priority-pass) for the same scenario on a single plot.
Reuses ``VehicleLogLoader`` from ``src/evaluation`` — the same loader the standard
``Evaluator`` and ``PriorityPassAnalysis`` are built on.

Controllers whose vehicle log distinguishes prioritized vehicles (``priority`` field
not always ``0``) are split into "prioritized" / "non-prioritized" series; other
controllers are plotted as a single aggregate line. Configs whose log file is
missing are skipped with a printed notice rather than failing the whole comparison.

Example usage (CLI)::

    python src/post_processing/vehicle_count_comparison.py \\
        configurations/demo_sumo_baseline_config.json \\
        configurations/demo_sumo_fixed_cycle_config.json \\
        configurations/demo_sumo_max_pressure_config.json \\
        configurations/demo_sumo_priority_pass_config.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from evaluation.loader import VehicleLogLoader


def load_controller(config_file: str) -> tuple[str, str, list[dict[str, Any]] | None]:
    """Load vehicle records for one scenario config.

    Args:
        config_file: Path to a JSON scenario config.

    Returns:
        ``(scenario, logic_module_name, vehicle_records)``; ``vehicle_records`` is
        ``None`` when ``vehicle_log.jsonl`` does not exist for this config.
    """
    with Path(config_file).open("r", encoding="utf-8") as f:
        config = json.load(f)

    scenario = str(config["scenario"])
    logic_modules = list(config.get("logic_modules", []))
    logic_module_name = str(logic_modules[0]["type"]) if logic_modules else "baseline"
    log_path = Path(config["recorder"]["logs_dir"]) / "vehicle_log.jsonl"

    try:
        _, vehicle_records = VehicleLogLoader(log_path).load()
    except FileNotFoundError:
        print(f"No data available for '{logic_module_name}' ({log_path}) — skipping.")
        return scenario, logic_module_name, None

    return scenario, logic_module_name, vehicle_records


def plot_vehicle_counts_comparison(
    controllers: dict[str, list[dict[str, Any]]], output_path: Path
) -> None:
    """Save an overlaid cumulative vehicle count plot for all given controllers.

    Args:
        controllers: Mapping of logic module name to its vehicle records.
        output_path: Destination PNG file path.
    """
    _, ax = plt.subplots(figsize=(12, 6))

    for logic_module_name, records in controllers.items():
        groups = (
            [("", records)]
            if all(rec["priority"] == 0 for rec in records)
            else [
                (" (non-prioritized)", [r for r in records if r["priority"] == 0]),
                (" (prioritized)", [r for r in records if r["priority"] != 0]),
            ]
        )
        for label_suffix, group in groups:
            if not group:
                continue
            sorted_group = sorted(group, key=lambda r: r["departure"])
            times = [r["departure"] for r in sorted_group]
            counts = list(range(1, len(times) + 1))
            ax.plot(
                times, counts, label=f"{logic_module_name}{label_suffix}", linewidth=2
            )

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Number of Vehicles")
    ax.set_title("Cumulative Vehicle Count Comparison Across Controllers")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    print(f"Saved plot to {output_path}")
    plt.close()


def main() -> None:
    """CLI entry point: compare vehicle counts over time across several configs."""
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print(
            "Usage: python src/post_processing/vehicle_count_comparison.py"
            " CONFIG_FILE [CONFIG_FILE ...]"
        )
        print("  CONFIG_FILE: one or more scenario JSON configs to compare, e.g.")
        print(
            "               demo_sumo_baseline_config.json demo_sumo_fixed_cycle_config.json"
        )
        print(
            "               demo_sumo_max_pressure_config.json"
            " demo_sumo_priority_pass_config.json"
        )
        sys.exit(0)

    controllers: dict[str, list[dict[str, Any]]] = {}
    scenario = None
    for config_file in args:
        config_scenario, logic_module_name, records = load_controller(config_file)
        if records is not None:
            controllers[logic_module_name] = records
            scenario = scenario or config_scenario

    if not controllers:
        print("No controller data found for any of the given configs.")
        return

    output_path = Path("results") / str(scenario) / "vehicle_counts_comparison.png"
    plot_vehicle_counts_comparison(controllers, output_path)


if __name__ == "__main__":
    main()
