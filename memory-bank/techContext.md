# Technical Context: FEDORA Platform

## Development Environment

### Python 3.13
- The platform requires Python 3.13 specifically
- Virtual environment setup: `python3.13 -m venv venv && source venv/bin/activate`
- All development should be done in the virtual environment
- Dependencies are managed via requirements.txt

### Requirements and Dependencies

#### numpy==2.4.4
Used for mathematical operations in traffic simulation calculations

#### sumolib==1.19.0
Python library for SUMO (Simulation of Urban Mobility) integration - provides utilities for SUMO configuration

#### traci==1.19.0
Python API for SUMO (TraCI - Traffic Control Interface) - allows communication with SUMO simulation

#### pytest==8.4.2
Testing framework used for running unit tests in the test suite

### SUMO Setup on macOS
- Version required: SUMO 1.19.0 or compatible
- Installation via Homebrew: `brew install sumo`
- The `SUMO_HOME` environment variable must be set
- Verification: `sumo --version` should display the installed version

## Running Examples

### Priority Pass Example
To run the Priority Pass example:
1. Ensure SUMO is installed and available in PATH
2. Run: `python example/run_priority_pass.py --run`
3. Expected output: JSON-formatted simulation results including traffic metrics and performance data

## Test Suite
Tests are run with:
```bash
pytest src/tests/ -v
```
Tests cover:
- Core component lifecycle management (test_core.py)
- Priority Pass specific functionality (test_priority_pass.py)
- All components are tested for proper configuration and behavior

## Code Quality
### Linting
Code is linted using pylint with rules defined in .pylintrc:
- All warnings should be addressed before committing
- Custom suppressions are specified in the .pylintrc file

## Common Failure Modes

### TraCI Connection Refused
- SUMO not installed or not in PATH
- SUMO binary path not correctly configured in PriorityPassConfig

### Import Errors
- Missing dependencies in virtual environment
- Improper Python path configuration

### Development Issues
- TODO/FIXME markers indicate incomplete functionality or issues:
  - No functional implementations for the other pilot sites (basque_country, nicosia, copenhagen, reggio_emilia, budapest)
  - Only Vienna pilot implementation is complete and functional

## Development Notes
- All file paths should be relative - no absolute paths are allowed
- Data should be stored in the SQLite database when available, not hardcoded in code or log files
- Components must follow the defined lifecycle state machine pattern
- The codebase is designed to be portable and work without any external dependencies except SUMO