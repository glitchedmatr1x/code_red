# Pass 13 — Big World Simulation Notes

Pass 13 is the repo-friendly source pass for the Code RED Faction War resource mod.

The working direction is to keep the mod **resource-only**:

- no SC-CL requirement
- no menu requirement
- no EXE/DLL loader requirement
- no plugin runtime dependency
- patched RPFs remain generated test artifacts, not core source files

## What already works well enough to build on

Previous passes showed that content/tune resource edits can noticeably affect the world. The strongest reliable lanes are:

- `content/ambient/placementglobals.xml` for event pressure and road/trail/wilderness placement
- `content/ambient/factionrelations.xml` for hostility and ally/friendly behavior
- `content/ai/*.tr` for behavior routing and combat/follow/help hooks
- `tune/level/territory/level.pop` for population pools and regional pressure
- `tune/settings/default.traffic` for road/route pressure metadata
- `tune/settings/ambientmgrtuning.xml` for actor headroom and persistence
- `tune/refgroups/**/*.refgroup` for camp, battle, cover, and prop set enrichment
- `navres/territory/props.xml` and `navres/battlesets.txt` as safety filters for props/vehicles/battle sets

## Pass 13 goals

1. Make wilderness less empty.
2. Make camps, broken wagons, rebel camps, and battle debris more frequent and more persistent.
3. Create stronger daily rival gang showdowns using time-windowed regional pools.
4. Keep Thieves Landing law-free internally, but allow law to ride in from outside if a major fight spills out.
5. Add a US Army bodyguard-posse lane as a best-effort resource approximation.
6. Add a law capture-posse lane so some deputies/marshals prefer lasso/hogtie/prison-wagon support instead of only shooting.
7. Use navres-confirmed props/vehicles where possible.
8. Keep generated RPFs outside GitHub and recreate them from recipes/build scripts.

## Important limitation

Resource-only edits can strongly encourage behavior, but they do not guarantee true scripted ownership:

- guaranteed vehicle drivers
- guaranteed train boarding
- exact once-per-day random scheduling
- exact Dutch/Javier/Bill/US Army named companion actors
- guaranteed lasso inventory on specific lawmen

Those need deeper WSC/WAT/template decoding later.

## Best next technical targets

- `companion_brain.wsc`
- `event_law_repsonse_posse.wsc`
- `vehicle_generator.wsc`
- `car_gringo.wsc`
- `playercar.wsc`
- `traincar_gringo.wsc`
- `trainsitgringo.wsc`
- `train_brain.wsc`
- `lassogringo.wsc`
- `pickuphogtiedgringo.wsc`
- `gringo_actorhasweapon.wsc`
- `gringores/*.wgd` town files, especially `thieveslanding.wgd`

## Packaging rule

GitHub stores recipes/scripts/fragments/reports. Testable RPFs are generated as artifacts:

```text
DROP_IN_PASS13_BIG_WORLD_SIMULATION/
  content.rpf
  tune_d11generic.rpf
  reports/
  README_INSTALL_AND_TEST_PASS13.txt
```
