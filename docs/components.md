# Components

## Orchestrator (`src/orchestrator.py`)

The sole orchestrator of the platform. It reads the full JSON configuration, creates all sub-components (Recorder, Logic Modules, Environment), drives the step loop, and routes messages between components.

**Responsibilities:**

- Instantiate and lifecycle-manage all other components
- Drive the `step` / `apply_and_advance` loop
- Fan-out environment state observations to all Logic Modules simultaneously
- Merge `logic_command` responses and forward the combined command to the Environment
- Mirror all traffic to the Recorder
- Query each Logic Module's measurement requirements and pass them to the Environment
- After each step, optionally poll components for internal state (`get_state` → `state_report`) and forward the reports to the Recorder — activated automatically when at least one state attribute is enabled in the recorder config

## Environment Layer

The environment layer is the **pluggable execution backend** of the platform. It produces state observations (`traffic_state`) and applies the merged commands received via `apply_and_advance`. Any implementation that respects this two-message contract can serve as the environment — the Orchestrator, Logic Modules, and Recorder are fully unaware of what is running behind it.

Concrete backends can include:

- **Microsimulations** (e.g. SUMO/TraCI, VISSIM, Aimsun) — run in headless mode for batch experiments or with a GUI for interactive inspection
- **Mesoscopic or macroscopic models** — suitable for network-wide or long-horizon studies where per-vehicle fidelity is not required
- **Hardware-in-the-loop testbeds** — where physical signal controllers or sensor arrays feed real measurements into the pipeline
- **Live pilot deployment sites** — field deployments where a thin field interface translates sensor readings and command outputs into the platform's message format

The only requirement is that the environment can provide the state fields requested by the active Logic Modules (declared via `get_required_measurements()`) and can accept the command type returned by those modules.

### Environment for Demonstrator: SUMO (`src/environment_sumo.py`)

Implements the `"sumo"` environment type using SUMO/TraCI. Manages the SUMO process lifecycle, the TraCI connection, and vehicle spawning via configurable demand models.

**Responsibilities:**

- Connect to SUMO via TraCI
- Wait passively for `step` messages before each iteration
- Collect queue lengths, vehicle positions, and signal states
- Apply commands received via `apply_and_advance`
- Spawn vehicles and manage simulation time

**Configuration key:** `"type": "sumo"` in the `"environment"` config block.

## Logic Modules

A logic module is any pluggable component that receives environment state observations (`traffic_state`) and returns a command dict (`logic_command`) each step. The interface is intentionally general: a module can implement a signal controller, a demand model, a pricing engine, a data logger, or any other decision-making or processing component that consumes environment observations and produces (possibly empty) commands.

Multiple modules can be listed in the `"logic_modules"` array; the Orchestrator fans the state out to all of them simultaneously and merges their command outputs before forwarding to the environment. The union of all modules' measurement requirements is collected automatically — no manual configuration of enabled measurements is needed.

Setting `"logic_modules": []` activates **baseline mode**: the Orchestrator immediately sends an empty `apply_and_advance` each step, leaving the environment's own default behaviour untouched (for SUMO, this means the built-in signal plans run unmodified). Use baseline runs as the performance reference for comparing active logic modules.

### Example Implementations in This Demonstrator

This repository demonstrates the framework in the context of traffic signal control. The three logic modules included here are all signal controllers — concrete examples of one possible use of the logic module slot. Any other decision-making or data-processing component that respects the `traffic_state` → `logic_command` interface (e.g. a demand model, a pricing engine, or a reinforcement-learning agent) could be plugged in instead, without changes to the Orchestrator, Environment, or Recorder.

#### Configurable Fixed-Cycle (`src/controller_fixed_cycle.py`)

User-defined pre-timed phase schedules with configurable per-phase green durations, transition (amber) duration, and per-intersection startup time offsets. Unlike the baseline, all phase timings are explicitly set in the configuration rather than inherited from the environment's defaults. Simple and predictable; cannot adapt to demand changes.

#### Max-Pressure (`src/controller_max_pressure.py`)

