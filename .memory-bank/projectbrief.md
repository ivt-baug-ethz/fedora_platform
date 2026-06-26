# Project Brief: FEDORA Platform

## Project Name and Purpose
The FEDORA (Federated European Digital Mobility) Platform is a Python 3.13 research platform for multimodal traffic management. It provides a reusable framework for traffic management pilots with support for optimization, simulation, pilot systems, data storage, and communication. The platform is designed to support federated digital ecosystems where public authorities, transport operators, industry, researchers, and citizens can cooperate through secure data sharing and advanced digital tools.

## Primary Users
- Researchers working on traffic management and mobility optimization
- Pilot operators managing real-world traffic management pilots
- Developers implementing traffic management algorithms and systems
- Infrastructure planners evaluating mobility solutions for urban areas

## Scope
### In Scope
- Core framework for creating MTM Spaces with components that have finite-state lifecycles
- Optimization modules for traffic management
- Simulation capabilities using SUMO (Simulation of Urban Mobility) 
- Pilot systems that bridge field-side operations and digital control
- Communication mechanisms for component-to-component messaging
- Data storage solutions including memory, JSON, and SQLite backends
- Vienna Priority Pass implementation as a representative pilot system

### Out of Scope
- Integration with real-world traffic infrastructure (that's a pilot-specific concern)
- Web interfaces or user dashboards (planned for future extensions)
- Real-time control systems for actual traffic lights (implemented in simulation)

## Pilot Sites
Based on the `models/` directory, the following pilot cities have infrastructure:
- **Vienna, Austria** - Primary pilot for the Priority Pass implementation
- **Basque Country, Spain** - Pilot focused on freight logistics hub integration
- **Nicosia, Cyprus** - Pilot focused on integration of aerial and road traffic services
- **Copenhagen, Denmark** - Pilot focused on foresight simulations for future mobility
- **Reggio Emilia, Italy** - Pilot focused on demand management strategies
- **Budapest, Hungary** - Pilot focused on cross-modal management of road and inland waterways

## Success Criteria
A "working correctly" platform means:
- All core components can be instantiated with proper lifecycle management
- The Priority Pass implementation from Vienna pilot works end-to-end: optimization, simulation, and pilot coordination
- All simulation dependencies (SUMO) can be properly installed and configured
- Communication between components works correctly using the in-memory message bus
- Test suite passes completely
- Results can be stored in the SQLite interaction store
- Example scripts run without error

## Key Constraints
- Python 3.13 only (specific version required)
- SUMO dependency required for simulation capabilities
- No absolute file paths - all paths must be relative to the project
- All code must be compatible with the established component lifecycle architecture
- Components must follow the finite-state machine pattern
- No hardcoding of network or intersection names