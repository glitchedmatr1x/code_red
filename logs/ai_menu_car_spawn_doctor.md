# Code RED AI Menu Car Spawn Doctor

Root: `D:\Games\Red Dead Redemption\Code_RED`

Boundary: read-only local scan. No files modified.

## Verdict

- AI menu source found: related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp
- AI menu source has the core native bridge and spawn action machinery
- actor enum map contains a Car01/vehicle entry
- roster contains a vehicle/car entry
- action menu contains spawn_selected_npc_request
- LIKELY READY for a direct AI-menu car spawn test if the menu build/install itself loads in-game

## Source token status

- `CR_NATIVE_CREATE_ACTOR_IN_LAYOUT`: `True`
- `CR_NATIVE_GET_PLAYER_ACTOR`: `True`
- `CR_NATIVE_GET_POSITION`: `True`
- `CR_NATIVE_START_VEHICLE`: `True`
- `CR_NATIVE_GET_VEHICLE`: `True`
- `CREATE_ACTOR_IN_LAYOUT`: `True`
- `START_VEHICLE`: `True`
- `GET_VEHICLE`: `True`

## Actor enum maps

### `data/codered/actor_enum_map.csv` exists=`True` has_car01=`True`
- `ACTOR_VEHICLE_Car01,1194,vehicle,CodeRED seed sanity map,ACTOR_VEHICLE_CAR01|actor_vehicle_car01|VEHICLE_Car01|VEHICLE_CAR01|vehicle_car01|AE_VEHICLE_Car01|AE_VEHICLE_CAR01|ae_vehicle_car01,canonical=ACTOR_VEHICLE_Car01; hex=0x000004AA; seed_only=true`
### `related_apps/CodeRED_Script_Workshop/workspace/edit/data/codered/actor_enum_map.csv` exists=`True` has_car01=`True`
- `ACTOR_VEHICLE_Car01,1194,vehicle,CodeRED seed sanity map,ACTOR_VEHICLE_CAR01|actor_vehicle_car01|VEHICLE_Car01|VEHICLE_CAR01|vehicle_car01|AE_VEHICLE_Car01|AE_VEHICLE_CAR01|ae_vehicle_car01,canonical=ACTOR_VEHICLE_Car01; hex=0x000004AA; seed_only=true`

## Rosters

### `data/codered/npc_roster.txt` exists=`True` has_vehicle_entry=`True`
- `ACTOR_VEHICLE_Car01`
- `ACTOR_VEHICLE_Truck01`
- `ACTOR_VEHICLE_Stagecoach`
- `ACTOR_VEHICLE_Cart01`
- `ACTOR_VEHICLE_Wagon02`
- `ACTOR_VEHICLE_Coach01`
- `ACTOR_VEHICLE_Canoe01`
- `ACTOR_VEHICLE_Raft01`
### `related_apps/CodeRED_Script_Workshop/workspace/edit/data/codered/npc_roster.txt` exists=`True` has_vehicle_entry=`True`
- `ACTOR_VEHICLE_Car01`
- `ACTOR_VEHICLE_Truck01`
- `ACTOR_VEHICLE_Stagecoach`
- `ACTOR_VEHICLE_Cart01`
- `ACTOR_VEHICLE_Wagon02`
- `ACTOR_VEHICLE_Coach01`
- `ACTOR_VEHICLE_Canoe01`
- `ACTOR_VEHICLE_Raft01`

## Actions

### `data/codered/ai_behavior_actions.csv` exists=`True` has_spawn_action=`True` has_vehicle_action=`False`
- `spawn_selected_npc_request,Spawn Selected NPC,spawn,1,Uses npc_roster label resolved through actor_enum_map.csv and CREATE_ACTOR_IN_LAYOUT`
- `regroup_near_player_request,Regroup Near Player,behavior,1,Sends spawned actors near player`
- `status_request,Status,debug,1,Reports native bridge, enum, tracked actors, and optional world scan support`
### `related_apps/CodeRED_Script_Workshop/workspace/edit/data/codered/ai_behavior_actions.csv` exists=`True` has_spawn_action=`True` has_vehicle_action=`False`
- `spawn_selected_npc_request,Spawn Selected NPC,spawn,1,Uses npc_roster label resolved through actor_enum_map.csv and CREATE_ACTOR_IN_LAYOUT`
- `regroup_near_player_request,Regroup Near Player,behavior,1,Sends spawned actors near player`
- `status_request,Status,debug,1,Reports native bridge, enum, tracked actors, and optional world scan support`