Real-time responsive control based on queue pressure (difference in queue lengths at opposing approaches). Uses an auction mechanism to select the highest-pressure phase each step. Adapts to demand but may be unstable under high congestion.

#### Urban Priority Pass (`src/controller_priority_pass.py`)

Extends Max-Pressure with a priority bidding mechanism for designated vehicles (e.g. public transit). Balances network-wide efficiency with transit reliability via a configurable trade-off parameter.

Priority Pass intentionally shares the same auction FSM timing parameters as Max-Pressure. At `trade_off = 0.0`, the combined bid is exactly the queue-length bid, so the controller should produce the same phase sequence as Max-Pressure for the same measurements and random seed. Values above zero gradually add UPP bids to the auction and are the intended prioritisation experiment.

## Recorder (`src/recorder.py`)

Listens on a dedicated TCP port for message copies forwarded by the Orchestrator. Writes inter-component communication and (optionally) per-step component state snapshots to log files for post-run analysis.

The Recorder is only instantiated when a `"recorder"` port is present in `communication.ports`. If the port is omitted, no log files are created and the simulation runs at minimum overhead.

**Output:**

- `logs/{run_label}/communication_log.txt` — inter-component messages (first line is always a `run_meta` record describing the run)
- `logs/{run_label}/vehicle_log.jsonl` — vehicle arrival/departure events (when `vehicle_log_enabled: true`)

**Configurable logging:**

- **Topic filter** (`topics`): an allowlist of message topics to record. Leave empty to capture all traffic; set to a non-empty list (e.g. `["traffic_state", "logic_command"]`) to reduce log volume.
- **Vehicle log** (`vehicle_log_enabled`): disabling this skips `vehicle_log.jsonl` and suppresses the post-run Evaluator.
- **State polling**: when the Orchestrator polls component state, the resulting `state_report` messages are forwarded to the Recorder and subject to the same topic filter. Enable specific state fields in the `recorder.state_polling` config to capture them — no changes to recorder configuration are needed beyond setting the desired attributes to `true`.

## Evaluation (`src/evaluation/`)

Post-run analysis package. Reads `vehicle_log.jsonl` and computes standard traffic-engineering
metrics. All metrics are agnostic aggregates with respect to the connected logic components —
they do not split results by vehicle priority class or controller type.

**Package structure:**

| Module                    | Responsibility                                                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `evaluation/config.py`    | `EvaluationConfig` dataclass — which metrics to compute and whether to run                                     |
| `evaluation/loader.py`    | `VehicleLogLoader` — parses `vehicle_log.jsonl` into per-vehicle records                                       |
| `evaluation/metrics.py`   | `MetricsComputer` — pure computation of all standard metrics (VKT, VHT, flow, density, speed, travel time variance) |
| `evaluation/plots.py`     | `PlotGenerator` — three aggregate plots (histogram, cumulative count, cumulative average travel time)          |
| `evaluation/evaluator.py` | `Evaluator` — facade that wires the above into a single `evaluate_and_report()` call                           |

**Output:** `results/{scenario}/{logic_module}/` — three PNGs + `evaluation_stats.json`.

**Configuration:** controlled by the `evaluation` block in the JSON config (`enabled`, `metrics`).
See the [Evaluation](evaluation.md) page for full details.

**Post-processing:** Controller-specific or cross-controller analysis (e.g. Priority Pass
priority vs. regular vehicle breakdown, or vehicle count comparison across several logic
modules) lives in `src/post_processing/` and is run manually.
See [Post-Processing](evaluation.md#post-processing).

## Entry Points

| Script                                             | Purpose                                                                                         |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `run.py`                                            | Main entry point: parses CLI args, starts Orchestrator, runs Evaluator after the run completes  |
| `src/post_processing/priority_pass_analysis.py`     | Manual post-processing: Priority Pass priority vs. regular vehicle breakdown (see above)         |
| `src/post_processing/vehicle_count_comparison.py`   | Manual post-processing: overlays cumulative vehicle count across multiple controllers            |
