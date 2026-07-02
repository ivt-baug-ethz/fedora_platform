# Configuration

All runtime settings are loaded from a JSON configuration file. The naming convention is `{scenario}_sumo_{logic_module}_config.json` (or `{scenario}_sumo_baseline_config.json` for runs without a controller).

## Configuration Files

| File | Scenario | Logic module |
|---|---|---|
| `demo_sumo_baseline_config.json` | Demo | None (SUMO default signal plans) |
| `demo_sumo_fixed_cycle_config.json` | Demo | Configurable Fixed-Cycle |
| `demo_sumo_max_pressure_config.json` | Demo | Max-Pressure |
| `demo_sumo_priority_pass_config.json` | Demo | Urban Priority Pass |
| `demo_sumo_priority_pass_full_state_config.json` | Demo | Urban Priority Pass — all state fields logged |
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
      "binary_headless": "sumo",
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
    "log_type": "txt",
    "topics": [],
    "vehicle_log_enabled": true,
    "state_polling": {
      "interval_steps": 1,
      "environment_state": {
        "step": true,
        "time": true,
        "vehicle_ids": true,
        "vehicle_lanes": true,
        "vehicle_lane_positions": true,
        "vehicle_upp": true,
        "pending_commands": true,
        "vehicle_speeds": false,
        "vehicle_waiting_times": false
      },
      "logic_module_state": {
        "step": true,
        "controller_type": true,
        "light_states": true,
        "bids": true,
        "bids_queue": true,
        "bids_upp": true,
        "bids_blended": true,
        "phase_switched": true,
        "tau": true
      }
    }
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
| `settings.binary` | SUMO binary for interactive runs (`sumo-gui`); used when `--headless` is not passed |
| `settings.binary_headless` | SUMO binary for headless runs (`sumo`); selected by passing `--headless` to `run.py` |
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

Controls what the Recorder writes and whether per-step component state is captured.

| Field | Default | Description |
|---|---|---|
| `logs_dir` | *(required)* | Directory for output log files |
| `log_type` | `"txt"` | Recorder backend; currently only `"txt"` is supported |
| `topics` | `[]` | Allowlist of message topics to record. An empty list logs **all** topics. Non-empty lists act as a filter (e.g. `["traffic_state", "logic_command"]`). |
| `vehicle_log_enabled` | `true` | Write per-vehicle arrival/departure events to `vehicle_log.jsonl`. Set to `false` to skip the vehicle log (note: disabling it also disables the post-run `Evaluator`). |

#### Disabling the recorder

Remove the `"recorder"` port from `communication.ports` (and omit the `recorder` section, or set its `logs_dir` to a placeholder) to skip recorder startup entirely. The Orchestrator will not instantiate a Recorder and no log files will be created. This is the lowest-overhead option for runs where logging is not needed.

#### State polling (`state_polling`)

The Orchestrator can query the internal state of each component after every step and forward the responses to the communication log. Polling is **automatically enabled** for a component when at least one of its state attributes is set to `true`; no separate `enabled` flag is needed. If all attributes are `false`, no polling occurs and no extra overhead is introduced.

| Field | Default | Description |
|---|---|---|
| `interval_steps` | `1` | Poll every N steps. `1` captures state every step; `10` captures every 10th step. |
| `environment_state` | — | Dict of boolean flags for environment state fields (see below). |
| `logic_module_state` | — | Dict of boolean flags for logic module state fields (see below). |

**`environment_state` fields:**

| Key | Description |
|---|---|
| `step` | Current simulation step counter |
| `time` | Simulation time in seconds |
| `vehicle_ids` | Set of active vehicle IDs |
| `vehicle_lanes` | Per-vehicle current lane ID |
| `vehicle_lane_positions` | Per-vehicle position along the current lane |
| `vehicle_upp` | Per-vehicle UPP token value |
| `pending_commands` | Command queue awaiting application |
| `vehicle_speeds` | Per-vehicle speed (TraCI call; minor overhead) |
| `vehicle_waiting_times` | Per-vehicle accumulated waiting time (TraCI call; minor overhead) |

The first seven fields are maintained in memory during the simulation loop at zero additional cost. `vehicle_speeds` and `vehicle_waiting_times` require a TraCI API call per vehicle per polled step; keep them `false` in production runs where they are not needed.

**`logic_module_state` fields:**

| Key | Applicable to |
|---|---|
| `step` | All controllers |
| `controller_type` | All controllers |
| `light_states` | All controllers |
| `bids` | Max-Pressure |
| `bids_queue` | Priority Pass |
| `bids_upp` | Priority Pass |
| `bids_blended` | Priority Pass |
| `phase_switched` | Max-Pressure, Priority Pass |
| `tau` | Priority Pass |

Fields not applicable to the active controller type are silently ignored (a `UserWarning` is emitted at startup to flag the mismatch, but the run continues normally).

#### Full-state example

`demo_sumo_priority_pass_full_state_config.json` sets every field to `true` with `interval_steps: 1`. Run it with:

```bash
python run.py configurations/demo_sumo_priority_pass_full_state_config.json
```

Use it to verify that state polling works end-to-end or to capture a complete diagnostic trace. For regular benchmarking runs, leave the TraCI fields and bid fields at `false` to avoid the overhead.

### `evaluation`

Controls whether post-run standard metrics are computed and which ones are enabled.

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | Run evaluation after the environment run completes. The `--skip-evaluation` CLI flag overrides this to `false`. |
| `metrics` | array of strings | `[]` | Metric allowlist. An empty list enables **all** standard metrics. |

**Valid metric names:** `travel_time`, `travel_time_variance`, `vht`, `vkt`, `flow`, `speed`,
`density`.

**Example — enable all metrics (default):**

```json
"evaluation": {
  "enabled": true,
  "metrics": []
}
```

**Example — enable only travel time and flow:**

```json
"evaluation": {
  "enabled": true,
  "metrics": ["travel_time", "flow"]
}
```

**Example — disable evaluation entirely:**

```json
"evaluation": {
  "enabled": false,
  "metrics": []
}
```

!!! note
    `vkt` and `space_mean_speed` require `route_distance_m` in vehicle departure events, and
    `density` requires `total_lane_length_m` in the `run_meta` log header. Both fields are
    written automatically by the bundled SUMO environment; any other environment implementation
    must populate the same fields to support these metrics. Metrics that cannot be computed due
    to missing data emit `null` in `evaluation_stats.json` rather than failing.

See the [Evaluation](evaluation.md) page for a complete description of all metrics and output
files.

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
