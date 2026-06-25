# External Integrations

## SUMO / TraCI

- `src/simulation_sumo.py` starts SUMO through TraCI with the binary configured in
  the scenario configuration JSON as `simulation.sumo_details.sumo_binary`.
- The default binary is `sumo-gui`; the user can replace it with a local SUMO executable name or
  path in the configuration.
- On Windows, `src/simulation_sumo.py` resolves `sumo-gui` from PATH, `SUMO_HOME`, and
  common local installs such as `%LOCALAPPDATA%\sumo-1.19.0\bin\sumo-gui.exe`.
- The SUMO configuration is loaded from the scenario path configured in the JSON.
- Runtime route and phase metadata is loaded from the JSON files in the scenario directory.

## Local TCP Messaging

- The platform uses localhost JSON-line TCP messages between `Simulation`, the active controller,
  `Connector`, and `Recorder`.
- The active controller is selected with `controller.type` in the configuration JSON; supported
  values are `fixed_cycle`, `max_pressure`, and `priority_pass`.
- Default ports are configured in the configuration JSON:
  - Connector: `127.0.0.1:51000`
  - Simulation: `127.0.0.1:51001`
  - Controller: `127.0.0.1:51002`
  - Recorder: `127.0.0.1:51003`
- Generated recorder text logs are written under `logs/` and vehicle event logs to `logs/{scenario}_{controller}/`.

## Python Environment Used This Session

- The project Python 3.13 venv could not be created because Python 3.13 was not registered with
  the Windows launcher.
- Validation used the user's Anaconda Python at
  `C:\Users\kriehl\AppData\Local\anaconda3\python.exe` (Python 3.11.5).
- Pytest was run with plugin autoload disabled to avoid unrelated global Anaconda pytest plugins.
