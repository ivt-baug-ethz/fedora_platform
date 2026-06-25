# Architectural Decisions

## ADR 2026-05-31: TCP JSON-Line FSM Component Architecture

### Status

Accepted.

### Context

The platform needed a small one-class-per-file structure while keeping SUMO
simulation, controller logic, routing, and recording as separate components. All
component communication happens over TCP on localhost with the connector managing
message routing.

### Decision

The platform runs finite-state-machine components over localhost TCP:

- `Simulation` owns TraCI/SUMO, computes phase queue metrics, and sends traffic state messages.
- `FixedCycleController`, `MaxPressureController`, and `PriorityPassController` implement alternative
  traffic-light control strategies.
- `Connector` routes JSON-line messages between components and mirrors communication to the recorder.
- `Recorder` appends routed communication to a JSON-lines text log.
- Configuration files (JSON) hold scenario-specific settings.
- `run.py` loads configuration, starts components in order, waits for simulation
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
