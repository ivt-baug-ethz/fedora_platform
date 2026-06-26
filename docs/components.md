# Components

## Orchestrator (`src/orchestrator.py`)

The sole orchestrator of the platform. It reads the full JSON configuration, creates all sub-components (Recorder, Logic Modules, Environment), drives the step loop, and routes messages between components.

**Responsibilities:**
- Instantiate and lifecycle-manage all other components
- Drive the `step` / `apply_and_advance` loop
- Fan-out `traffic_state` to all Logic Modules simultaneously
- Merge `logic_command` responses and forward the combined command to the Environment
- Mirror all traffic to the Recorder
- Query each Logic Module's measurement requirements and pass them to the Environment

## Environment: SUMO (`src/environment_sumo.py`)

Implements the `sumo_simulation` environment type. Manages the SUMO/TraCI connection lifecycle and exposes traffic state over TCP.

**Responsibilities:**
- Connect to SUMO via TraCI
- Wait passively for `step` messages before each iteration
- Collect queue lengths, vehicle positions, and signal states
- Apply traffic light commands received via `apply_and_advance`
- Spawn vehicles and manage simulation time

**Configuration key:** `"type": "sumo_simulation"` in the `"environment"` config block.

## Logic Modules (Controllers)

Logic modules receive `traffic_state` observations and return `logic_command` decisions. All three included modules share this interface and can be composed without code changes.

### Fixed-Cycle (`src/controller_fixed_cycle.py`)

Pre-timed phase schedules with configurable cycle lengths and offsets. Simple and predictable; cannot adapt to demand changes.

### Max-Pressure (`src/controller_max_pressure.py`)

Real-time responsive control based on queue pressure (difference in queue lengths at opposing approaches). Uses an auction mechanism to select the highest-pressure phase. Adapts to demand but may be unstable under high congestion.

### Urban Priority Pass (`src/controller_priority_pass.py`)

Extends Max-Pressure with a priority bidding mechanism for designated vehicles (e.g. public transit). Balances network-wide efficiency with transit reliability via a configurable trade-off parameter.

## Recorder (`src/recorder.py`)

Listens on a dedicated TCP port for message copies from the Orchestrator. Writes all inter-component communication to log files for post-simulation analysis.

**Output:**
- `logs/{scenario}_{logic_module}/communication_log.txt` — all messages
- `logs/{scenario}_{logic_module}/vehicle_log.jsonl` — vehicle arrival/departure events

## Evaluator (`src/evaluator.py`)

Post-simulation analysis component. Reads vehicle event logs, calculates travel times and delays (separated by priority status), generates visualizations, and exports summary statistics.

**Output:** `results/{scenario}/{logic_module}/`

## Entry Points

| Script | Purpose |
|---|---|
| `run.py` | Main entry point: parses CLI args, starts Orchestrator, runs Evaluator after simulation completes |
