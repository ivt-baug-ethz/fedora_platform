# Getting Started

## Requirements

- **Python 3.13** (required)
- **SUMO 1.19.0+** (for simulation scenarios)
  - macOS: `brew install sumo`
  - Linux: install via package manager or from [sumo.dlr.de](https://sumo.dlr.de)
  - Ensure `sumo` or `sumo-gui` is on PATH, or set the `SUMO_HOME` environment variable

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/sjschlapbach/fedora_platform.git
   cd fedora_platform
   ```

2. Create and activate a virtual environment:

   ```bash
   python3.13 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Verify the setup:
   ```bash
   pytest tests/ -v
   ```

## Running a Scenario

Each control strategy has its own configuration file. The naming convention is `{scenario}_sumo_{logic_module}_config.json`.

### Demo Scenario

```bash
# Baseline — no controller, SUMO default signal plans (performance reference)
python run.py configurations/demo_sumo_baseline_config.json

# Configurable Fixed-Cycle
python run.py configurations/demo_sumo_fixed_cycle_config.json

# Max-Pressure
python run.py configurations/demo_sumo_max_pressure_config.json

# Urban Priority Pass (default)
python run.py configurations/demo_sumo_priority_pass_config.json

# Urban Priority Pass — all state fields logged (diagnostic / validation run)
python run.py configurations/demo_sumo_priority_pass_full_state_config.json

# Shorthand for the default (priority-pass demo)
python run.py
```

### Vienna Pilot Scenario

```bash
# Baseline — no controller, SUMO default signal plans (performance reference)
python run.py configurations/vienna_sumo_baseline_config.json

# Configurable Fixed-Cycle, Max-Pressure, Urban Priority Pass
python run.py configurations/vienna_sumo_fixed_cycle_config.json
python run.py configurations/vienna_sumo_max_pressure_config.json
python run.py configurations/vienna_sumo_priority_pass_config.json
```

### Options

```bash
python run.py --help                          # list all options
python run.py <config> --skip-evaluation      # skip post-run evaluation plots
python run.py <config> --headless             # use headless SUMO binary (no GUI); required
                                              # for CI and server environments
python run.py <config> --headless --skip-evaluation  # CI-style run without evaluation visualizations
```

The `--headless` flag switches to the `binary_headless` value in `environment.settings` (defaults to `sumo` if absent), bypassing the GUI-based `binary` entry. All provided configuration files already include `"binary_headless": "sumo"`.

## Output

| Path                                                             | Contents                         |
| ---------------------------------------------------------------- | -------------------------------- |
| `logs/{scenario}_{logic_module}/communication_log.txt`           | All inter-component TCP messages |
| `logs/{scenario}_{logic_module}/vehicle_log.jsonl`               | Vehicle arrival/departure events (with `route_distance_m` per vehicle and `total_lane_length_m` in the run header) |
| `results/{scenario}/{logic_module}/travel_time_distribution.png` | Travel time histogram (aggregate) |
| `results/{scenario}/{logic_module}/average_travel_time.png`      | Cumulative average travel time   |
| `results/{scenario}/{logic_module}/vehicle_counts.png`           | Total vehicle count over time    |
| `results/{scenario}/{logic_module}/evaluation_stats.json`        | Standard metrics: travel time stats, VHT, VKT, flow, speed, density, travel time variance |

See [Evaluation](evaluation.md) for a description of all computed metrics and how to configure or disable evaluation.
