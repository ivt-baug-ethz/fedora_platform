# System Patterns: FEDORA Platform

## Component Lifecycle

### Finite State Machine Diagram
```
[*] --> CREATED
CREATED --> CONFIGURED: configure()
CONFIGURED --> READY: prepare (resources allocated)
READY --> RUNNING: start()
RUNNING --> STOPPED: stop()
READY --> STOPPED: stop()
CONFIGURED --> STOPPED: stop()
CREATED --> STOPPED: stop()
CREATED --> FAILED: fail()
CONFIGURED --> FAILED: fail()
READY --> FAILED: fail()
RUNNING --> FAILED: fail()
FAILED --> STOPPED: stop()
STOPPED --> CONFIGURED: configure()
```

### States
- **CREATED**: Component instantiated, not yet configured
- **CONFIGURED**: Parameters set, resources not yet allocated
- **READY**: Resources allocated, ready to start
- **RUNNING**: Actively processing
- **STOPPED**: Stopped, can be reconfigured
- **FAILED**: Encountered an unrecoverable error

### Valid Transitions
- CREATED → CONFIGURED, STOPPED, FAILED
- CONFIGURED → READY, STOPPED, FAILED
- READY → RUNNING, STOPPED, FAILED
- RUNNING → STOPPED, FAILED
- STOPPED → CONFIGURED
- FAILED → STOPPED

## Key Design Patterns

### Finite State Machine Pattern
All components in `src/` implement the same FSM constants and transition map (defined in `orchestrator.py` base pattern, mirrored in each component). Illegal transitions raise immediately; correct ordering is enforced structurally.

### Orchestrator-Owns-All Pattern
`run.py` only parses CLI args and calls `Orchestrator.start()` / `wait_until_done()`. The Orchestrator creates every sub-component (Recorder, Logic Module(s), Environment) from the JSON config and manages their full lifecycle. No component is instantiated in `run.py` directly.

### Persistent TCP Connection Pattern
All senders create one socket per target on first use and reuse it for every subsequent message. Receivers parse line-by-line on persistent connections. This prevents port exhaustion at high step rates (learned: ephemeral port table fills ~step 2317 on macOS with per-message connections).

## Core Application Pattern (TCP FSM Controllers)

The main application is built from modular FSM-based components in `src/`, orchestrated by the Orchestrator:

- **`run.py`** (root level) — Thin entry point (~70 lines): parses CLI args, creates `Orchestrator`, calls `start()` / `wait_until_done()`, runs Evaluator
- **`src/orchestrator.py`** — **Platform orchestrator**: reads full JSON config, creates and starts Recorder/LogicModule/Environment, drives the environment step loop via `"step"` and `"apply_and_advance"` messages; dispatches environment class by `"type"` via `_ENVIRONMENT_TYPES`
- **`src/environment_sumo.py`** — `SumoEnvironment` (`NAME = "environment"`): passive SUMO wrapper, waits for `"step"` command from Orchestrator before each iteration; measurement types injected by Orchestrator from controller requirements; type key `"sumo_simulation"`
- **`src/controller_fixed_cycle.py`** — Fixed-cycle controller FSM; `get_required_measurements()` returns `[]`
- **`src/controller_max_pressure.py`** — Max-pressure controller FSM; `get_required_measurements()` returns `["queue_lengths"]` or `["weighted_queue_lengths"]` based on bidding_strategy
- **`src/controller_priority_pass.py`** — Priority Pass controller FSM; `get_required_measurements()` returns queue measurement + `"upp_bids"`
- **`src/recorder.py`** — Listens on TCP, logs routed communication to files in `logs/`

### Environment Step Loop (Orchestrator-Driven)

```
Orchestrator.start() → recorder.start() → logic_module[0].start() → ... → environment.start()
    ↓
environment sends "environment_started"
    ↓
Orchestrator._route() intercepts → sends "step" to environment
    ↓
environment collects measurements → sends "traffic_state" to orchestrator
    ↓
Orchestrator intercepts "traffic_state" → fans out to ALL logic modules
    ↓
each logic module computes plan → sends "logic_command" (with payload.type="traffic_light_command") to orchestrator
    ↓
Orchestrator accumulates responses; once all N modules replied:
  → merges command dicts → sends "apply_and_advance" + next "step" to environment
    ↓
environment applies commands → advances SUMO → collects next measurements → ...
    ↓
environment sends "environment_stopped" → Orchestrator.done_event.set()
```

Config supports N logic modules via `"logic_modules": [...]` array and exactly one environment via
`"environment": {"type": "sumo_simulation", ...}`. Adding a new environment type requires
implementing the `"step"` / `"apply_and_advance"` handler contract and registering in `_ENVIRONMENT_TYPES`.

All components use explicit state constants and transition maps. Runtime messages are JSON objects
sent over localhost TCP, terminated by newlines. Configuration is loaded from `configurations/`
directory and scenario-specific SUMO files are loaded from `scenarios/`.
