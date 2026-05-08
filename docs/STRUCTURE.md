# FEDORA Platform - Directory Structure

```
fedora_platform/
├── src/
│   ├── __init__.py
│   ├── components.py          – Abstract FEDORA components and finite-state lifecycle
│   ├── communication.py       – Message bus and transport adapter templates
│   ├── storage.py             – Memory, JSON, and SQLite stores plus storage templates
│   ├── mtm_space.py           – Component container for one MTM Space
│   ├── priority_pass.py       – Vienna Priority Pass implementation
│   └── traffic_model_sumo/    – SUMO controller, recorder, and microscopic simulator code
│       ├── __init__.py
│       ├── Controller.py      – SUMO Priority Pass controller logic
│       ├── Recorder.py        – SUMO data recorder
│       ├── Simulator.py       – SUMO simulator main class
│       └── SimulationTools.py – Simulation analysis tools
├── models/
│   ├── pilot_vienna/          – SUMO network, demand, route and phase files
│   ├── pilot_basque_country/
│   ├── pilot_nicosia/
│   ├── pilot_copenhagen/
│   ├── pilot_reggio_emilia/
│   └── pilot_budapest/
├── docs/                      – Documentation files
│   ├── STRUCTURE.md           – This file
│   ├── DECISIONS.md           – Architectural Decision Records
│   ├── INTEGRATIONS.md        – External tool integrations
│   └── scratchpad.md          – Session working memory
├── figures/                   – Pilot images and repository banner
├── example/                   – Run scripts (e.g. run_priority_pass.py)
├── fedora_demo.py             – Command-line utility to demonstrate platform
├── requirements.txt           – Pinned dependencies
├── .pylintrc                  – Pylint configuration
└── AGENTS.md                  – This file
```
