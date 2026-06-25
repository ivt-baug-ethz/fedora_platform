# System Patterns: FEDORA Platform

## Component Lifecycle

### Finite State Machine Diagram
```
[*] --> CREATED
CREATED --> CONFIGURED: configure()
CONFIGURED --> READY: resources prepared
READY --> RUNNING: start()
RUNNING --> PAUSED: pause()
PAUSED --> RUNNING: start()
RUNNING --> STOPPED: stop()
READY --> STOPPED: stop()
CONFIGURED --> STOPPED: stop()
CREATED --> STOPPED: stop()
CREATED --> FAILED: fail()
CONFIGURED --> FAILED: fail()
READY --> FAILED: fail()
RUNNING --> FAILED: fail()
PAUSED --> FAILED: fail()
FAILED --> STOPPED: stop()
STOPPED --> CONFIGURED: configure()
```

### States
- **CREATED**: Component is instantiated but not configured
- **CONFIGURED**: Component has been configured with parameters but is not ready to run
- **READY**: Component is ready to start running (resources prepared)
- **RUNNING**: Component is actively processing
- **PAUSED**: Component has been temporarily suspended
- **STOPPED**: Component has been stopped, can be reconfigured
- **FAILED**: Component has encountered an error and cannot recover

### Valid Transitions
- CREATED → CONFIGURED, STOPPED, FAILED
- CONFIGURED → READY, STOPPED, FAILED
- READY → RUNNING, STOPPED, FAILED
- RUNNING → PAUSED, STOPPED, FAILED
- PAUSED → RUNNING, STOPPED, FAILED
- STOPPED → CONFIGURED, FAILED
- FAILED → STOPPED

### Abstract Methods
- `step(self)` - Advance component by one logical step
- `configure(self, configuration)` - Configure component with settings
- `start(self)` - Start the component running
- `stop(self)` - Stop the component
- `pause(self)` - Pause the component temporarily
- `fail(self)` - Signal component has failed

## Class Hierarchy

### Main Component Classes
- FedoraComponent (base class for all components)
  - OptimizationModule (abstract - computes control decisions)
    - PriorityPassTrafficOptimizer (Vienna pilot implementation)
  - SimulatorModule (abstract - runs simulations)
    - MicroscopicTrafficSumoSimulator (SUMO-based simulator)
  - PilotSystem (abstract - represents field side pilots)
    - ViennaPilot (Vienna pilot implementation)
  - DataStorage (abstract - persistent data store)
    - InMemoryDataStore (volatile storage for testing)
    - JSONFileDataStore (JSON file-based storage)
    - SQLiteInteractionStore (SQLite-based storage)

### Communication Classes
- MessageBus (protocol)
  - InMemoryMessageBus (implementation for local testing)

### Supporting Classes
- MTMSpace (container for coordinating components)
- ComponentState (enumeration of possible component states)
- ComponentRole (enumeration of component types)
- Message (data structure for messages)
- TransitionError (exception for invalid state transitions)

## Module Dependency Graph

### src/fedora_platform/
- components.py: Core component architecture, lifecycle, and message protocols
- communication.py: Message bus and communication templates
- storage.py: Storage backends and templates
- mtm_space.py: MTM Space coordination container
- priority_pass.py: Priority Pass implementation for Vienna pilot  
- traffic_model_sumo/: SUMO controller, recorder, and simulator code
  - Controller.py: SUMO traffic controller implementation
  - Recorder.py: SUMO data recording and analysis
  - Settings.py: SUMO settings configuration
  - SimulationTools.py: Analysis and reporting tools for simulations
  - Simulator.py: SUMO simulation loop management

