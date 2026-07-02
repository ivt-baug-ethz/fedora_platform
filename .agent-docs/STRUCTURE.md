# FEDORA Platform - Directory Structure

```
fedora_platform/
├── src/                           – Core application components (TCP FSM controllers)
│   ├── environment_sumo.py        – SUMO/TraCI environment FSM, vehicle spawning, queue metrics
│   ├── controller_fixed_cycle.py  – Fixed-cycle traffic light controller FSM
│   ├── controller_max_pressure.py – Max-pressure auction controller FSM
│   ├── controller_priority_pass.py – Priority Pass (Vienna pilot) controller FSM
│   ├── orchestrator.py               – TCP JSON-line message router FSM and platform orchestrator
│   ├── recorder.py                – TCP communication logger FSM
│   ├── evaluation/                – Standard evaluation package (VKT, VHT, flow, density, speed)
│   │   ├── __init__.py            – Re-exports Evaluator and EvaluationConfig
│   │   ├── config.py              – EvaluationConfig dataclass and metric allowlist
│   │   ├── loader.py              – VehicleLogLoader: parse vehicle_log.jsonl
│   │   ├── metrics.py             – MetricsComputer: pure metric computation
│   │   ├── plots.py               – PlotGenerator: aggregate standard plots
│   │   └── evaluator.py           – Evaluator facade (wires loader → metrics → plots)
│   └── post_processing/           – Controller-specific post-processing scripts (manual, not part of pipeline)
│       ├── __init__.py
│       ├── priority_pass_analysis.py  – PriorityPassAnalysis: priority vs. regular vehicle
│       │                                 breakdown; runnable directly as a CLI script
│       └── vehicle_count_comparison.py – Overlays cumulative vehicle count over time for
│                                          multiple controllers on one plot; CLI script
│
├── run.py                         – Thin entry point: parses CLI args, starts Orchestrator, runs Evaluator
│
├── tests/                         – Unit and integration tests
│   ├── test_controllers.py        – Controller FSMs, auctions, config parity tests
│   ├── test_evaluator.py          – Evaluator end-to-end tests
│   ├── test_loader.py             – VehicleLogLoader unit tests
│   ├── test_metrics.py            – MetricsComputer unit tests
│   ├── test_evaluation_config.py  – EvaluationConfig unit tests
│   └── test_recorder.py           – Recorder FSM and TCP logging tests
│
├── configurations/                – Scenario configuration files (named: {scenario}_sumo_{controller}_config.json)
│   ├── demo_sumo_baseline_config.json        – Demo: no controller (SUMO default signal plans); logic_modules: []
│   ├── demo_sumo_fixed_cycle_config.json     – Demo: configurable fixed-cycle controller
│   ├── demo_sumo_max_pressure_config.json    – Demo: max-pressure controller
│   ├── demo_sumo_priority_pass_config.json   – Demo: priority-pass controller (default)
│   ├── vienna_sumo_baseline_config.json      – Vienna: no controller (SUMO default signal plans); logic_modules: []
│   ├── vienna_sumo_fixed_cycle_config.json   – Vienna: configurable fixed-cycle controller
│   ├── vienna_sumo_max_pressure_config.json  – Vienna: max-pressure controller
│   └── vienna_sumo_priority_pass_config.json – Vienna: priority-pass controller
│
├── scenarios/                     – Scenario-specific SUMO files and metadata
│   ├── demo/
│   │   └── sumo/                  – SUMO network, demand, and phase files for demo
│   │       ├── config.sumocfg     – SUMO configuration
│   │       ├── network.net.xml    – SUMO network definition
│   │       ├── demand.xml         – Vehicle route definitions
│   │       ├── phase_inc_lanes.json    – Per-phase incoming lanes
│   │       ├── route_*.json       – Route metadata (distances, durations, etc.)
│   │       └── possible_trips.xml – Trip source data
│   ├── pilot_vienna/              – Vienna pilot scenario skeleton
│   ├── pilot_basque_country/      – Basque Country pilot scenario skeleton
│   ├── pilot_nicosia/             – Nicosia pilot scenario skeleton
│   ├── pilot_copenhagen/          – Copenhagen pilot scenario skeleton
│   ├── pilot_reggio_emilia/       – Reggio Emilia pilot scenario skeleton
│   └── pilot_budapest/            – Budapest pilot scenario skeleton
│
├── logs/                          – Generated simulation logs
│   ├── .gitkeep                   – Marker for git
│   ├── demo_priority_pass/        – Demo priority pass run logs
│   │   ├── communication_log.txt  – All inter-component messages
│   │   └── vehicle_log.jsonl      – Vehicle arrival/departure events
│   └── {scenario}_{logic_module}/   – Logs from other scenario/controller combinations
│
├── results/                        – Evaluation results (auto-generated, .gitignored)
│   ├── demo/
│   │   ├── priority_pass/         – Priority pass evaluation
│   │   │   ├── travel_time_distribution.png
│   │   │   ├── average_travel_time.png
│   │   │   ├── vehicle_counts.png
│   │   │   ├── evaluation_stats.json
│   │   │   ├── pp_travel_time_distribution.png  (from post_processing, if run)
│   │   │   ├── pp_average_travel_time.png       (from post_processing, if run)
│   │   │   ├── pp_vehicle_counts.png            (from post_processing, if run)
│   │   │   └── pp_analysis_stats.json           (from post_processing, if run)
│   │   ├── max_pressure/
│   │   └── fixed_cycle/
│   ├── vienna/
│   │   ├── priority_pass/
│   │   ├── max_pressure/
│   │   └── fixed_cycle/
│   └── {scenario}/{logic_module}/   – Evaluation output structure
│
├── .agent-docs/                   – LLM-maintained documentation (MANDATORY)
│   ├── STRUCTURE.md               – This file (directory tree and responsibilities)
│   ├── DECISIONS.md               – Architectural Decision Records (ADRs)
│   ├── INTEGRATIONS.md            – External tool integrations and setup
│   └── scratchpad.md              – Per-session working memory and progress
│
├── docs/                          – User-facing MkDocs documentation (deployed to GitHub Pages)
│   ├── index.md                   – Home page
│   ├── getting-started.md         – Installation and running scenarios
│   ├── architecture.md            – Architecture overview and diagrams
│   ├── components.md              – Component reference
│   ├── evaluation.md              – Evaluation metrics, configuration, and post-processing
│   └── configuration.md          – Configuration reference
│
├── mkdocs.yml                     – MkDocs + Material configuration
│
├── .memory-bank/                  – Persistent project context (read/update every session)
│   ├── projectbrief.md            – Project scope and goals (read-only)
│   ├── systemPatterns.md          – Architecture and design patterns
│   ├── techContext.md             – Technical environment and dependencies
│   ├── activeContext.md           – Current focus and recent changes
│   ├── progress.md                – Implementation status and test coverage
│   └── productContext.md          – Product goals and success criteria
│
├── figures/                       – Pilot images and repository banner
│
├── .github/                       – GitHub-specific files
│   └── workflows/                 – GitHub Actions CI/CD workflows
│       ├── docs.yml               – Deploy MkDocs documentation to GitHub Pages
│       ├── lint.yml               – Pylint code quality check
│       ├── python_testing.yml     – pytest test suite
│       └── format_check.yml       – Code formatting check
│
├── venv/                          – Python virtual environment (auto-created)
│
├── requirements.txt               – Pinned Python dependencies
├── pyproject.toml                 – Python project metadata
├── .pylintrc                      – Pylint configuration and rules
├── .gitignore                     – Git ignore patterns
├── README.md                      – Project overview and getting started
├── AGENTS.md                      – Complete agent instructions (MANDATORY READ)
├── CLAUDE.md                      – Quick reference for Claude Code (this documentation)
└── LICENSE                        – Project license
```

