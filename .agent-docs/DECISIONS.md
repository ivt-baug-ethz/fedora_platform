# Architectural Decisions

## ADR 2026-06-26: Baseline Mode — Zero Logic Modules

### Status

Accepted.

### Context

All existing configurations required at least one logic module. There was no way to run the
simulation with SUMO's own built-in signal plans as a performance baseline without adding a
dummy controller. Comparative studies need a reference run that applies no external control.

Additionally, the "fixed-cycle controller" label was ambiguous — it could be confused with
SUMO's own internal fixed-plan timing, while in practice it is a fully *configurable* Python
controller that overrides SUMO's plans with user-supplied phase durations and offsets.

### Decision

**Baseline mode:** `"logic_modules": []` (an empty array) is now a valid configuration. The
Orchestrator detects zero modules in `_route()` and, upon receiving `traffic_state`, immediately
sends an empty `apply_and_advance` (no commands) followed by the next `step`, without waiting for
any `logic_command`. The environment applies zero commands and calls `simulationStep()`, leaving
all traffic lights under SUMO's built-in signal plans for that step.

Structural changes:
- `orchestrator.py`: removed `assert len(self.logic_modules) > 0` from `start()`; added a
  `not self.logic_modules` fast-path in `_route()` for the `traffic_state` topic.
- `run.py`: `logic_module_name` defaults to `"baseline"` when `logic_modules` is empty; result
  directory becomes `results/{scenario}/baseline/`.
- Baseline configs omit the `"logic_module"` port from `communication.ports` (no TCP listener
  is needed for a module that does not exist).

**Naming:** `controller_fixed_cycle` and its class `FixedCycleController` are now described as
the "configurable fixed-cycle controller" in all documentation and docstrings to make clear that
its phase timings come from the configuration file, not from SUMO.

**New configuration files:**
- `configurations/demo_sumo_baseline_config.json`
- `configurations/vienna_sumo_baseline_config.json`

### Consequences

- Baseline runs produce logs in `logs/{scenario}_baseline/` and results in
  `results/{scenario}/baseline/` — comparable with controller runs via the Evaluator.
- Single-module and multi-module configs are completely unchanged.
- Adding a baseline config requires only omitting the `logic_module` port and setting
  `"logic_modules": []`; no Python changes.
- The Evaluator can compare baseline vs. controller results directly from their respective
  result directories.

---

## ADR 2026-06-26: Generalize Simulation to Environment

### Status

Accepted.

### Context

The platform was built with a single concrete simulation environment in mind (SUMO via TraCI), and all
naming reflected that: the config key was `"simulation"`, the source file was `simulation_sumo.py`,
the TCP component name was `"simulation"`, and lifecycle topics were `"simulation_started"` /
`"simulation_stopped"`. This made the framework sound SUMO-specific even though the Orchestrator's
message contract is fully general and could connect to a real-world pilot city deployment just as
easily as a microscopic traffic simulator.

### Decision

All references to the "simulation" concept as a component role are replaced by the more general term
"environment":

- The top-level config key `"simulation"` is renamed to `"environment"`. A mandatory `"type"` field
  selects the implementation; the only currently supported value is `"sumo"`.
- The SUMO-specific sub-key `"sumo_details"` is renamed to `"settings"` (type-agnostic; the `"type"` field already
  identifies the environment). Inner keys are cleaned to `"binary"`, `"config_file"`, and `"label"`.
- The `"simulation_measurements"` key in `"setup"` is renamed to `"measurements"` for generality.
- The port key `"simulation"` in `communication.ports` is renamed to `"environment"`.
- `src/simulation_sumo.py` → `src/environment_sumo.py`; class `Simulation` → `SumoEnvironment`;
  `NAME = "simulation"` → `NAME = "environment"`.
- TCP lifecycle topics: `"simulation_started"` → `"environment_started"`;
  `"simulation_stopped"` → `"environment_stopped"`.
