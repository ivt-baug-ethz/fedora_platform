# FEDORA Platform - Directory Structure

```
fedora_platform/
├── src/                           – Core application components (TCP FSM controllers)
│   ├── simulation_sumo.py         – SUMO/TraCI FSM, vehicle spawning, queue metrics
│   ├── controller_fixed_cycle.py  – Fixed-cycle traffic light controller FSM
│   ├── controller_max_pressure.py – Max-pressure auction controller FSM
│   ├── controller_priority_pass.py – Priority Pass (Vienna pilot) controller FSM
│   ├── orchestrator.py               – TCP JSON-line message router FSM and platform orchestrator
│   ├── recorder.py                – TCP communication logger FSM
│   └── evaluator.py               – Evaluation component for delay analysis and visualization
│
├── run.py                         – Thin entry point: parses CLI args and starts the Orchestrator
├── evaluate.py                    – Standalone script to evaluate simulation results
│
├── tests/                         – Unit and integration tests
│   ├── test_core.py               – Core component lifecycle and message bus tests
│   ├── test_priority_pass.py      – Priority Pass and SUMO adapter tests
│   └── __pycache__/               – pytest cache (auto-generated)
│
├── configurations/                – Scenario configuration files (named: {scenario}_sumo_{controller}_config.json)
│   ├── demo_sumo_fixed_cycle_config.json     – Demo: fixed-cycle controller
│   ├── demo_sumo_max_pressure_config.json    – Demo: max-pressure controller
│   ├── demo_sumo_priority_pass_config.json   – Demo: priority-pass controller (default)
│   ├── vienna_sumo_fixed_cycle_config.json   – Vienna: fixed-cycle controller
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
│   │   │   ├── delay_distribution.png
│   │   │   ├── cumulative_delay.png
│   │   │   └── evaluation_stats.json
│   │   ├── max_pressure/
│   │   └── fixed_cycle/
│   ├── vienna/
│   │   ├── priority_pass/
│   │   ├── max_pressure/
│   │   └── fixed_cycle/
│   └── {scenario}/{logic_module}/   – Evaluation output structure
│
├── docs/                          – LLM-maintained documentation (MANDATORY)
│   ├── STRUCTURE.md               – This file (directory tree and responsibilities)
│   ├── DECISIONS.md               – Architectural Decision Records (ADRs)
│   ├── INTEGRATIONS.md            – External tool integrations and setup
│   └── scratchpad.md              – Per-session working memory and progress
│
├── memory-bank/                   – Persistent project context (read/update every session)
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

**simulation_sumo.py**

- Manages SUMO/TraCI connection lifecycle
- Passive step loop: waits for `"step"` message from Orchestrator before each iteration; does not drive itself
- Spawns vehicles, reads traffic state, and applies traffic light commands via `"apply_and_advance"` messages
- Accepts `lane_measurements_enabled` list from Orchestrator (populated from logic module requirements) — no measurement config needed in JSON
- Implements FSM for simulation control flow (CREATED → CONFIGURED → READY → RUNNING → STOPPED)
- Publishes traffic metrics (queue lengths, vehicle positions) as JSON messages over TCP

**orchestrator.py**

- **Platform orchestrator**: reads the full JSON configuration and creates Recorder, LogicModule, and Simulation internally
- Routes JSON-line TCP messages between application components
- Drives the simulation step loop by intercepting `simulation_started`, `traffic_light_command`, and `simulation_stopped` topics
- Sends `"step"` and `"apply_and_advance"` commands to Simulation to control each iteration
- Queries each logic module's `get_required_measurements()` to determine which metrics the Simulation should collect; no user configuration of measurement types needed
- Mirrors all traffic for logging to Recorder component

**controller_fixed_cycle.py**

- Implements fixed-cycle traffic light control
- Receives traffic state from Simulation, computes phase duration, sends commands back
- Uses simple cycle timing (e.g., 60s cycle: 30s green north/south, 30s green east/west)
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
- Implements FSM for controller state transitions

**recorder.py**

- Listens on dedicated TCP port for message copies from Orchestrator
- Logs all inter-component communication (traffic, commands, state) to text files
- Writes logs to `logs/` directory for post-simulation analysis
- Implements FSM for recorder state transitions

**evaluator.py**

- Post-simulation analysis component for evaluating performance
- Reads vehicle event logs (arrivals/departures) from simulation
- Calculates vehicle delays and separates metrics by priority status
- Generates visualizations: delay distributions and cumulative delay over time
- Exports evaluation statistics to JSON for further analysis

### Entry Points

**run.py**

- Thin entry point (~70 lines): parses CLI arguments (`CONFIG_FILE`, `--skip-evaluation`)
- Creates a `Orchestrator` with the full config dict and calls `start()` / `wait_until_done()`
- Runs the `Evaluator` after the simulation completes (unless `--skip-evaluation` is passed)
- All component lifecycle management is handled by the Orchestrator internally

### Structural Rules

1. **All code in `src/` must be importable** — No absolute paths, all paths relative to project root
2. **One class per file** (in `src/`) — Makes imports clear and single-responsibility explicit
3. **No external scripts in `src/`** — Entry points live at root level (e.g., `run.py`)
4. **Scenario-specific files in `scenarios/`** — SUMO network, demand, and metadata organized by scenario
5. **Configuration in `configurations/`** — All runtime settings loaded from JSON, no hardcoding
6. **Tests at root-level `tests/`** — Central location for all unit and integration tests