## Module Responsibilities

### Core Application Components (`src/`)

**environment_sumo.py**

- Implements the `sumo` environment type: manages SUMO/TraCI connection lifecycle
- Passive step loop: waits for `"step"` message from Orchestrator before each iteration; does not drive itself
- Spawns vehicles, reads traffic state, and applies traffic light commands via `"apply_and_advance"` messages
- Accepts `lane_measurements_enabled` list from Orchestrator (populated from logic module requirements) — no measurement config needed in JSON
- Implements FSM lifecycle (CREATED → CONFIGURED → READY → RUNNING → STOPPED); `NAME = "environment"`
- Publishes traffic metrics (queue lengths, vehicle positions) as JSON messages over TCP

**orchestrator.py**

- **Platform orchestrator**: reads the full JSON configuration and creates Recorder, LogicModule, and Environment internally
- Routes JSON-line TCP messages between application components
- Drives the environment step loop by intercepting `environment_started`, `logic_command`, and `environment_stopped` topics
- Sends `"step"` and `"apply_and_advance"` commands to Environment to control each iteration
- Queries each logic module's `get_required_measurements()` to determine which metrics the Environment should collect; no user configuration of measurement types needed
- Mirrors all traffic for logging to Recorder component
- Supports pluggable environment types via `_ENVIRONMENT_TYPES` dict (currently: `"sumo"`)

**controller_fixed_cycle.py**