- Orchestrator: `self.simulation` → `self.environment`; `_configure_simulation` →
  `_configure_environment`; `_send_step_to_simulation` → `_send_step_to_environment`;
  `self.simulation_running` → `self.environment_running`. Adds `_ENVIRONMENT_TYPES` dict for
  type-string → class dispatch (mirrors the existing `_LOGIC_MODULE_TYPES` pattern).

### Consequences

- Exactly one environment is allowed per configuration (unchanged constraint, now explicit in naming).
- Adding a new environment type (e.g., `"pilot_vienna_live"`) requires only implementing the
  `"step"` / `"apply_and_advance"` message contract and registering the class in `_ENVIRONMENT_TYPES`.
- All existing configs must be updated to use `"environment"` / `"sumo"` / `"measurements"` keys —
  no backward-compatibility shim is provided.
- The term "environment" accurately covers both simulation environments (SUMO) and real-world pilot
  city deployments, making the framework's scope clear.

---

## ADR 2026-05-31: TCP JSON-Line FSM Component Architecture

### Status

Accepted.

### Context

The platform needed a small one-class-per-file structure while keeping SUMO
simulation, controller logic, routing, and recording as separate components. All
component communication happens over TCP on localhost with the orchestrator managing
message routing.

### Decision

The platform runs finite-state-machine components over localhost TCP:

- `Simulation` owns TraCI/SUMO, computes phase queue metrics, and sends traffic state messages.
- `FixedCycleController`, `MaxPressureController`, and `PriorityPassController` implement alternative
  traffic-light control strategies.
- `Orchestrator` routes JSON-line messages between components and mirrors communication to the recorder.
- `Recorder` appends routed communication to a JSON-lines text log.
- Configuration files (JSON) hold scenario-specific settings.
- `run.py` loads configuration, starts components in order, waits for simulation
  completion, and stops components in reverse order.

Messages are JSON objects terminated by newlines. The orchestrator is the only router, so components
only need to know their own TCP listener and the orchestrator endpoint.

### Consequences

- The prototype is easy to inspect and run as a self-contained folder, and runtime settings plus
  the active logic module can be edited without touching Python code.
- Components remain process-bound for now, but their TCP contract allows later separation into
  independent processes.
- The FSM and TCP server code is intentionally duplicated across files to preserve the
  one-class-per-file shape requested for readability.

---

## ADR 2026-06-25: Orchestrator as Sole Orchestrator

### Status

Accepted.

### Context

Previously, `run.py` wired all components and the `Simulation` drove its own step loop autonomously.
The measurement types collected by the simulation were configured explicitly by the user in the JSON
config under `setup.simulation_measurements.sumo.lane_measurements.enabled`. This created two problems:
the entry point was responsible for knowing all component internals, and the user had to keep the
measurement list manually in sync with the logic module type (a MaxPressure run should not collect
`upp_bids`).

### Decision

The `Orchestrator` is now the sole orchestrator:

- `Orchestrator.configure()` accepts the **full** JSON configuration, creates `Recorder`, `Controller`,
  and `Simulation` internally. `run.py` is reduced to parsing CLI arguments and calling
  `Orchestrator.start()` / `Orchestrator.wait_until_done()`.
- Each logic module class exposes `get_required_measurements() -> list[str]`. The Orchestrator calls this
  after instantiating the controller and passes the result to the Simulation. The `"enabled"` key is
  removed from all configuration files.
- The Simulation is **passive**: its `_run_loop` waits on `step_event` at the top of each iteration.
  The Orchestrator drives the loop by intercepting three message topics in `_route()`:
  - `"simulation_started"` → sends first `"step"` to simulation
  - `"logic_command"` (from controller, with `payload.type == "traffic_light_command"`) → transforms into `"apply_and_advance"` + next `"step"`
  - `"simulation_stopped"` → sets `done_event`, stops routing

