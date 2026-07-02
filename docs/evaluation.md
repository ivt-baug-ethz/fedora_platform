# Evaluation

The FEDORA Platform includes a built-in evaluation pipeline that runs automatically after each
environment run and computes standard traffic-engineering metrics from the recorded vehicle log.
It is agnostic to the underlying environment implementation — simulation-based (e.g. SUMO) or a
real-world pilot deployment — as long as the environment writes vehicle events in the expected
log format.

---

## Overview

After the environment run completes, `run.py` instantiates an `Evaluator` (from `src/evaluation/`)
that:

1. Reads `vehicle_log.jsonl` from the configured `logs_dir`
2. Computes all enabled standard metrics
3. Saves three plots to the output directory
4. Writes a `evaluation_stats.json` summary file

Output is written to `results/{scenario}/{logic_module_type}/`.

---

## Enabling and Disabling

Evaluation is controlled by the `evaluation` block in the JSON scenario config:

```json
"evaluation": {
  "enabled": true,
  "metrics": []
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | Run evaluation after the environment run. |
| `metrics` | array of strings | `[]` | Allowlist of metrics to compute. An empty list enables **all** standard metrics. |

The `--skip-evaluation` CLI flag always overrides `enabled`, setting it to `false` regardless of
the config:

```bash
python run.py configurations/demo_sumo_baseline_config.json --skip-evaluation
```

---

## Standard Metrics

All metrics are aggregate (controller-agnostic). They do not distinguish between vehicle types
or priority classes — see [Post-Processing](#post-processing) for per-group analysis.

| Metric key | Description | Formula | Unit | Data requirement |
|---|---|---|---|---|
| `overall_avg_travel_time` | Mean vehicle travel time | mean(departure − arrival) | s | Always |
| `overall_median_travel_time` | Median vehicle travel time | median(travel times) | s | Always |
| `overall_min_travel_time` | Fastest observed trip | min(travel times) | s | Always |
| `overall_max_travel_time` | Slowest observed trip | max(travel times) | s | Always |
| `travel_time_variance` | Travel time spread | sample variance(travel times) | s² | ≥ 2 vehicles |
| `vht` | Vehicle Hours Traveled | sum(travel times) / 3600 | veh·h | — |
| `vkt` | Vehicle Kilometers Traveled | sum(route distances) / 1000 | veh·km | Route distances in log |
| `flow` | Aggregate traffic flow | vehicles / run\_duration\_h | veh/h | — |
| `space_mean_speed` | Space-mean speed | VKT / VHT | km/h | VKT available |
| `density` | Average network density | VHT / (duration\_h × road\_length\_km) | veh/km | Network length in log |

### Metric Allowlist

To compute only a subset of metrics, list them explicitly in the config:

```json
"evaluation": {
  "enabled": true,
  "metrics": ["travel_time", "vht", "flow"]
}
```

Valid metric names: `travel_time`, `travel_time_variance`, `vht`, `vkt`, `flow`, `speed`,
`density`.

---

## Data Dependencies

Some metrics require additional data in `vehicle_log.jsonl` that the environment implementation
must populate:

- **`vkt` and `space_mean_speed`** require `route_distance_m` in departure events.  
  Written by the environment when a vehicle exits, based on the distance it travelled through
  the network. The bundled SUMO environment (`src/environment_sumo.py`) queries this from TraCI
  at vehicle arrival, while the route is still resolvable, and caches it until departure. Logs
  produced before this feature was added, or written by an environment that does not populate
  this field, will yield `null` for these metrics.

- **`density`** requires `total_lane_length_m` in the `run_meta` header.  
  Written at run start from the environment's road network length. In the bundled SUMO
  environment, only road lanes are counted; internal junction lanes (IDs starting with `:`) are
  excluded. Any other environment implementation that wants this metric must populate the same
  field in `run_meta`.

When required data is absent, the affected metric key is present in `evaluation_stats.json` but
set to `null`. No error is raised.

---

## Output Files

All outputs are written to `results/{scenario}/{logic_module_type}/`:

| File | Description |
|---|---|
| `evaluation_stats.json` | All computed metrics as a flat JSON object |
| `travel_time_distribution.png` | Histogram of all vehicle travel times |
| `average_travel_time.png` | Cumulative average travel time over run time |
| `vehicle_counts.png` | Cumulative completed vehicle count over run time |

---

## Post-Processing

### Controller-Specific Analysis

Some analyses are specific to a particular controller and are not part of the standard
evaluation pipeline. These live in the `post_processing/` directory at the repository root and
are run manually after collecting logs.

**Available post-processing scripts:**

| Script | Controller | Description |
|---|---|---|
| `post_processing/priority_pass_analysis.py` | Priority Pass | Priority vs. regular vehicle comparison (travel time, counts, averages per group) |

Example — run Priority Pass analysis on an existing log:

```python
from pathlib import Path
from post_processing.priority_pass_analysis import PriorityPassAnalysis

analysis = PriorityPassAnalysis(
    logs_dir=Path("logs/demo_priority_pass"),
    output_dir=Path("results/demo/controller_priority_pass/pp_analysis"),
)
analysis.run()
```

Output: `pp_analysis_stats.json` and three per-group plots in the specified `output_dir`.

### Custom Post-Processing

`vehicle_log.jsonl` is a plain JSONL file (one JSON object per line) that can be consumed by
any script or tool. The format is:

```json
{"type": "run_meta", "scenario": "demo", "total_lane_length_m": 12847.3, ...}
{"vehicle_id": "v_42", "event_type": "arrival", "time": 134.0, "priority": 0}
{"vehicle_id": "v_42", "event_type": "departure", "time": 178.0, "priority": 0, "route_distance_m": 763.4}
```

`evaluation_stats.json` is a flat JSON object with all computed metric values and can be read
directly by Python, R, Julia, or any data analysis tool.

### Controller Comparison

Comparison of different controllers (e.g., Max-Pressure vs. Priority Pass) is not provided as
a built-in pipeline feature, but can be implemented straightforwardly as a custom
post-processing script that reads `evaluation_stats.json` or `vehicle_log.jsonl` from multiple
runs and compares the results.
