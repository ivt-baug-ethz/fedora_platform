# Product Context: FEDORA Platform

## Platform Overview
The FEDORA Platform is a research platform designed for multimodal traffic management systems. It implements a component-based architecture where optimization modules, simulators, pilot systems, data storage, and communication mechanisms are all treated as stateful components with a shared finite-state machine lifecycle.

## The Priority Pass

The Urban Priority Pass (UPP) is the custom-developed traffic-light control algorithm. It:
- Extends Max-Pressure with a priority bidding mechanism for designated vehicles (e.g. transit)
- Uses an auction to dynamically allocate green time to traffic phases
- Implements a configurable trade-off parameter (tau) between transit priority and network efficiency
- Manages traffic-light phases with minimum green time enforcement
- Must match Max-Pressure exactly at `trade_off = 0.0` for the same measurements/random seed;
  higher values of `trade_off` isolate the effect of UPP priority bids

## Platform Structure

- `src/` — All runtime components (orchestrator, environment adapter, controllers, recorder, evaluator)
- `scenarios/` — Scenario-specific SUMO assets (network, demand, route, phase files)
  - `scenarios/demo/sumo/` — Demo scenario (functional, used for testing)
  - `scenarios/pilot_vienna/` — Vienna pilot SUMO assets (functional)
  - `scenarios/pilot_*/` — Other pilot sites (skeleton directories, not yet integrated)
- `configurations/` — JSON configuration files (one per scenario × controller combination)
- `run.py` — Thin entry point; delegates all lifecycle management to the Orchestrator

## Communication Model

Components communicate over persistent localhost TCP connections using JSON-line messages:
- Each message is a newline-terminated JSON object with `sender`, `target`, `topic`, and `payload`
- The Orchestrator routes messages between Environment, Logic Module(s), and Recorder
- All senders reuse one persistent socket per target (created on first use, reset on OSError)

## Known Limitations or Open Issues
- The Vienna pilot implementation is the only fully functional pilot
- Other pilot directories (pilot_basque_country, pilot_nicosia, etc.) exist but have no working implementations yet
- The platform is currently limited to SUMO simulations, not integration with real hardware
- No specific testing for the other pilot implementations beyond the Vienna pilot
- Dependencies on SUMO and its configuration can cause installation issues
