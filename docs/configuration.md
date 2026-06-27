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
  "scenario": "demo",
  "scenario_path": "scenarios/demo/sumo",
  "communication": {
    "host": "127.0.0.1",
    "ports": {
      "orchestrator": 51000,
      "environment": 51001,
      "recorder": 51003,
      "logic_module": 51002
    },
    "socket_timeout": 2.0
  },
  "setup": {
    "startup_pause_seconds": 0.2,
    "random_seed": 42,
    "traffic_lights": ["J25", "J26"],
    "controller_response_timeout_seconds": 0.05,
    "measurements": {
      "sumo": {
        "lane_measurements": {
          "pressure_lanes": "phase_inc_lanes.json"
        },
        "measurement_details": {
          "sensor_distance": 100.0
        },
        "road_measurements": {},
        "sensor_measurements": {},
        "vehicle_measurements": {}
      }
    }
  },
  "environment": {
    "type": "sumo",
    "settings": {
      "binary": "sumo-gui",
      "config_file": "config.sumocfg",
      "label": "demo_priority_pass"
    },
    "demand": {
      "traci_spawning_active": true,
      "route_probabilities_file": "route_probabilities.json",
      "flow_per_entrance_per_hour": 50.0,
      "spawn_horizon": 30000,
      "max_steps": 5000,
      "step_delay_seconds": 0.0
    }
  },
  "recorder": {
    "logs_dir": "logs/demo_priority_pass",
    "log_type": "txt"
  },
  "logic_modules": [
    {
      "type": "controller_priority_pass",
      "priority_pass": {
        "transition_duration": 3,
        "bidding_strategy": "phase_queue_length",
        "auction_winner": "highest_bid",
        "min_green_duration": 3,
        "max_green_duration": 60,
        "auction_suspend_duration": 4,
        "trade_off": 0.6
      }
    }
  ]
}
```

## Key Fields

### `communication`

| Field | Description |
|---|---|
| `host` | Host used for all local TCP components |
| `ports.orchestrator` | TCP port for the Orchestrator |
| `ports.environment` | TCP port for the Environment |
| `ports.recorder` | TCP port for the Recorder |
| `ports.logic_module` | TCP port for the first logic module |

### `setup`

| Field | Description |
|---|---|
| `random_seed` | Shared deterministic seed injected into the environment and logic modules |
| `traffic_lights` | SUMO traffic-light IDs controlled or observed in the scenario |
| `controller_response_timeout_seconds` | Environment wait time for logic-module responses before advancing |
| `measurements.sumo.lane_measurements.pressure_lanes` | Phase-to-lane mapping file, resolved relative to `scenario_path` |

### `environment`

| Field | Description |
|---|---|
| `type` | Environment type, currently `"sumo"` |
| `settings.binary` | SUMO binary name or path (`sumo-gui` or `sumo`) |
| `settings.config_file` | SUMO `.sumocfg` file, resolved relative to `scenario_path` |
| `settings.label` | TraCI connection label |
| `demand.*` | TraCI spawning and demand parameters |

### `logic_modules`

An ordered array of logic module definitions. All modules run each step; their command outputs are merged by the Orchestrator. Set to `[]` for **baseline mode**: the Orchestrator sends an empty `apply_and_advance` each step so SUMO's built-in signal plans run unmodified. Omit the `logic_module` port from `communication.ports` when the array is empty.

| Field | Description |
|---|---|
| `type` | Module type: `"controller_fixed_cycle"`, `"controller_max_pressure"`, or `"controller_priority_pass"` |
| `host` / `port` | TCP address the module listens on; injected by Orchestrator, not set directly in config |

For Priority Pass experiments, keep the auction timing fields aligned with the matching Max-Pressure config (`transition_duration`, `min_green_duration`, `max_green_duration`, and `auction_suspend_duration`). With `trade_off = 0.0`, Priority Pass should then match Max-Pressure exactly for the same SUMO random seed; larger values isolate the effect of UPP bid prioritisation.

### `recorder`

| Field | Description |
|---|---|
| `logs_dir` | Directory for output log files |
| `log_type` | Recorder backend type; currently `"txt"` |

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
