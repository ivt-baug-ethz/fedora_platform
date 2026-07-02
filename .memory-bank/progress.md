# Progress

## Implemented and Working (Post-Reorganization)

**Core framework:**
- Core component model with component lifecycle management
- Communication system with message bus pattern
- Storage system with memory, JSON, and SQLite backends
- Priority Pass implementation for Vienna pilot
- SUMO integration for traffic simulation

**Orchestrator-driven components (in `src/`):**
- `orchestrator.py` — Platform orchestrator FSM: reads full config, creates/starts all sub-components, drives environment step loop via `"step"` / `"apply_and_advance"` messages; dispatches environment class via `_ENVIRONMENT_TYPES`; optionally polls component state after each step and forwards `state_report` to recorder
- `environment_sumo.py` — `SumoEnvironment` (`NAME = "environment"`): passive SUMO/TraCI FSM, waits for `"step"` from Orchestrator, measurement types injected (not config-driven); `get_state` handler with lazy TraCI caching; `vehicle_log_enabled` guard
- `controller_fixed_cycle.py` — Fixed-cycle controller FSM; `get_required_measurements()` returns `[]`; `get_state` handler returns step/light_states
- `controller_max_pressure.py` — Max-pressure controller FSM; `get_required_measurements()` returns queue metric based on bidding_strategy; `get_state` handler returns bids/phase_switched
- `controller_priority_pass.py` — Priority Pass controller FSM; `get_required_measurements()` returns queue metric + `"upp_bids"`; `get_state` handler returns queue/upp/blended bids + tau
- `recorder.py` — TCP communication logger FSM writing to `logs/`; configurable via `topics`, `vehicle_log_enabled`; writes `run_meta` header on start; always functional when instantiated (enabled/disabled decision belongs to orchestrator)

**TCP communication (fixed 2026-06-25):**
- All senders (`Orchestrator._forward`, `SumoEnvironment._send_message`, `*Controller._send_message`) use persistent connections — created on first use, reused per target, reset on OSError
- All receivers (`_handle_client`) parse messages line-by-line from persistent connections
- `SumoEnvironment._run_loop` has a 30-second safety timeout on `step_event.wait()`

**Baseline mode:**
- `"logic_modules": []` is a valid configuration — Orchestrator short-circuits in `_route()`, immediately sends empty `apply_and_advance` + `step`, SUMO uses its own built-in signal plans
- `configurations/demo_sumo_baseline_config.json` and `vienna_sumo_baseline_config.json` created (no `logic_module` port)
- `run.py` defaults `logic_module_name` to `"baseline"` when list is empty; result dir: `results/{scenario}/baseline/`

**Configuration and scenarios:**
- Centralized configuration files in `configurations/` — `"enabled"` key removed from `lane_measurements` (auto-derived from controller)
- Baseline configs omit `"logic_module"` from `communication.ports`; all controller configs use `"logic_module"` port key as before
- Scenario-specific SUMO files organized in `scenarios/demo/sumo/` and `scenarios/pilot_*/`
- `run.py` is a thin entry point: creates Orchestrator, calls start/wait_until_done, runs Evaluator
- SUMO executable resolution from PATH, `SUMO_HOME`, and platform-specific install locations

**Evaluation (updated 2026-07-02):**
- `src/evaluation/` package: EvaluationConfig, VehicleLogLoader, MetricsComputer, PlotGenerator, Evaluator
- Standard metrics: VKT, VHT, flow, space-mean speed, density, travel time stats, travel time variance
  (average delay / delay variance were added 2026-07-01 and removed 2026-07-02 — the free-flow proxy
  assumption was invalid for networks with routes of different lengths; see DECISIONS.md)
- `post_processing/priority_pass_analysis.py`: PP-specific priority vs. regular vehicle analysis (manual post-processing)
- Evaluation configurable via `evaluation.enabled` / `evaluation.metrics` in JSON configs
- `vehicle_log.jsonl` extended with `route_distance_m` (per departure) and `total_lane_length_m` (in run_meta)
- Edge lengths in `environment_sumo.py` derived from `lane.getEdgeID()` + cached lane lengths (TraCI has
  no `edge.getLength()`)

**Testing:**
- Test suite at root-level `tests/` directory — 107 tests passing (up from 80)
- Basic functionality tests for core components and Priority Pass implementation
- Configuration validation tests passing
- New: test_loader.py (7 tests), test_metrics.py (13 tests), test_evaluation_config.py (6 tests)
- Priority Pass parity regression tests verify that `trade_off = 0.0` matches Max-Pressure
  phase commands/FSM state and that shipped Priority Pass configs preserve Max-Pressure
  auction timing.

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

### tests/test_controllers.py

- FSM lifecycle for all 3 controller types (fixed-cycle, max-pressure, priority-pass)
- `get_required_measurements()` for all controller types
- Fixed-cycle phase progression
- Max-pressure auction winner selection and bid extraction
- Priority-pass tau bid blending
- Priority-pass/Max-Pressure equivalence at `trade_off = 0.0`
- Demo/Vienna config timing parity between Max-Pressure and Priority Pass
- Orchestrator logic module instantiation by type

### tests/test_evaluator.py

- Evaluator unit tests (travel time calculation, statistics, plot generation)

### tests/test_recorder.py

- Recorder FSM, configuration, and TCP logging tests

## Pilot Readiness

| Pilot | Model assets present | Code integration status |
|-------|---------------------|-------------------------|
| Vienna | Yes | Fully integrated |
| Basque Country | Yes | Placeholder |
| Nicosia | Yes | Placeholder |
| Copenhagen | Yes | Placeholder |
| Reggio Emilia | Yes | Placeholder |
| Budapest | Yes | Placeholder |
