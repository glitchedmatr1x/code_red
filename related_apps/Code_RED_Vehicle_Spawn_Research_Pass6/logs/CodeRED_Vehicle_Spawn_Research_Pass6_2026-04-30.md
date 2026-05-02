# Code RED — Vehicle Spawn Research / Trainer-Style Runtime Path Pass 6

Date: 2026-04-30

## Why this pass happened

The copied Blackwater RPF experiment that nudged `i_gen_wagonBroken02x` crashed in-game. That means the WSI placement lane is not safe enough for wagon/cart physics records, even when the change is tiny.

The earlier Blackwater test that removed the broken car still matters: WSI can affect/remove static world props. But the crash strongly suggests wagon/car spawn work should move away from physics placement mutation and toward runtime spawn/gringo/script behavior.

## What this pass adds

```text
tools/codered_vehicle_spawn_research.py
```

This tool is read-only. It scans RPF/resource bytes for runtime vehicle-spawn clues and creates tables for:

```text
vehicle_spawn_strings.csv
vehicle_tokens.csv
candidate_wsc_scripts.csv
gringo_vehicle_callsite_candidates.csv
gringo_wgd_vehicle_keyword_hits.csv
vehicle_spawn_research_master.json
trainer_spawn_research_summary.md
```

## Inputs used in this pass

```text
gringores.rpf
content.rpf
tune_d11generic.rpf
previous gringo WGD component export from commongringos.wgd / blackwater.wgd
```

## Strongest results

The cleanest results still come from the decoded WGD component export:

```text
content\scripting\gringo\CommonScripts\Vehicle_Generator
content\scripting\gringo\CommonScripts\car_gringo
content\scripting\gringo\CommonScripts\PlayerCar
content\scripting\gringo\CommonScripts\CarCrank_gringo
content\scripting\gringo\GringoBrains\GringoBrainScripts\Gen_Vehicle_Brain
content\scripting\gringo\CommonScripts\GatlingAttachGringo
content\scripting\gringo\CommonScripts\TurretAttachMover
content\scripting\gringo\CommonScripts\TrainGringo
content\scripting\gringo\CommonScripts\trainCar_gringo
```

Useful tune/content string labels found:

```text
AE_Companion_FBI
AE_Caucasian_Male_SteamEngineDriver01
Coach_Passenger
CRM_ROB_COACH
CRM_ROB_TRAIN
Drive_Stagecoach
Enter_Minecart
horse_matchspeed_train
horse_matchspeed_wagon
out_warn_vehicle
PASS_COACH_CurrentDest / Exit / Faster / Slower / SkipToDest
passenger0 / passenger1 / passenger2 / passenger3
Steal_Wagon
taxi_coach_help
trainmarshal_help
tutorial_law_posse_spawn
mp_gy_safe_spawned
mp_gy_weapon_spawned
```

## Interpretation

Do not keep testing cars by moving wagon/carter records. Wagons are unstable and probably depend on matching WSI/WBD/WVD/physics/nav state.

Best route now:

```text
1. Use WSI only for clearing/removing static blocker props.
2. Use gringo/WSC/native-style runtime research for actual spawned vehicles.
3. Compare trainer spawn names against VEHICLE_* and gringo `PlayerCar` / `Vehicle_Generator` paths.
4. Search FBI/coach/train WSC resources next because they are the most likely to contain real vehicle setup patterns.
```

## Next pass recommendation

Pass 7 should be:

```text
Vehicle Runtime Callsite Resolver
```

Tasks:

```text
1. Extract and decode candidate WSC/RSC resources around FBI, coach, train, wagon, and Vehicle_Generator leads.
2. Build a string-neighborhood table around PlayerCar, Vehicle_Generator, passenger0-3, Coach_Passenger, Drive_Stagecoach, and Steal_Wagon.
3. Add a trainer-name comparison input so a known trainer spawn label can be checked against game tokens.
4. Keep all outputs read-only until an actual runtime trigger path is proven.
```
