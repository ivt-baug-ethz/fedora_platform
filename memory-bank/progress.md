# Progress

## Implemented and Working

- Core component model with component lifecycle management.
- Communication system with message bus pattern.
- Storage system with memory, JSON, and SQLite backends.
- Priority Pass implementation for Vienna pilot.
- SUMO integration for traffic simulation.
- Test suite with basic functionality testing.
- Example script for running Priority Pass simulation.
- `simple_b` five-file TCP FSM prototype:
  - `config.json` stores TCP, SUMO, spawning, and controller settings.
  - `main.py` directly loads the JSON config and starts/stops all components.
  - `simulation.py` owns SUMO/TraCI, vehicle spawning, queue metrics, and traffic-light commands.
  - `controller_priority_pass.py` owns the Priority Pass auction FSM.
  - `connector.py` routes JSON-line TCP messages and mirrors traffic to the recorder.
  - `recorder.py` writes communication records to a text log.
- `simple_b` resolves `sumo-gui` from PATH, `SUMO_HOME`, and common Windows local SUMO installs,
  including the user's `%LOCALAPPDATA%\sumo-1.19.0\bin\sumo-gui.exe` path.

## Partially Implemented

- Other pilot sites (Basque Country, Nicosia, Copenhagen, Reggio Emilia, Budapest) exist in
  `models/` but do not have functional implementations yet.
- `simple_b` has compile/configuration validation, but the live SUMO GUI loop was not run during
  this session.

## Planned / Placeholder

- Implementation of other pilot systems beyond Vienna.
- Integration with real traffic infrastructure.
- Additional communication protocols.
- Enhanced storage backends.
- Web UI components.
- Optional future split of `simple_b` FSMs into independent processes.

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

### simple_b

- `py_compile` passes for all five Python files using the available Anaconda Python.
- Component configuration loading succeeds without starting SUMO.
- SUMO executable resolution was validated against the local Windows install path.
- No dedicated automated test file exists yet for the TCP FSM prototype.

## Pilot Readiness

| Pilot | Model assets present | Code integration status |
|-------|---------------------|-------------------------|
| Vienna | Yes | Fully integrated |
| Basque Country | Yes | Placeholder |
| Nicosia | Yes | Placeholder |
| Copenhagen | Yes | Placeholder |
| Reggio Emilia | Yes | Placeholder |
| Budapest | Yes | Placeholder |
| simple_b prototype | Yes | Simplified TCP FSM prototype |
