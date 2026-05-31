# Architectural Decisions

## ADR 2026-05-31: simple_b Uses TCP JSON-Line FSM Components

### Status

Accepted.

### Context

The `simple_b` prototype needed a small one-class-per-file structure while keeping SUMO
simulation, controller logic, routing, and recording as separate components. The user also
requested that all component communication happen over TCP on localhost and that the connector
manage message routing.

### Decision

`simple_b` now runs four finite-state-machine components over localhost TCP:

- `Simulation` owns TraCI/SUMO, computes phase queue metrics, and sends traffic state messages.
- `FixedCycleController`, `MaxPressureController`, and `PriorityPassController` own alternative
  traffic-light control FSMs.
- `Connector` routes JSON-line messages between components and mirrors communication to the recorder.
- `Recorder` appends routed communication to a JSON-lines text log.
- `config.json` holds the top-level configuration.
- `main.py` directly loads `config.json`, starts components in order, waits for simulation
  completion, and stops components in reverse order.

Messages are JSON objects terminated by newlines. The connector is the only router, so components
only need to know their own TCP listener and the connector endpoint.

### Consequences

- The prototype is easy to inspect and run as a self-contained folder, and runtime settings plus
  the active controller can be edited without touching Python code.
- Components remain process-bound for now, but their TCP contract allows later separation into
  independent processes.
- The FSM and TCP server code is intentionally duplicated across files to preserve the
  one-class-per-file shape requested for readability.
