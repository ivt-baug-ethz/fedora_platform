# Active Context

## Current Status

`simple_b` is a self-contained TCP/SUMO prototype with selectable fixed-cycle, max-pressure, and
Priority Pass controllers.

## Recent Changes

- Replaced legacy `simple_b` script modules with:
  - `main.py`
  - `config.json`
  - `simulation.py`
  - `controller_fixed_cycle.py`
  - `controller_max_pressure.py`
  - `controller_priority_pass.py`
  - `connector.py`
  - `recorder.py`
- Added explicit finite-state-machine states and transition maps to the simulation, controller,
  connector, and recorder components.
- Routed component communication through localhost TCP JSON-line messages managed by the connector.
- Added SUMO executable auto-resolution for Spyder/Windows runs where `sumo-gui` is not on PATH.
- Moved all launcher configuration from `main.py` into `simple_b/config.json`; `main.py` now
  directly loads JSON and starts/stops components without a wrapper class.
- Added `controller_fixed_cycle.py` and `controller_max_pressure.py` based on the legacy demo
  controller settings.
- `config.json` now selects the active controller with `controller.type`.
- Updated documentation files for structure, integrations, decisions, and scratchpad notes.
- Added a gitignore pattern for generated `simple_b` recorder `.txt` logs.

## What Is Working

- `simple_b` controller/component Python files each contain one class.
- `simple_b/config.json` owns local TCP, SUMO, demand, and controller settings.
- The simulation component loads the restored SUMO JSON metadata from `sumo_simulation_files`.
- Syntax compilation passes for all `simple_b` controller/component Python files.
- Simple configuration loading succeeds for all four FSM components.
- `Simulation.configure()` resolves `sumo-gui` to the local SUMO install under `%LOCALAPPDATA%`.
- Existing repository tests under `tests/` pass in the available Anaconda environment when pytest
  plugin autoload is disabled.

## What Is Incomplete

- The full SUMO GUI loop was not executed during this session after adding path resolution.
- `pylint src/` still reports pre-existing lint issues in the existing `src/` codebase.
- Python 3.13 is still not available through the Windows launcher on this machine.

## Known Issues

- The user's Anaconda Python is Python 3.11.5, not the repository's requested Python 3.13.
- Default Anaconda pytest plugin discovery fails because an unrelated Dash/Jupyter plugin raises
  before test collection.

## Next Logical Steps

1. Run `python simple_b/main.py` in the local SUMO-capable environment to verify the live GUI loop.
2. Tune `simple_b/config.json` for the desired flow, run length, and Priority Pass settings.
3. If needed, split the FSMs into separate processes while keeping the same TCP message contract.

## Active Decisions Pending

- Whether `simple_b` should remain a threaded single-process demo or become a multi-process demo.
