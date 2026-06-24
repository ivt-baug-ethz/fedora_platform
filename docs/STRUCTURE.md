# FEDORA Platform - Directory Structure

```
fedora_platform/
├── src/                           – Core application components (TCP FSM controllers)
│   ├── simulation_sumo.py         – SUMO/TraCI FSM, vehicle spawning, queue metrics
│   ├── controller_fixed_cycle.py  – Fixed-cycle traffic light controller FSM
│   ├── controller_max_pressure.py – Max-pressure auction controller FSM
│   ├── controller_priority_pass.py – Priority Pass (Vienna pilot) controller FSM
│   ├── connector.py               – TCP JSON-line message router FSM
│   └── recorder.py                – TCP communication logger FSM
│
├── run.py                         – Entry point: loads configuration and starts components
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
│   │       ├── phase_bidder_lanes.json    – Per-phase incoming lanes
│   │       ├── phase_exit_lanes.json      – Per-phase outgoing lanes
│   │       ├── route_*.json       – Route metadata (distances, durations, etc.)
│   │       └── possible_trips.xml – Trip source data
│   ├── pilot_vienna/              – Vienna pilot scenario skeleton
│   ├── pilot_basque_country/      – Basque Country pilot scenario skeleton
│   ├── pilot_nicosia/             – Nicosia pilot scenario skeleton
│   ├── pilot_copenhagen/          – Copenhagen pilot scenario skeleton
│   ├── pilot_reggio_emilia/       – Reggio Emilia pilot scenario skeleton
│   └── pilot_budapest/            – Budapest pilot scenario skeleton
│
├── logs/                          – Generated output and logs
│   ├── .gitkeep                   – Marker for git
│   └── sumo_priority_pass/        – Logs from demo runs
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
- Spawns vehicles, reads traffic state, and applies traffic light commands
- Implements FSM for simulation control flow (CREATED → CONFIGURED → READY → RUNNING → STOPPED)
- Publishes traffic metrics (queue lengths, vehicle positions) as JSON messages over TCP

**connector.py**
- Routes JSON-line TCP messages between application components
- Maintains persistent TCP connections to all components (Simulation, Controller, Recorder)
- Implements FSM for connection state management
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
- Listens on dedicated TCP port for message copies from Connector
- Logs all inter-component communication (traffic, commands, state) to text files
- Writes logs to `logs/` directory for post-simulation analysis
- Implements FSM for recorder state transitions

### Entry Point

**run.py**
- Loads configuration from `configurations/` directory (JSON format)
- Initializes all FSM components (Simulation, Controller, Connector, Recorder)
- Orchestrates component startup order and lifecycle transitions
- Handles inter-component communication setup (TCP host/port configuration)

### Structural Rules

1. **All code in `src/` must be importable** — No absolute paths, all paths relative to project root
2. **One class per file** (in `src/`) — Makes imports clear and single-responsibility explicit
3. **No external scripts in `src/`** — Entry points live at root level (e.g., `run.py`)
4. **Scenario-specific files in `scenarios/`** — SUMO network, demand, and metadata organized by scenario
5. **Configuration in `configurations/`** — All runtime settings loaded from JSON, no hardcoding
6. **Tests at root-level `tests/`** — Central location for all unit and integration tests