Two new orchestrator→simulation message topics:
- `"step"` — begin next iteration (collect state, send traffic_state)
- `"apply_and_advance"` — apply the merged logic commands and advance the environment by one step

The internal step sequence inside `_run_step` is unchanged: spawn → track → collect → send state →
wait for apply → apply → simulationStep.

### Consequences

- `run.py` is a thin (~70 line) entry point; no knowledge of component internals.
- Adding a new logic module type only requires implementing `get_required_measurements()` — the
  orchestrator and simulation adapt automatically.
- Swapping the simulation environment requires implementing the `"step"` and `"apply_and_advance"`
  message handlers; no changes to the orchestrator or controllers.
- The `"enabled"` list is removed from all JSON config files; measurement selection is automatic.
- The Environment cannot run standalone without an Orchestrator (by design — it waits for `step_event`).

---

## ADR 2026-06-25: Persistent TCP Connections

### Status

Accepted.

### Context

Each simulation step generated ≥7 short-lived loopback TCP connections (one per
`_forward` / `_send_message` call across all components). After closing, each
connection enters the OS TIME_WAIT state (≈30 s on macOS). At high step rates (e.g.
SUMO-GUI running without a forced delay), the ephemeral port table fills up and new
`create_connection` calls fail with `EADDRNOTAVAIL`. All senders silently stored this
error, so the simulation hung indefinitely at `step_event.wait()` (which had no
timeout). This was reproducible around step 2317 on fast machines.

### Decision

All senders (`Orchestrator._forward`, `Simulation._send_message`,
`*LogicModule._send_message`) now maintain a **persistent socket** to their target.
The socket is created on first use and reused for all subsequent messages. On
`OSError` the socket is closed and a reconnect is attempted on the next send.

All receivers (`_handle_client` in every component) now parse messages **line-by-line**
from the persistent connection (instead of buffering until EOF), so they process
messages as they arrive.

A 30-second timeout was added to `step_event.wait()` in `Simulation._run_loop`.
If no `"step"` signal is received within 30 s, the simulation raises `TimeoutError`
and fails loudly rather than hanging silently.

### Consequences

- TIME_WAIT connections drop from 7 per step to 0 for a typical run (one persistent
  connection per channel, established once at startup and kept open).
- `_handle_client` loops now poll `stop_event` on a 1-second `recv` timeout, so
  threads exit cleanly within 1 s of `stop()` being called.
- The receiver side now processes messages as they arrive (lower latency), rather
  than batching until the sender closes the connection.
- Connection failures surface as `last_error` on the component (existing behaviour)
  plus a reconnect attempt on the next message; the system is tolerant of transient
  connection drops.

---

## ADR 2026-06-25: Rename "Controller" Slot to "Logic Module"

### Status

Accepted.

### Context

The pluggable component connected to the Orchestrator was called "controller" throughout
the codebase and configuration files. Future extension work may plug in demand models,
pricing engines, or other non-controller logic that still communicates via the same
traffic-state → command interface. Calling it "controller" would be misleading for
those use cases.

### Decision

The component slot is renamed from `"controller"` to `"logic_module"` everywhere:

- The `NAME` constant in all three controller classes changes to `"logic_module"`.
- The config section key changes from `"controller"` to `"logic_module"` in all JSON configs.
- The port key in `communication.ports` changes from `"controller"` to `"logic_module"`.
- The Orchestrator attribute `self.controller` → `self.logic_module`; method
  `_configure_controller` → `_configure_logic_module`; dict `_CONTROLLER_TYPES` →
  `_LOGIC_MODULE_TYPES`; type alias `_AnyController` → `_AnyLogicModule`.
- All `_send_message("controller", ...)` calls in `simulation_sumo.py` become
  `_send_message("logic_module", ...)`.
- The orchestrator's routing check `sender == "controller"` becomes `sender == "logic_module"`.

The three existing controller implementations keep their class names and all logic unchanged.

### Consequences

