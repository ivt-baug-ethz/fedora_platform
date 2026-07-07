# Project Overview

**FEDORA Platform** (Federated European Digital Mobility) is a Python **3.13** research
platform for multimodal traffic management. It is a **modular orchestration framework**
that connects pluggable traffic **logic modules** (e.g. signal controllers, demand models)
to compatible execution **environments** (simulation or, in future, real-world pilot sites)
through a JSON-line message-passing architecture over localhost TCP. Decision logic is
decoupled from environment execution: an **Orchestrator** routes state observations from the
environment to all connected logic modules and feeds their merged decisions back each step.

**Demonstrator (this repo):** traffic signal control. Three controllers —
**Fixed-Cycle**, **Max-Pressure**, and the custom **Urban Priority Pass (UPP)** — plus a
**baseline** (SUMO's built-in plans), driven against **SUMO/TraCI** as the environment. The
architecture is not signal-specific: any logic module producing a compatible command, and
any environment implementing the `step` / `apply_and_advance` contract, can be plugged in.

## The Urban Priority Pass (UPP)
Custom traffic-light control algorithm. Extends Max-Pressure with a **priority bidding**
mechanism (auction) that allocates green time to phases, trading transit priority against
network efficiency via a configurable **`trade_off` (tau)** parameter, with minimum-green
enforcement. **Parity invariant:** at `trade_off = 0.0`, UPP bids are ignored and UPP must
produce exactly the same phase commands as Max-Pressure for the same measurements and random
seed. Higher `trade_off` is the experiment knob isolating UPP's priority effect.

## Primary users
Traffic-management researchers, pilot operators, algorithm/systems developers, infrastructure
planners evaluating urban mobility solutions.

## Scope
- **In scope:** the orchestration framework and component FSM lifecycle; signal controllers;
  SUMO simulation; evaluation/metrics; recording; the Vienna Priority Pass pilot.
- **Out of scope:** real hardware integration (pilot-specific), web dashboards, real-time
  control of physical signals (only simulated).

## Pilot sites (assets under `scenarios/`)
- **Vienna, AT** — primary pilot; only fully functional one (Priority Pass).
- **Basque Country (ES), Nicosia (CY), Copenhagen (DK), Reggio Emilia (IT), Budapest (HU)** —
  skeleton scenario directories, not yet code-integrated.

## Success criteria ("working correctly")
- All core components instantiate with correct FSM lifecycle management.
- The Vienna Priority Pass runs end-to-end (control → simulation → recording → evaluation).
- SUMO installs/configures and the demo + Vienna scenarios run to completion.
- Inter-component TCP messaging works without port exhaustion.
- The full test suite passes; example configs run without error; results are recorded/evaluated.

## Status / known limitations
Vienna + the demo scenario are functional and green; other pilots are placeholders. The
platform is currently SUMO-only (no real-hardware backend). SUMO install/config issues are the
most common setup failure mode (see `mem:integrations` → *Common failure modes*).

## Roadmap / planned (not yet implemented)
Functional implementations for the other five pilot sites; integration with real traffic
infrastructure (the swappable-environment slot is designed for this); additional communication
protocols and storage backends; optional web-UI components; optionally splitting the FSM
components into independent processes.

See also: `mem:codebase_structure`, `mem:system_patterns`, `mem:integrations`,
`mem:code_style_and_conventions`, `mem:suggested_commands`, `mem:task_completion_checklist`,
`mem:tools_and_skills`, `mem:architectural_decisions`, `mem:ai_tracking_system`.
