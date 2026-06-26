# FEDORA Platform

A modular orchestration framework for integrating traffic logic modules with compatible simulation environments or real-world deployment sites.

## What is FEDORA?

FEDORA decouples **decision logic** from **environment execution** through a JSON-line message-passing architecture over TCP. An Orchestrator routes state observations from the environment to all connected logic modules, and feeds their merged decisions back to the environment each step.

The framework is demonstrated here at the example of traffic signal control, but the architecture is not specific to any domain: any logic module that produces a compatible command in response to an environment state observation can be plugged in.

## Key Features

- **Pluggable environment slot** — any environment implementing the `step` / `apply_and_advance` message contract can be connected (simulations or real deployments)
- **Pluggable logic module stack** — one or more logic modules receive environment state and produce commands each step; outputs are merged before application
- **Finite-state machine lifecycle** for all components — makes composition explicit and testable
- **Orchestrator-driven control loop** — sole orchestrator drives component lifecycle and the step loop
- **TCP-based inter-component communication** with JSON-line message format over localhost
- **Persistent logging** of all inter-component messages for post-run analysis

## Demonstrators

Three traffic signal control strategies are included as logic module demonstrators:

| Controller | Strategy | Use case |
|---|---|---|
| Fixed-Cycle | Pre-timed phase schedules | Baseline, predictable operation |
| Max-Pressure | Queue-pressure auction | Adaptive demand response |
| Urban Priority Pass (UPP) | Max-Pressure + priority bidding | Transit-priority coordination |

## Quick Start

```bash
git clone https://github.com/sjschlapbach/fedora_platform.git
cd fedora_platform
python3.13 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py
```

See [Getting Started](getting-started.md) for full setup instructions, including SUMO installation.
