# External Integrations

## SUMO / TraCI

- `simple_b/simulation.py` starts SUMO through TraCI with the binary configured in
  `simple_b/config.json` as `simulation.sumo_binary`.
- The default binary is `sumo-gui`; the user can replace it with a local SUMO executable name or
  path in the top-level config.
- On Windows/Spyder, `simple_b/simulation.py` now resolves `sumo-gui` from PATH, `SUMO_HOME`, and
  common local installs such as `%LOCALAPPDATA%\sumo-1.19.0\bin\sumo-gui.exe`.
- The SUMO configuration is loaded from
  `simple_b/sumo_simulation_files/Configuration.sumocfg`.
- Runtime route and phase metadata is loaded from the JSON files in
  `simple_b/sumo_simulation_files/`.

## Local TCP Messaging

- `simple_b` uses localhost JSON-line TCP messages between `Simulation`, the active controller,
  `Connector`, and `Recorder`.
- The active controller is selected with `controller.type` in `simple_b/config.json`; supported
  values are `fixed_cycle`, `max_pressure`, and `priority_pass`.
- Default ports are configured in `simple_b/main.py`:
  - Connector: `127.0.0.1:51000`
  - Simulation: `127.0.0.1:51001`
  - Controller: `127.0.0.1:51002`
  - Recorder: `127.0.0.1:51003`
- Generated recorder text logs are written under `simple_b/sumo_simulation_files/logs/` and are
  ignored by git when they use the configured `.txt` extension.

## Python Environment Used This Session

- The project Python 3.13 venv could not be created because Python 3.13 was not registered with
  the Windows launcher.
- Validation used the user's Anaconda Python at
  `C:\Users\kriehl\AppData\Local\anaconda3\python.exe` (Python 3.11.5).
- Pytest was run with plugin autoload disabled to avoid unrelated global Anaconda pytest plugins.
