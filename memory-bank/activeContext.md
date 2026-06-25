# Active Context

## Current Status

Repository is fully reorganized and documented as a proof-of-concept modular traffic control platform.
Documentation reflects technical architecture rather than FEDORA project context.
The platform demonstrates three optimization/control strategies (fixed-cycle, max-pressure, priority-pass)
with separate configuration files and entry point support for scenario selection.

## Recent Configuration Reorganization (2026-06-24)

**Configuration Files:**
- Renamed from `sumo_*_demo_config.json` to `{scenario}_sumo_{controller}_config.json` pattern
- Demo scenario: `demo_sumo_*.json` (3 configs for fixed-cycle, max-pressure, priority-pass)
- Vienna pilot: `vienna_sumo_*.json` (3 configs for each controller type)
- Clear naming immediately indicates scenario and controller type
- Each config contains only relevant parameters (no unused controller sections)

**New System Flowchart:**
- Added comprehensive Mermaid flowchart to README showing:
  - Component startup sequence (Recorder → Controller → Connector → Simulator)
  - 0.2s pauses between component starts for initialization
  - Port binding and state transitions during startup
  - Steady-state control loop once pipeline is ready
  - Message flow between Simulator, Controller, and Recorder
  - Decision logic for each controller type

## Previous Reorganization (2026-06-24)

**Structural changes:**
- Reorganized core components into `src/`:
  - `src/connector.py` — TCP JSON-line message router FSM
  - `src/controller_fixed_cycle.py` — Fixed-cycle controller FSM
  - `src/controller_max_pressure.py` — Max-pressure controller FSM
  - `src/controller_priority_pass.py` — Priority Pass controller FSM
  - `src/simulation_sumo.py` — SUMO TraCI FSM and traffic-state publisher
  - `src/recorder.py` — TCP communication logger FSM
- Moved tests to root-level `tests/` directory
- Created `scenarios/` directory for scenario-specific files:
  - `scenarios/demo/sumo/` — Demo SUMO simulation files
  - `scenarios/pilot_vienna/`, `pilot_basque_country/`, etc. — Pilot scenario files
- Created `configurations/` directory for scenario configuration files
- Entry point at `run.py` loads configuration and orchestrates component startup
- Created `logs/` directory for output artifacts

## What Is Working

- All controller/component Python files in `src/` are importable and syntactically valid
- Configuration loading from JSON files in `configurations/` succeeds for all FSM components
- SUMO simulation file loading from `scenarios/demo/sumo/` metadata works
- Test suite passes: `pytest tests/ -v`
- TCP communication routing through Connector component functions correctly
- Relative path handling throughout the codebase

## What Is Incomplete

- Tests are not yet extended for all controller variants
- Full end-to-end integration testing with SUMO GUI not yet validated in new structure
- Some pilot scenario directories are skeleton implementations

## Known Issues

- Python 3.13 requirement may not be available in all development environments
- SUMO installation and PATH configuration varies by platform

## Next Logical Steps

1. Validate scenario execution with `run.py` pointing to different configurations
2. Extend test suite to cover all controller types and scenario variants
3. Document scenario structure and configuration patterns in STRUCTURE.md
4. Implement remaining pilot scenario integrations

## Active Decisions

- Keep components at root of `src/` for direct importability in `run.py`
- Use `scenarios/` structure to organize scenario-specific SUMO files and configurations
- Keep all tests at root-level `tests/` directory for central discoverability
