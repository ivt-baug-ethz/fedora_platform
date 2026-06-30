# Architecture

## Overview

FEDORA separates five core responsibilities across independent components connected by a TCP message bus:

| Component | Role |
|---|---|
| **Environment** | Execution backend (simulation or real deployment) |
| **Logic Module(s)** | Decision-making (one or more, pluggable) |
| **Orchestrator** | Sole controller — creates all sub-components, drives the step loop |
| **Recorder** | Logs all inter-component messages |
| **Storage** | Persists records to files or databases |

## Component Lifecycle (FSM)

Every component is modelled as a finite-state machine. This makes composition explicit and ensures each component manages its own readiness without hidden state.

```
CREATED → CONFIGURED → READY → RUNNING → STOPPED
```

`FAILED` transitions are reachable from any state. `STOPPED` can reconfigure.

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> CONFIGURED: configure()
    CONFIGURED --> READY: resources prepared
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

## Control Loop

The Orchestrator drives a closed loop at the environment's step rate (e.g. ~0.1 s/step for SUMO):

```mermaid
%%{init: {'flowchart': {'curve': 'natural'}, 'theme': 'base'}}%%
graph TB
    Start(["Start: run.py\nLoad config"])

    subgraph startup["Startup Phase"]
        direction LR
        Start -->|Initialize| Con["Orchestrator"]
        Con -->|Initialize| Rec["Recorder"]
        Con -->|Initialize| LMs["Logic Module(s)"]
        Con -->|Initialize| Sim["Environment"]
    end

    startup --> Ready["Pipeline Ready"]

    subgraph loop["Main Simulation Loop"]
        direction TB
        Con0["6.1 Orchestrator\nSends step"]
        Sim1["6.2 Environment\nReads state"]
        Con1["6.3 Orchestrator\nFan-out"]
        LM1["6.4 Logic Module(s)\nCompute decision (×N)"]
        Sim2["6.5 Environment\nApplies & advances"]
        Rec1["6.6 Recorder\nLogs messages"]

        Con0 -->|step| Sim1
        Sim1 -->|traffic_state| Con1
        Con1 -->|fan-out to all| LM1
        LM1 -->|logic commands ×N| Con1
        Con1 -->|apply_and_advance merged commands| Sim2
        Con1 -->|Mirror| Rec1
        Sim2 -->|Done| Con0
    end

    Ready --> loop
    Sim2 --> Check{Environment\ncomplete?}
    Check -->|No| Con0
    Check -->|Yes| End(["Shutdown & Evaluate"])
```

### Step-by-Step

1. Orchestrator sends `step` to Environment → begin new iteration
2. Environment collects current state and publishes `traffic_state`
3. Orchestrator fans `traffic_state` out to all configured Logic Modules simultaneously
4. Each Logic Module independently computes its decision and publishes a `logic_command`
5. Orchestrator accumulates N responses; merges their command dicts; sends single `apply_and_advance` to Environment
6. Environment applies merged commands and advances one step
7. Orchestrator mirrors all messages to Recorder
8. Loop back to step 1, or shut down when the environment signals completion

## Message Format

All messages use a JSON-line envelope over TCP:

```json
{
  "sent_at": 1750000000.0,
  "sender": "environment",
  "target": "logic_module",
  "topic": "traffic_state",
  "payload": {
    "step": 1234,
    "queue_lengths": {"J25": 5, "J26": 12},
    "signal_state": {"J25": "green", "J26": "red"}
  }
}
```

### Message Topics

| Topic | Direction | Description |
|---|---|---|
| `traffic_state` | Environment → Logic Module(s) via Orchestrator | Current environment state observations |
| `logic_command` | Logic Module → Orchestrator | Decision output; `payload.type` identifies command kind |
| `step` | Orchestrator → Environment | Begin next state-collection iteration |
| `apply_and_advance` | Orchestrator → Environment | Apply merged commands and advance one step |
| `get_state` | Orchestrator → Environment / Logic Module(s) | Request a snapshot of internal state (sent when state polling is active) |
| `state_report` | Environment / Logic Module(s) → Orchestrator | Response to `get_state`; contains only the fields enabled in `state_polling` config |
| `environment_started` / `environment_stopped` | Environment → Orchestrator | Lifecycle signals |
| `communication` | Orchestrator → Recorder | Mirror of all routed messages (including `state_report` responses) |

## Communication Layer

All communication is JSON-line over persistent TCP connections on localhost. Default port assignments:

| Component | Default address |
|---|---|
| Orchestrator | `127.0.0.1:51000` |
| Environment (SUMO) | `127.0.0.1:51001` |
| Logic Module | `127.0.0.1:51002` |
| Recorder | `127.0.0.1:51003` |

Connections are persistent (one socket per target, reused for all messages). Receivers parse line-by-line; each newline-terminated JSON string is one message.
