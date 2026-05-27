# HANDOFF — Code RED AI Menu Car Spawn Lane — 2026-05-04

## Current status

The Code RED ScriptHookRDR AI Menu now loads in-game. The screenshot proof showed the overlay active with:

```text
CODERED AI MENU
Spawn Selected Vehicle / Actor
Roster 1-9 / 413
```

This means the ASI/menu is loading, but the game folder was still using the old giant roster data. The action label was updated, but `npc_roster.txt` was not yet force-replaced in the installed game folder.

## Important conclusion

The remaining blocker is not SC-CL compile and not ASI loading. It is installed menu data:

```text
Old roster loaded: 413 entries
Wanted roster: vehicle-first safe list, 11 entries
First wanted entry: ACTOR_VEHICLE_Car01
```

## Latest fix added

Added force installer:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/install_vehicle_first_menu_data_windows.ps1
```

Commit:

```text
293590c26f71e8ed192fa1bf9d5a273f0452a847
```

What it does:

```text
- Backs up existing game-root data/codered files
- Writes a short vehicle-first npc_roster.txt
- Writes a safer ai_behavior_actions.csv
- Writes a small actor_enum_map.csv with vehicle/rideable entries
- Rewrites CodeRED_AI_Menu.ini to point at data/codered
- Does not modify RPF archives
```

## Run this next

From repo root after pulling:

```powershell
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_vehicle_first_menu_data_windows.ps1 -GameRoot "D:\Games\Red Dead Redemption"
```

Then relaunch the game.

## Expected in-game verification

Open Code RED AI Menu.

Expected footer should change from:

```text
Roster 1-9 / 413
```

to something like:

```text
Roster 1-9 / 11
```

Expected first roster item:

```text
ACTOR_VEHICLE_Car01
```

Then run:

```text
Spawn Selected Vehicle / Actor
```

## AI Menu build status

Build succeeded with `user32.lib` linked:

```text
related_apps\Code_RED_ScriptHookRDR_AI_Menu\build\CodeRED_AI_Menu.asi
Length: 379904
SHA1: A68CCB9F518BF85B70A52D41C2A6B6CE58FAE484
```

Build helper:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/build_ai_menu_asi_windows.ps1
```

Install helper:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/install_ai_menu_asi_windows.ps1
```

## Car spawn readiness doctor result

Local doctor showed:

```text
likely_ready: True
AI menu source found: related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp
AI menu source has the core native bridge and spawn action machinery
actor enum map contains a Car01/vehicle entry
roster contains a vehicle/car entry
action menu contains spawn_selected_npc_request
```

This means the AI Menu does not need to load `camp_car_probe` artifacts for the first car test. It should be able to spawn `ACTOR_VEHICLE_Car01` directly from its existing native bridge if the installed data is correct.

## Camp-car SC-CL artifact lane status

The separate SC-CL camp-car artifacts are also built and staged:

```text
camp_car_probe.xsc  length=1158  sha1=C8DC6821D04A76302C123814A8DCBD507DD6200E
camp_car_probe.sco  length=1075  sha1=0351E47E3B0F5C6BA7C8D75A6C8FDA92A78D8C8B
camp_car_probe.wsc  length=1158  sha1=2729784CA37478DD22E0CFE8BD52B11793A36E14
```

Staged kit:

```text
script_compiling\sccl\output\playtest_kits\camp_car_artifacts_20260504_192307.zip
ZIP SHA1: 7B182C7A2044F12549E80AC1171F2CBC6CD52DD2
```

Use this lane later if direct ASI menu spawn works but car control/enter/tune needs a separate script.

## Known issue to avoid

Do not use the giant 413-entry roster for now. It contains unsafe NPC entries and has caused crashes. The current test should only use the vehicle-first roster until specific actor entries are verified.

## Next best pass after the vehicle-first install test

If `ACTOR_VEHICLE_Car01` spawns but cannot be driven:

```text
Add a dedicated AI Menu action:
Spawn Car + Start Vehicle + Put Player In Vehicle
```

Potential names:

```text
spawn_vehicle_car01_request
enter_spawned_vehicle_request
start_spawned_vehicle_request
```

If no car spawns after the vehicle-first roster is active:

```text
Check CodeRED_AI_Menu.log
Check whether CREATE_ACTOR_IN_LAYOUT returned an invalid actor
Check whether actor enum 1194 / 0x000004AA is accepted in the current game state/location
```

## Boundary

This handoff only documents current state and next commands. It does not modify RPF archives.
