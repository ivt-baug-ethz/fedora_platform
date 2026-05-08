# Product Context: FEDORA Platform

## Platform Overview
The FEDORA Platform is a research platform designed for multimodal traffic management systems. It implements a component-based architecture where optimization modules, simulators, pilot systems, data storage, and communication mechanisms are all treated as stateful components with a shared finite-state machine lifecycle.

## MTM Space Concept
An MTM Space is a container that coordinates related components through a shared communication system. It allows different components (optimizers, simulators, pilots, data storages) to work together in a synchronized way while maintaining their individual responsibilities.

## The Priority Pass
The Priority Pass is a traffic-light control algorithm implemented in the Vienna pilot. It:
- Uses auctions to dynamically allocate green time to traffic phases
- Implements a trade-off parameter between fairness and efficiency
- Operates within SUMO simulations in the Vienna pilot area
- Manages traffic-light phases with minimum green time enforcement
- Supports traffic-light phase control using a finite state machine in SUMO

## Pilot Structure
The platform uses the src/ codebase to define the reusable components and the models/pilot_* directories to contain pilot-specific assets:
- src/ contains all core components and implementation
- models/pilot_vienna/ contains SUMO network, demand, route, and phase files for the Vienna pilot (primary pilot)
- Other models/pilot_* folders exist for additional pilot sites but have no specific functional implementation yet

## Communication Model
Components communicate through a message bus:
- Messages are typed (topic-based) and carry payloads
- Components register with the message bus to receive messages
- Messages flow through an in-memory bus for local testing (InMemoryMessageBus)
- Components can publish responses to specific topics to trigger downstream actions

## Storage Model
The platform supports multiple storage backends:
- **Memory**: For testing and temporary storage
- **JSON Files**: One JSON file per key for readable artifacts  
- **SQLite**: Full-featured local database for storing records and interaction logs
- The SQLite interaction store can optionally log every message published to the bus

## Known Limitations or Open Issues
- The Vienna pilot implementation is the only fully functional pilot
- Other pilot directories (pilot_basque_country, pilot_nicosia, etc.) exist but have no working implementations yet
- The platform is currently limited to SUMO simulations, not integration with real hardware
- No specific testing for the other pilot implementations beyond the Vienna pilot
- Dependencies on SUMO and its configuration can cause installation issues