# Integrations

## SUMO / TraCI
- `src/environment_sumo.py` (`SumoEnvironment`) starts SUMO through TraCI. The binary is
  configured in the scenario/environment JSON (e.g. `sumo_binary`); default `sumo-gui`, replaceable
  with any local SUMO executable name or path.
- Binary resolution is robust across platforms: `sumo-gui` is resolved from `PATH`, the
  `SUMO_HOME` environment variable, and common local install locations (e.g. on Windows
  `%LOCALAPPDATA%\sumo-1.19.0\bin\sumo-gui.exe`). This avoids failures when SUMO is installed but
  not on the shell `PATH`.
- SUMO config, network, demand, route, and phase metadata are loaded from the scenario directory
  referenced in the JSON. **Required version: SUMO 1.19.0** (matching `sumolib==1.19.0`,
  `traci==1.19.0`); `SUMO_HOME` must be set (`sumo --version` to verify).

## Local TCP messaging
- Components communicate over **persistent localhost TCP** with newline-terminated JSON messages
  (`sent_at`, `sender`, `target`, `topic`, `payload`) between Environment, LogicModule(s),
  Orchestrator, and Recorder. See `mem:system_patterns` for the persistent-connection rule.
- Default ports (configured per JSON `communication.ports`): Orchestrator `127.0.0.1:51000`,
  Environment `51001`, LogicModule `51002`, Recorder `51003`. Baseline configs omit the
  `"logic_module"` port entirely.
- Recorder text logs are written under `logs/`; vehicle-event logs under
  `logs/{scenario}_{controller}/vehicle_log.jsonl`.

## Message topics (contract)
`traffic_state` (Env→Modules via Orchestrator), `logic_command` (Modules→Orchestrator, with
`payload.type`), `step` / `apply_and_advance` (Orchestrator→Env), `environment_started` /
`environment_stopped` (Env→Orchestrator), `vehicle_log_meta` / `vehicle_event` (Env→Orchestrator),
`communication` and `vehicle_log` (Orchestrator→Recorder).

## Common failure modes
- **TraCI "connection refused" / SUMO won't start** — SUMO not installed or not on `PATH`, or the
  configured `sumo_binary` path is wrong. The binary resolver checks `PATH`, `SUMO_HOME`, and
  common local install paths (see above); set `SUMO_HOME` and verify with `sumo --version`.
- **Port already in use** — a previous run left a component bound to `51000–51003`; ensure the
  prior run shut down, or change the ports in the config.
- **`pytest` fails before collecting tests (Anaconda)** — a global Anaconda pytest plugin
  (Dash/Jupyter) can abort startup. Workaround: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/`.
- **Import errors** — usually a missing dependency in the venv or the venv not activated;
  re-run `pip install -r requirements.txt` inside the activated `venv`.
- **Windows Python 3.13 / venv issues** — 3.13 may not be on the Windows launcher, and
  `ensurepip` can hit temp-permission errors; use an explicit `python3.13` path and repair local
  ACLs if `venv` creation fails.

## CI (`.github/workflows/`)
`python_testing.yml` (pytest), `lint.yml` (pylint), `format_check.yml` (black --check),
`docs.yml` (MkDocs build/deploy to GitHub Pages), `sumo_scenarios.yml` (full end-to-end pipeline
simulation). See `mem:suggested_commands` for the local equivalents.
