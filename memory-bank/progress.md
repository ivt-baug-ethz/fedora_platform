# Progress

## Implemented and Working (Post-Reorganization)

**Core framework:**
- Core component model with component lifecycle management
- Communication system with message bus pattern
- Storage system with memory, JSON, and SQLite backends
- Priority Pass implementation for Vienna pilot
- SUMO integration for traffic simulation

**Orchestrator-driven components (in `src/`):**
- `orchestrator.py` — Platform orchestrator FSM: reads full config, creates/starts all sub-components, drives simulation step loop via `"step"` / `"apply_and_advance"` messages
- `simulation_sumo.py` — Passive SUMO/TraCI FSM: waits for `"step"` from Orchestrator, measurement types injected (not config-driven)
- `controller_fixed_cycle.py` — Fixed-cycle controller FSM; `get_required_measurements()` returns `[]`
- `controller_max_pressure.py` — Max-pressure controller FSM; `get_required_measurements()` returns queue metric based on bidding_strategy
- `controller_priority_pass.py` — Priority Pass controller FSM; `get_required_measurements()` returns queue metric + `"upp_bids"`
- `recorder.py` — TCP communication logger FSM writing to `logs/`

**TCP communication (fixed 2026-06-25):**
- All senders (`Orchestrator._forward`, `Simulation._send_message`, `*Controller._send_message`) use persistent connections — created on first use, reused per target, reset on OSError
- All receivers (`_handle_client`) parse messages line-by-line from persistent connections
- `Simulation._run_loop` has a 30-second safety timeout on `step_event.wait()`

**Configuration and scenarios:**
- Centralized configuration files in `configurations/` — `"enabled"` key removed from `lane_measurements` (auto-derived from controller)
- Scenario-specific SUMO files organized in `scenarios/demo/sumo/` and `scenarios/pilot_*/`
- `run.py` is a thin entry point (~70 lines): creates Orchestrator, calls start/wait_until_done, runs Evaluator
- SUMO executable resolution from PATH, `SUMO_HOME`, and platform-specific install locations

**Testing:**
- Test suite at root-level `tests/` directory
- Basic functionality tests for core components and Priority Pass implementation
- Configuration validation tests passing

## Partially Implemented

- Pilot scenarios (Basque Country, Nicosia, Copenhagen, Reggio Emilia, Budapest) have skeleton
  directory structures in `scenarios/` but lack complete functional implementations
- Extended test coverage for all controller variants still in progress

## Planned / Placeholder

- Implementation of other pilot systems beyond Vienna.
- Integration with real traffic infrastructure.
- Additional communication protocols.
- Enhanced storage backends.
- Web UI components.
- Optional future split of FSM components into independent processes.

## Test Coverage Assessment

### src/fedora_platform/components.py

- Tests cover basic component lifecycle and state transitions.
- Test suite confirms correct handling of valid and invalid transitions.

### src/fedora_platform/priority_pass.py

- Tests cover Priority Pass optimizer, simulator, and pilot implementation.
- Tests verify correct control settings generation and simulation functionality.
- Tests verify message handling between components.

### src/fedora_platform/mtm_space.py

- Tests cover MTM Space functionality including component registration and step execution.

### src/fedora_platform/communication.py

- Tests cover message bus functionality including message routing, subscriptions, and delivery.

### src/fedora_platform/storage.py

- Tests cover all data storage backends (memory, JSON, SQLite).
- Tests verify interaction logging functionality.

## Pilot Readiness

| Pilot | Model assets present | Code integration status |
|-------|---------------------|-------------------------|
| Vienna | Yes | Fully integrated |
| Basque Country | Yes | Placeholder |
| Nicosia | Yes | Placeholder |
| Copenhagen | Yes | Placeholder |
| Reggio Emilia | Yes | Placeholder |
| Budapest | Yes | Placeholder |
