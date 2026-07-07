# Codebase Structure

Layout of the FEDORA Platform. Keep current when files/modules are added, moved, or removed.

## Top level
- `run.py` — thin entry point (parses `CONFIG_FILE`, `--skip-evaluation`, `--headless`;
  creates an `Orchestrator`, calls `start()` / `wait_until_done()`; then reads
  `config["evaluation"]`, builds `EvaluationConfig`, and runs the `Evaluator` unless disabled).
  All component lifecycle is owned by the Orchestrator — nothing else is instantiated here.
- `configurations/` — JSON configs, one per `{scenario}_sumo_{controller}_config.json`
  (demo + vienna × baseline/fixed_cycle/max_pressure/priority_pass). No hardcoded settings in code.
- `scenarios/` — scenario-specific SUMO assets. `scenarios/demo/sumo/` (functional:
  `config.sumocfg`, `network.net.xml`, `demand.xml`, `phase_*.json`, `route_*.json`,
  `possible_trips.xml`); `scenarios/pilot_vienna/` (functional); `scenarios/pilot_*/` (skeletons).
- `tests/` — **root-level** test suite (run command in `mem:suggested_commands`):
  `test_controllers.py` (controller FSMs, auction logic, measurement requirements, and the
  Priority-Pass = Max-Pressure parity at `trade_off=0`), `test_evaluator.py` (Evaluator
  end-to-end), `test_loader.py` (`VehicleLogLoader`), `test_metrics.py` (`MetricsComputer`),
  `test_evaluation_config.py` (`EvaluationConfig`), `test_recorder.py` (Recorder FSM + TCP logging).
- `docs/` — user-facing **MkDocs Material** site (`mkdocs.yml`), deployed to GitHub Pages:
  `index.md`, `getting-started.md`, `architecture.md`, `components.md`, `configuration.md`,
  `evaluation.md`.
- `logs/` — generated run logs (git-ignored). `results/` — generated evaluation output (git-ignored).
- `figures/` — banner + pilot images. `requirements.txt` — pinned deps. `pyproject.toml` —
  packaging metadata (setuptools, `src/` layout). `README.md` — user-facing only.
- `AGENTS.md` — the single agent-instruction source of truth. `CLAUDE.md` — thin pointer to it.
  `.serena/` — Serena config + memories (reference knowledge). `.ai/` — local decision/progress
  logs (git-ignored). See `mem:ai_tracking_system`.

## `src/` — core components (TCP FSM; one class per file)
- `orchestrator.py` — **platform orchestrator**: reads the full JSON config; creates and starts
  Recorder, LogicModule(s), and Environment; drives the environment step loop by intercepting
  `environment_started` / `logic_command` / `environment_stopped` and issuing `"step"` /
  `"apply_and_advance"`. Queries each module's `get_required_measurements()` to tell the
  environment which metrics to collect (no measurement config in JSON). Mirrors all traffic to
  the Recorder; forwards environment-reported `vehicle_event` / `vehicle_log_meta` to the
  Recorder as `vehicle_log` messages. Pluggable environment types via `_ENVIRONMENT_TYPES`
  (currently `"sumo"`).
- `environment_sumo.py` — `SumoEnvironment` (`NAME = "environment"`): passive SUMO/TraCI FSM;
  waits for `"step"` before each iteration; spawns vehicles, reads traffic state, applies signal
  commands on `"apply_and_advance"`. **Reports** vehicle arrivals/departures (+ route distances)
  as messages — writes **no** log files itself (gated by injected `report_vehicle_events`). Edge
  lengths derived from `lane.getEdgeID()` + cached lane lengths (TraCI lacks `edge.getLength()`).
- `controller_fixed_cycle.py` — configurable pre-timed controller; `get_required_measurements() -> []`.
- `controller_max_pressure.py` — pressure-based auction controller;
  `get_required_measurements()` returns `["queue_lengths"]` or `["weighted_queue_lengths"]`
  by `bidding_strategy`.
- `controller_priority_pass.py` — UPP controller; `get_required_measurements()` returns the
  queue metric + `"upp_bids"`. Strict Max-Pressure extension (see the parity invariant in
  `mem:project_overview`); shares Max-Pressure auction timing in the shipped configs.
- `recorder.py` — TCP communication logger FSM; writes `communication_log.txt` and is the **sole
  owner** of `vehicle_log.jsonl` (written from forwarded `vehicle_log` messages, fresh per run;
  gated by `recorder.enabled` / `vehicle_log_enabled`). Writes to `logs/{scenario}_{controller}/`.
- `evaluation/` — standard metrics package: `config.py` (`EvaluationConfig`, metric allowlist),
  `loader.py` (`VehicleLogLoader` → `(run_meta, completed vehicle records)`), `metrics.py`
  (`MetricsComputer`: VKT, VHT, flow, space-mean speed, density, travel-time mean/median/min/max/
  variance; missing data yields `None`), `plots.py` (`PlotGenerator`: histogram + cumulative count
  + cumulative average travel time), `evaluator.py` (`Evaluator` facade → `evaluation_stats.json`).
- `post_processing/` — controller-specific, manual (not part of the standard pipeline):
  `priority_pass_analysis.py` (`PriorityPassAnalysis`: priority vs. regular vehicle breakdown;
  CLI `python src/post_processing/priority_pass_analysis.py CONFIG_FILE`; auto-run by `run.py`
  for Priority Pass configs), `vehicle_count_comparison.py` (cross-controller cumulative vehicle
  counts; reuses `VehicleLogLoader`; accepts multiple configs, skips missing logs).

## Runtime flow
`run.py` → `Orchestrator` creates/starts Recorder → LogicModule(s) → Environment → step loop
(`step` → `traffic_state` fan-out → `logic_command` ×N merged → `apply_and_advance`) →
`environment_stopped` → optional `Evaluator`. See `mem:system_patterns` for the loop detail.

## Structural rules
No absolute paths (relative to project root, `pathlib`); one class per file in `src/`; entry
points at root (`run.py`), not in `src/`; scenario files in `scenarios/`; config in
`configurations/`; tests in root `tests/`.
