# FEDORA Platform - Directory Structure

# TODO - OUTDATED STRUCTURE - UPDATE BASED ON NEW STRUCTURE

```
fedora_platform/
├── src/
│   └── fedora_platform/
│       ├── __init__.py
│       ├── components.py          - Abstract FEDORA components and finite-state lifecycle
│       ├── communication.py       - Message bus and transport adapter templates
│       ├── storage.py             - Memory, JSON, and SQLite stores plus storage templates
│       ├── mtm_space.py           - Component container for one MTM Space
│       ├── priority_pass.py       - Vienna Priority Pass implementation
│       └── traffic_model_sumo/    - Legacy SUMO controller, recorder, and simulator code
│           ├── __init__.py
│           ├── Controller.py      - SUMO Priority Pass controller logic
│           ├── Recorder.py        - SUMO data recorder
│           ├── Settings.py        - Legacy SUMO settings holder
│           ├── Simulator.py       - SUMO simulator main class
│           └── SimulationTools.py - Simulation analysis and controller-setting helpers
├── tests/
│   ├── test_core.py               - Core lifecycle, bus, storage, and templates tests
│   └── test_priority_pass.py      - Priority Pass and SUMO adapter tests
├── simple_b/                      - Self-contained TCP/SUMO Priority Pass prototype
│   ├── main.py                    - Configures and starts all simple_b components
│   ├── config.json                 - Local TCP, SUMO, spawning, and controller config
│   ├── simulation.py              - SUMO TraCI FSM and traffic-state publisher
│   ├── controller_fixed_cycle.py  - Fixed-cycle controller FSM
│   ├── controller_max_pressure.py - Max-pressure controller FSM
│   ├── controller_priority_pass.py - Priority Pass controller FSM
│   ├── connector.py               - TCP JSON-line message router FSM
│   ├── recorder.py                - TCP communication logger FSM
│   └── sumo_simulation_files/
│       ├── config.sumocfg  - SUMO configuration
│       ├── demand.xml             - SUMO route definitions
│       ├── network.net.xml        - SUMO network
│       ├── possible_trips.xml      - Trip source data
│       ├── phase_bidder_lanes.json - Per-phase incoming lane groups
│       ├── phase_exit_lanes.json   - Per-phase outgoing lane groups
│       ├── route_distances.json   - Route distance metadata
│       ├── route_durations.json   - Route minimum-duration metadata
│       ├── route_end_edges.json    - Route completion edge metadata
│       ├── route_probabilities.json - Spawn entrance route probabilities
│       ├── route_start_edges.json  - Route start edge metadata
├── models/
│   ├── pilot_vienna/              - SUMO network, demand, route, and phase files
│   ├── pilot_basque_country/
│   ├── pilot_nicosia/
│   ├── pilot_copenhagen/
│   ├── pilot_reggio_emilia/
│   └── pilot_budapest/
├── docs/
│   ├── STRUCTURE.md               - This file
│   ├── DECISIONS.md               - Architectural Decision Records
│   ├── INTEGRATIONS.md            - External tool integrations
│   └── scratchpad.md              - Session working memory
├── memory-bank/                   - Persistent agent context
├── figures/                       - Pilot images and repository banner
├── example/                       - Run scripts
├── runs/                          - Local run artifacts
├── requirements.txt               - Pinned dependencies
├── pyproject.toml                 - Python project metadata
├── README.md
├── .pylintrc
├── .gitignore
└── AGENTS.md
```