- Existing configurations must use `"logic_module"` as the port key and top-level section name.
- The term "logic module" is broader, accommodating future non-controller plugins without
  renaming again.
- For the current demonstration setup, only controller-type logic modules are used.

**Follow-up (2026-06-25):** Logic module `type` identifier strings were also prefixed with `"controller_"`:
`"fixed_cycle"` → `"controller_fixed_cycle"`, `"max_pressure"` → `"controller_max_pressure"`,
`"priority_pass"` → `"controller_priority_pass"`. This makes the type value self-describing when
read in a config file — even without the section heading, the reader knows what kind of logic module is plugged in.

---

## ADR 2026-06-25: Multi-Logic-Module Support

### Status

Accepted.

### Context

The Orchestrator previously wired exactly one logic module per run. Generalising the framework
to support pluggable combinations of logic modules (e.g., a demand model + a signal controller
running in tandem) required a structural change in the configuration schema and the Orchestrator
routing logic.

### Decision

The configuration key `"logic_module"` (a single object) is replaced by `"logic_modules"` (an
ordered array of objects). The Orchestrator is updated to:

- Instantiate all entries in the array as separate logic module objects in order.
- Port assignment: index 0 falls back to the `"logic_module"` port key for backward compatibility
  with existing single-module configs; index `i > 0` requires `"logic_module_i"` in
  `communication.ports`.
- Start all modules in array order (with the configured startup pause between each), and stop them
  in reverse order.
- Intercept `"traffic_state"` in `_route()` and fan it out to every logic module simultaneously
  (replacing the previous passthrough to a single target).
- Accumulate `"logic_command"` responses (with `payload.type == "traffic_light_command"`) in a per-step counter; once all N modules have
  replied, merge their command dicts and send a single `"apply_and_advance"` to the simulation.
  Commands for the same key from multiple modules are merged with last-write-wins
  semantics (non-deterministic for conflicting assignments).
- Collect required measurements as the union (preserving order) of each module's
  `get_required_measurements()` return value.

`run.py` uses `logic_modules[0]["type"]` for the result directory name and checks all entries for
`"controller_priority_pass"` to determine whether priority-pass plots should be shown.

### Consequences

- Existing single-module configurations remain valid by wrapping the existing object in a one-element
  array and keeping the `"logic_module"` port key unchanged.
- Adding a second logic module to a run requires only a new array entry in the config and a new port
  key in `communication.ports` (no Python changes).
- With a single module the behaviour is identical to before: the first and only `"logic_command"` response immediately triggers `"apply_and_advance"`.
- Conflicting command assignments from multiple modules are merged with last-write-wins order;
  callers are responsible for assigning disjoint target sets if determinism is required.

---

## ADR 2026-06-27: Priority Pass Baseline Must Match Max-Pressure at `trade_off = 0`

### Status

Accepted.

### Context

Priority Pass is intended to be a controlled extension of Max-Pressure: the auction FSM should remain the same, and the `trade_off` parameter should be the experiment knob that blends queue-length bids with UPP priority bids. The shipped Priority Pass configs had longer `min_green_duration` and `auction_suspend_duration` values than the matching Max-Pressure configs, causing different phase timing even when priority bids were disabled.

### Decision

The demo and Vienna Priority Pass configs now keep the same auction timing fields as their Max-Pressure counterparts: `transition_duration`, `bidding_strategy`, `auction_winner`, `min_green_duration`, `max_green_duration`, and `auction_suspend_duration`. A regression test asserts that `PriorityPassController` produces the same phase sequence and light FSM state as `MaxPressureController` when `trade_off = 0.0`, even if UPP bids are present in the measurements.

### Consequences

- Setting `trade_off = 0.0` should reproduce Max-Pressure behaviour for the same SUMO random seed.
- Increasing `trade_off` isolates the effect of UPP prioritisation instead of mixing it with changed auction timings.
- Future config changes must preserve timing parity unless intentionally creating a separate experiment variant.
