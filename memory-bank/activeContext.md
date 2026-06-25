# Active Context

## Current Status (2026-06-25) — Multi-Logic-Module Support Added

The Orchestrator now supports an ordered array of logic modules per run. Config key changed from
`"logic_module"` (object) to `"logic_modules"` (array). The Orchestrator fans `traffic_state` out
to all modules simultaneously, accumulates all `traffic_light_command` responses per step, merges
their command dicts, and then sends a single `apply_and_advance`. Single-module behavior is
unchanged. All 6 JSON config files updated; all 69 tests pass; pylint at 9.73/10.

---

## Previous Status (2026-06-25) — Inline Comments + Logic Module Rename Complete

Repository uses a Orchestrator-driven architecture. The Orchestrator is the sole entry-point: it reads
the full JSON config, creates and starts Recorder/Controller/Simulation, and drives the simulation step
loop. The Simulation is passive (waits for "step" messages). Measurement types are auto-discovered from
the logic module's `get_required_measurements()` method — the user no longer configures `"enabled"` in
the JSON config files.

## Recent Configuration Reorganization (2026-06-24)

**Configuration Files:**
- Renamed from `sumo_*_demo_config.json` to `{scenario}_sumo_{controller}_config.json` pattern
- Demo scenario: `demo_sumo_*.json` (3 configs for fixed-cycle, max-pressure, priority-pass)
- Vienna pilot: `vienna_sumo_*.json` (3 configs for each controller type)
- Clear naming immediately indicates scenario and controller type
- Each config contains only relevant parameters (no unused controller sections)

**New System Flowchart:**
- Added comprehensive Mermaid flowchart to README showing:
  - Component startup sequence (Recorder → Controller → Orchestrator → Simulator)
  - 0.2s pauses between component starts for initialization
  - Port binding and state transitions during startup
  - Steady-state control loop once pipeline is ready
  - Message flow between Simulator, Controller, and Recorder
  - Decision logic for each controller type

## Previous Reorganization (2026-06-24)

**Structural changes:**
- Reorganized core components into `src/`:
  - `src/orchestrator.py` — TCP JSON-line message router FSM
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
- TCP communication routing through Orchestrator component functions correctly
- Relative path handling throughout the codebase

## What Is Incomplete

- Tests are not yet extended for all controller variants
- Full end-to-end integration testing with SUMO GUI not yet validated in new structure
- Some pilot scenario directories are skeleton implementations

## Known Issues

- Python 3.13 requirement may not be available in all development environments
- SUMO installation and PATH configuration varies by platform

## Bug Fixed (2026-06-25)

Simulation got stuck at `step_event.wait()` around step 2317. Root cause: each step
created ≥7 short-lived loopback TCP connections; on macOS the ephemeral port table
fills up after ~2317 steps at high step rates, silently dropping connections and
leaving `step_event` permanently unset.

Fix: all senders now reuse persistent connections; all receivers parse line-by-line
instead of buffering until EOF; `step_event.wait()` gained a 30-second timeout.

## Code Cleanup (2026-06-25)

All `src/` files were comprehensively cleaned up:

- **simulation_sumo.py**: Fixed import order (`traci` after stdlib); inlined 9 trivial single-use helpers into their call sites with inline comments; renamed `_criterion_to_abort` → `_simulation_ended`, `_crawl_step_traci_data` → `_update_vehicle_positions`; removed dead `traci_module` and `vehicle_sensor_entered` attributes; added full docstrings with Args/Returns to all methods
- **orchestrator.py** (formerly connector.py): Inlined `_configure_recorder()` into `configure()`; added Args/Returns docstrings throughout; updated class docstring
- **recorder.py**: Fixed import order; removed self-evident inline comments; added Args/Returns docstrings
- **evaluator.py**: Removed dead `if plt is None:` guards (plt is always imported); condensed docstrings
- **controller_*.py**: Added Args/Returns to all docstrings; inline comments for non-obvious algorithm steps; renamed `_determine_auction_winner_phase` → `_determine_auction_winner` in both auction controllers
- **README.md**: Fixed tests/ directory listing (only `test_evaluator.py` exists); corrected "SQLite backend available" to "additional backends planned"

## Next Logical Steps

1. End-to-end test with SUMO GUI against all three controller configs (requires SUMO installation)
2. Extend test suite to cover `get_required_measurements()` on all controller types
3. Add unit tests for Orchestrator orchestration hooks (simulation_started, traffic_light_command interception)
4. Implement remaining pilot scenario integrations

## Active Decisions

- Keep components at root of `src/` for direct importability
- Use `scenarios/` structure to organize scenario-specific SUMO files and configurations
- Keep all tests at root-level `tests/` directory for central discoverability
- Orchestrator owns all component lifecycle — `run.py` must not create component objects directly

## Rename: connector → orchestrator (2026-06-25)

- `src/connector.py` renamed to `src/orchestrator.py`; class `Connector` → `Orchestrator`; `NAME = "orchestrator"`
- Config port key `"connector"` → `"orchestrator"` in all 6 JSON config files
- All controllers and simulation: `self.connector` → `self.orchestrator`, `_connector_connection` → `_orchestrator_connection`, `_connector_lock` → `_orchestrator_lock`, config key `"connector"` → `"orchestrator"`
- `run.py` updated: imports from `orchestrator`, uses variable `orchestrator`
- All docs (README, STRUCTURE.md, DECISIONS.md, INTEGRATIONS.md, CLAUDE.md) updated
- memory-bank and auto-memory updated

## Test Coverage Extension (2026-06-25)

Added two new test files:
- `tests/test_controllers.py` (54 tests): FSM lifecycle for all 3 controller types; `get_required_measurements()`; fixed-cycle phase progression; max-pressure auction winner selection and bid extraction; priority-pass tau bid blending; Orchestrator logic module instantiation by type
- `tests/test_recorder.py` (12 tests): Recorder FSM; configure sets paths; invalid transitions; TCP communication and multi-message logging

Total: 67 tests, all passing.

## Inline Comments Added (2026-06-25)

All 8 source files now have compact lowercase inline comments on every logical block:
- `run.py`, `recorder.py`, `evaluator.py`, `orchestrator.py`, `simulation_sumo.py`
- `controller_fixed_cycle.py`, `controller_max_pressure.py`, `controller_priority_pass.py`
Recurring patterns (SO_REUSEADDR, lazy TCP connection, 1-second timeout) use identical phrasing across all files.

## Component Slot Rename: "controller" → "logic_module" (2026-06-25)

The pluggable component slot was renamed from "controller" to "logic_module":
- Port key in `communication.ports`: `"controller"` → `"logic_module"`
- Config section: `"controller": { "type": ... }` → `"logic_module": { "type": ... }`
- Orchestrator: `self.controller` → `self.logic_module`, `_configure_controller` → `_configure_logic_module`, `_CONTROLLER_TYPES` → `_LOGIC_MODULE_TYPES`, `_AnyController` → `_AnyLogicModule`
- All simulation `_send_message("controller", ...)` → `_send_message("logic_module", ...)`
- All three controller class `NAME = "logic_module"`
- Type key rename: `"fixed_cycle"` → `"controller_fixed_cycle"`, etc. in both configs and `_LOGIC_MODULE_TYPES`
- Controller class names and all logic unchanged.