- Implements the configurable fixed-cycle controller (distinct from the baseline which uses SUMO's built-in plans)
- Receives traffic state, advances per-intersection cycle timers, sends phase commands back
- Phase durations, transition (amber) duration, and per-intersection startup offsets are fully configurable
- Implements FSM for controller state transitions

**controller_max_pressure.py**

- Implements max-pressure-based auction algorithm
- Receives traffic state, computes pressure (queue length difference) per movement
- Selects movement with highest pressure, implements auction mechanism
- Implements FSM for controller state transitions

**controller_priority_pass.py**

- Implements Vienna Priority Pass optimization algorithm
- Receives traffic state and priority vehicle information
- Optimizes phase sequence considering both traffic efficiency and transit priority
- Shares Max-Pressure auction timing; with `trade_off = 0.0`, UPP bids are ignored and the phase sequence should match Max-Pressure for the same measurements and random seed
- Implements FSM for controller state transitions

**recorder.py**

- Listens on dedicated TCP port for message copies from Orchestrator
- Logs all inter-component communication (traffic, commands, state) to text files
- Writes logs to `logs/` directory for post-simulation analysis
- Implements FSM for recorder state transitions

**evaluation/ (package)**

- `config.py`: `EvaluationConfig` dataclass — which metrics to compute and whether to run; `from_dict()` validates metric names against `ALL_METRICS`
- `loader.py`: `VehicleLogLoader` — reads `vehicle_log.jsonl`, returns `(run_meta, vehicle_records)` with only completed vehicles (both arrival and departure timestamps)
- `metrics.py`: `MetricsComputer` — pure, I/O-free computation of VKT, VHT, flow, space-mean speed, density, travel time mean/median/min/max/variance; missing data (e.g. no `route_distance_m`) yields `None` rather than raising
- `plots.py`: `PlotGenerator` — three aggregate plots (no priority/group split): travel time histogram, cumulative vehicle count, cumulative average travel time
- `evaluator.py`: `Evaluator` — facade that wires loader → metrics → plots → writes `evaluation_stats.json`

**src/post_processing/priority_pass_analysis.py**

- `PriorityPassAnalysis` — manual post-processing script for Priority Pass runs
- Reads `vehicle_log.jsonl` and splits vehicles into regular (priority=0) vs. priority (priority=1) groups
- Computes per-group travel time statistics and generates per-group plots
- Not part of the standard evaluation pipeline; run manually after collecting PP logs
- Has a `main()` CLI entry point: `python src/post_processing/priority_pass_analysis.py CONFIG_FILE`
  derives `logs_dir` from `config["recorder"]["logs_dir"]` and writes to
  `results/{scenario}/{logic_module}/` — the same directory as the standard evaluation output;
  `pp_`-prefixed filenames avoid collisions — mirroring `run.py`'s config-driven pattern

**src/post_processing/vehicle_count_comparison.py**

- Cross-controller post-processing: overlays cumulative vehicle count over time for several
  logic modules (e.g. baseline, fixed-cycle, max-pressure, priority-pass) on one plot
- Reuses `VehicleLogLoader` from `src/evaluation/loader.py` (controller-agnostic, already
  returns the `priority` field) instead of re-parsing `vehicle_log.jsonl`
- `main()` CLI entry point accepts multiple `CONFIG_FILE` arguments (one per controller);
  configs whose `vehicle_log.jsonl` is missing are skipped with a printed notice rather than
  failing the whole comparison
- A controller is split into "prioritized"/"non-prioritized" series only when its own vehicle
  records actually contain a non-zero `priority` value (data-driven, not keyed off the
  controller's type name); otherwise it is plotted as a single aggregate line
- Output: `results/{scenario}/vehicle_counts_comparison.png` (scenario taken from the first
  config whose log data was found)

### Entry Points

**run.py**

- Thin entry point: parses CLI arguments (`CONFIG_FILE`, `--skip-evaluation`, `--headless`)
- Creates an `Orchestrator` with the full config dict and calls `start()` / `wait_until_done()`
- Reads `config["evaluation"]` block and constructs `EvaluationConfig` to control which metrics run
- Runs the `Evaluator` after the environment run completes unless `evaluation.enabled` is false or `--skip-evaluation` is passed (CLI flag overrides config)
- All component lifecycle management is handled by the Orchestrator internally

**src/post_processing/priority_pass_analysis.py**

- Secondary entry point, run manually and separately from `run.py` (not invoked automatically)
- `main()` parses a single `CONFIG_FILE` argument, derives `logs_dir`/`output_dir` the same way
  `run.py` does, and runs `PriorityPassAnalysis`

### Structural Rules

1. **All code in `src/` must be importable** — No absolute paths, all paths relative to project root
2. **One class per file** (in `src/`) — Makes imports clear and single-responsibility explicit
3. **No external scripts in `src/`** — Entry points live at root level (e.g., `run.py`)
4. **Scenario-specific files in `scenarios/`** — SUMO network, demand, and metadata organized by scenario
5. **Configuration in `configurations/`** — All runtime settings loaded from JSON, no hardcoding
6. **Tests at root-level `tests/`** — Central location for all unit and integration tests
