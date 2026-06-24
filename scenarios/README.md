# FEDORA Models

This folder contains model and pilot-specific assets that are part of the main
repository. Runtime code should resolve pilot assets from here, not from external
example folders.

Runtime Python code belongs in `src/fedora_platform/`. Model folders should
contain network files, demand files, configuration, calibration data, and other
pilot assets.

```text
models/
  demo/                  Example model for demonstration and testing
  pilot_vienna/
    sumo/                SUMO network, demand, route and phase files
  pilot_basque_country/  Reserved for freight logistics hub integration models
  pilot_nicosia/         Reserved for aerial and road traffic integration models
  pilot_copenhagen/      Reserved for foresight simulation models
  pilot_reggio_emilia/   Reserved for demand management strategy models
  pilot_budapest/        Reserved for road and inland waterway models
```
