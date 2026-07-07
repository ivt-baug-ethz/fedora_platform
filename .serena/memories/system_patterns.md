# System Patterns

## Component lifecycle (finite state machine)
Every `src/` component shares the same FSM constants and transition map. Illegal transitions
raise immediately, so correct ordering is enforced structurally.

States: **CREATED** (instantiated) → **CONFIGURED** (params set) → **READY** (resources
allocated) → **RUNNING** (processing) → **STOPPED** (can reconfigure); **FAILED**
(unrecoverable).

Valid transitions:
- CREATED → CONFIGURED, STOPPED, FAILED
- CONFIGURED → READY, STOPPED, FAILED
- READY → RUNNING, STOPPED, FAILED
- RUNNING → STOPPED, FAILED
- STOPPED → CONFIGURED
- FAILED → STOPPED

## Key patterns
- **FSM pattern** — explicit state constants + transition maps in every component.
- **Orchestrator-owns-all** — `run.py` only parses CLI args and calls `Orchestrator.start()` /
  `wait_until_done()`. The Orchestrator creates *every* sub-component (Recorder, LogicModule(s),
  Environment) from the JSON config and manages their full lifecycle. Nothing is instantiated in
  `run.py` directly. Environment class dispatched by `"type"` via `_ENVIRONMENT_TYPES`.
- **Persistent TCP connections** — each sender creates **one socket per target** on first use and
  reuses it for every subsequent message (reset on `OSError`); receivers parse **line-by-line** on
  persistent connections. This prevents ephemeral-port exhaustion at high step rates (learned: the
  port table fills around step ~2317 on macOS with per-message connections).
- **Environment reports, platform persists** — `SumoEnvironment` emits vehicle state via
  `vehicle_log_meta` / `vehicle_event`; the Orchestrator forwards it to the Recorder as
  `vehicle_log`, which owns `vehicle_log.jsonl`. Keeps evaluation decoupled from the (swappable)
  environment. (See the corresponding ADR in `mem:architectural_decisions`.)

## Orchestrator-driven step loop
```
Orchestrator.start() → recorder.start() → logic_module[0].start() → ... → environment.start()
  → environment sends "environment_started"
  → Orchestrator intercepts → sends "step" to environment
  → environment collects measurements → sends "traffic_state"
  → Orchestrator fans "traffic_state" out to ALL logic modules
  → each module computes plan → sends "logic_command" (payload.type="traffic_light_command")
  → Orchestrator accumulates; once all N modules replied → merges command dicts
    → sends "apply_and_advance" + next "step"
  → environment applies commands, advances SUMO, collects next measurements → ...
  → environment sends "environment_stopped" → Orchestrator.done_event.set()
```
Config supports N logic modules via `"logic_modules": [...]` and exactly one environment via
`"environment": {"type": "sumo_simulation", ...}`. **Baseline mode:** `"logic_modules": []` is
valid — the Orchestrator short-circuits and sends an empty `apply_and_advance` + `step` each step,
leaving SUMO's built-in signal plans in control. Adding a new environment type = implement the
`"step"` / `"apply_and_advance"` handler contract and register it in `_ENVIRONMENT_TYPES`.

All runtime messages are newline-terminated JSON objects over localhost TCP. Configuration is
loaded from `configurations/`; scenario SUMO files from `scenarios/`.
