# Configuration

All runtime settings are loaded from a JSON configuration file. The naming convention is `{scenario}_sumo_{logic_module}_config.json` (or `{scenario}_sumo_baseline_config.json` for runs without a controller).

## Configuration Files

| File | Scenario | Logic module |
|---|---|---|
| `demo_sumo_baseline_config.json` | Demo | None (SUMO default signal plans) |
| `demo_sumo_fixed_cycle_config.json` | Demo | Configurable Fixed-Cycle |
| `demo_sumo_max_pressure_config.json` | Demo | Max-Pressure |
| `demo_sumo_priority_pass_config.json` | Demo | Urban Priority Pass |
| `vienna_sumo_baseline_config.json` | Vienna pilot | None (SUMO default signal plans) |
| `vienna_sumo_fixed_cycle_config.json` | Vienna pilot | Configurable Fixed-Cycle |
| `vienna_sumo_max_pressure_config.json` | Vienna pilot | Max-Pressure |
| `vienna_sumo_priority_pass_config.json` | Vienna pilot | Urban Priority Pass |

## Configuration Structure

```json
{
  "environment": {
    "type": "sumo_simulation",
    "host": "127.0.0.1",
    "port": 51001,
    "sumo_details": {
      "sumo_binary": "sumo-gui",
      "config_path": "scenarios/demo/sumo/config.sumocfg"
    }
  },
  "logic_modules": [
    {
      "type": "priority_pass",
      "host": "127.0.0.1",
      "port": 51002,
      "scenario_path": "scenarios/demo/sumo"
    }
  ],
  "orchestrator": {
    "host": "127.0.0.1",
    "port": 51000
  },
  "recorder": {
    "host": "127.0.0.1",
    "port": 51003,
    "logs_dir": "logs/demo_priority_pass"
  }
}
```

## Key Fields

### `environment`

| Field | Description |
|---|---|
| `type` | Environment type — currently `"sumo_simulation"` |
| `host` / `port` | TCP address the Environment listens on |
| `sumo_details.sumo_binary` | SUMO binary name or path (`sumo-gui` or `sumo`) |
| `sumo_details.config_path` | Path to the `.sumocfg` SUMO configuration file |

### `logic_modules`

An ordered array of logic module definitions. All modules run each step; their command outputs are merged by the Orchestrator. Set to `[]` for **baseline mode**: the Orchestrator sends an empty `apply_and_advance` each step so SUMO's built-in signal plans run unmodified. Omit the `logic_module` port from `communication.ports` when the array is empty.

| Field | Description |
|---|---|
| `type` | Module type: `"controller_fixed_cycle"`, `"controller_max_pressure"`, or `"controller_priority_pass"` |
| `host` / `port` | TCP address the module listens on (injected by Orchestrator; not set in config directly) |

### `orchestrator`

| Field | Description |
|---|---|
| `host` / `port` | TCP address the Orchestrator listens on (default `127.0.0.1:51000`) |

### `recorder`

| Field | Description |
|---|---|
| `host` / `port` | TCP address the Recorder listens on (default `127.0.0.1:51003`) |
| `logs_dir` | Directory for output log files |

## Adding a New Logic Module

1. Create `src/controller_<name>.py` implementing the FSM lifecycle and the `traffic_state` / `logic_command` message contract.
2. Register the new type in the Orchestrator's `_LOGIC_MODULE_TYPES` dict.
3. Add a configuration file in `configurations/` following the naming convention.
4. Add the new module to `logic_modules` in the configuration JSON.

## Scenario Files

Scenario-specific SUMO files live in `scenarios/{scenario_name}/sumo/`:

| File | Description |
|---|---|
| `config.sumocfg` | SUMO configuration (references network and demand files) |
| `network.net.xml` | Road network topology |
| `demand.xml` | Vehicle route definitions |
| `phase_inc_lanes.json` | Per-phase incoming lanes mapping |
| `route_*.json` | Route metadata (distances, durations) |
