# Code RED AI Menu Car Spawn Readiness — 2026-05-04

## Command

```powershell
py -3 tools\codered_ai_menu_car_spawn_doctor.py
Get-Content logs\ai_menu_car_spawn_doctor.md -TotalCount 180
```

## Result

```text
likely_ready: True
```

## Verdict from local doctor

```text
AI menu source found: related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp
AI menu source has the core native bridge and spawn action machinery
actor enum map contains a Car01/vehicle entry
roster contains a vehicle/car entry
action menu contains spawn_selected_npc_request
LIKELY READY for a direct AI-menu car spawn test if the menu build/install itself loads in-game
```

## Required source bridge tokens present

```text
CR_NATIVE_CREATE_ACTOR_IN_LAYOUT: True
CR_NATIVE_GET_PLAYER_ACTOR: True
CR_NATIVE_GET_POSITION: True
CR_NATIVE_START_VEHICLE: True
CR_NATIVE_GET_VEHICLE: True
CREATE_ACTOR_IN_LAYOUT: True
START_VEHICLE: True
GET_VEHICLE: True
```

## Car enum evidence

```text
data/codered/actor_enum_map.csv
ACTOR_VEHICLE_Car01,1194,vehicle,CodeRED seed sanity map,ACTOR_VEHICLE_CAR01|actor_vehicle_car01|VEHICLE_Car01|VEHICLE_CAR01|vehicle_car01|AE_VEHICLE_Car01|AE_VEHICLE_CAR01|ae_vehicle_car01,canonical=ACTOR_VEHICLE_Car01; hex=0x000004AA; seed_only=true
```

## Roster evidence

```text
data/codered/npc_roster.txt
ACTOR_VEHICLE_Car01
ACTOR_VEHICLE_Truck01
ACTOR_VEHICLE_Stagecoach
ACTOR_VEHICLE_Cart01
ACTOR_VEHICLE_Wagon02
ACTOR_VEHICLE_Coach01
ACTOR_VEHICLE_Canoe01
ACTOR_VEHICLE_Raft01
```

## Action evidence

```text
data/codered/ai_behavior_actions.csv
spawn_selected_npc_request,Spawn Selected NPC,spawn,1,Uses npc_roster label resolved through actor_enum_map.csv and CREATE_ACTOR_IN_LAYOUT
```

## Interpretation

The AI menu is not wired to load `camp_car_probe` artifacts, but it likely does not need to be for the first car test. The menu can likely spawn `ACTOR_VEHICLE_Car01` directly through its existing spawn-selected path if the `.asi` build/install loads in-game.

## Next test

1. Build/install the ScriptHookRDR AI Menu `.asi` if not already installed.
2. Ensure `data/codered/actor_enum_map.csv`, `data/codered/npc_roster.txt`, and `data/codered/ai_behavior_actions.csv` are beside the installed menu path/game root as expected by the menu config.
3. In-game, open the Code RED AI menu.
4. Select `ACTOR_VEHICLE_Car01` from the roster.
5. Run `Spawn Selected NPC`.
6. If it spawns but does not drive, use the separate camp-car script lane for enter/tune controls.
