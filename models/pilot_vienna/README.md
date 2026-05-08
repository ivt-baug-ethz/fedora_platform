# Pilot 1 - Vienna Model Assets

The Vienna pilot folder contains model assets for the current Priority
Pass/SUMO prototype. Runtime Python code lives in `src/fedora_platform/`.

```text
pilot_vienna/
  sumo/
    Configuration.sumocfg
    Network.net.xml
    Demand.xml
    Phase_BidderLanes.json
    Phase_ExitLanes.json
    Route_*.json
```

`src/fedora_platform/priority_pass.py` resolves this folder by default through
`PriorityPassConfig.model_root`.