### Dependencies
- components.py depends on standard library (abc, enum, dataclasses, typing)
- communication.py depends on components.py and collections, dataclasses, typing
- storage.py depends on components.py, json, sqlite3, pathlib, contextlib, and typing
- mtm_space.py depends on components.py and communication.py
- priority_pass.py depends on components.py, dataclasses, pathlib, typing, and modules from traffic_model_sumo
- traffic_model_sumo/* depends on numpy, traci, pathlib, dataclasses, typing

## SUMO Integration Pattern

### TraCI Initialization and Termination
- TraCI connection is initialized in Simulator.open_simulation() 
- TraCI connection is terminated in Simulator.close_simulation()
- The connection lifecycle is managed by the MicroscopicTrafficSumoSimulator class

### TraCI Connection Ownership
- The MicroscopicTrafficSumoSimulator class owns the TraCI connection lifecycle
- It manages opening and closing of the simulation environment

### Recorder and Simulator Relationship
- The Recorder class gathers and processes data during simulation
- The Simulator class coordinates with the Recorder to manage data collection during the simulation loop
- The two work together to provide structured simulation results

## Key Design Patterns

### Finite State Machine Pattern
- All components implement a common finite-state machine with transitions for lifecycle management
- Pattern is used for both the component lifecycle and the Priority Pass controller state machine

### Component Pattern (Observer Pattern)
- Components communicate through a message bus using publish/subscribe
- Components can receive messages via their `receive()` method and publish messages via `publish()`

### Factory Pattern
- Used in `available_communication_templates()` and `available_storage_templates()` to define configuration blueprints for communication and storage systems
- PriorityPassTrafficOptimizer creates traffic-light control settings based on parameters

### Adapter Pattern
- The MicroscopicTrafficSumoSimulator acts as an adapter around the SUMO simulation environment
- Different storage backend implementations (InMemoryDataStore, JSONFileDataStore, SQLiteInteractionStore) are adapters for different storage systems

### Strategy Pattern
- Multiple storage implementations represent different strategies for data persistence
- Communication templates represent different strategies for component-to-component communication

## Core Application Pattern (TCP FSM Controllers)

The main application is built from modular FSM-based components in `src/`, orchestrated by the Orchestrator:

- **`run.py`** (root level) — Thin entry point (~70 lines): parses CLI args, creates `Orchestrator`, calls `start()` / `wait_until_done()`, runs Evaluator
- **`src/orchestrator.py`** — **Platform orchestrator**: reads full JSON config, creates and starts Recorder/Controller/Simulation, drives the simulation step loop via `"step"` and `"apply_and_advance"` messages
- **`src/simulation_sumo.py`** — Passive simulation wrapper: waits for `"step"` command from Orchestrator before each iteration; measurement types injected by Orchestrator from controller requirements
- **`src/controller_fixed_cycle.py`** — Fixed-cycle controller FSM; `get_required_measurements()` returns `[]`
- **`src/controller_max_pressure.py`** — Max-pressure controller FSM; `get_required_measurements()` returns `["queue_lengths"]` or `["weighted_queue_lengths"]` based on bidding_strategy
- **`src/controller_priority_pass.py`** — Priority Pass controller FSM; `get_required_measurements()` returns queue measurement + `"upp_bids"`
- **`src/recorder.py`** — Listens on TCP, logs routed communication to files in `logs/`

### Simulation Step Loop (Orchestrator-Driven)

```
Orchestrator.start() → recorder.start() → logic_module[0].start() → ... → simulation.start()
    ↓
simulation sends "simulation_started"
    ↓
Orchestrator._route() intercepts → sends "step" to simulation
    ↓
simulation collects measurements → sends "traffic_state" to orchestrator
    ↓
Orchestrator intercepts "traffic_state" → fans out to ALL logic modules
    ↓
each logic module computes plan → sends "traffic_light_command" to orchestrator
    ↓
Orchestrator accumulates responses; once all N modules replied:
  → merges command dicts → sends "apply_and_advance" + next "step" to simulation
    ↓
simulation applies commands → advances SUMO → collects next measurements → ...
    ↓
simulation sends "simulation_stopped" → Orchestrator.done_event.set()
```

Config supports N logic modules via `"logic_modules": [...]` array. Single-module case (N=1)
is behaviorally identical to the previous single-module design.

All components use explicit state constants and transition maps. Runtime messages are JSON objects
sent over localhost TCP, terminated by newlines. Configuration is loaded from `configurations/`
directory and scenario-specific SUMO files are loaded from `scenarios/`.
