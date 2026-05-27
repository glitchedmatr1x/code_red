# HANDOFF — Code RED AI Menu Spawn Crash Fix — 2026-05-04

## Crash result

The direct vehicle-first menu crashed when spawning through the raw ASI/native path.

The risky entries were:

```text
ACTOR_VEHICLE_Car01
ACTOR_VEHICLE_Truck01
```

These should not be exposed through the default `spawn_selected_npc_request` path until the vehicle is created through a safer WGD/gringo/vehicle-generator or dedicated initialized vehicle lane.

## Fix committed

Updated default repo roster:

```text
data/codered/npc_roster.txt
```

New default order:

```text
ACTOR_RIDEABLE_ANIMAL_Horse01
ACTOR_RIDEABLE_ANIMAL_MEX_Mule01
ACTOR_RIDEABLE_ANIMAL_Buffalo
ACTOR_VEHICLE_Stagecoach
ACTOR_VEHICLE_Wagon02
ACTOR_VEHICLE_Coach01
ACTOR_VEHICLE_Cart01
```

Updated installer:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/install_vehicle_first_menu_data_windows.ps1
```

It now installs a spawn-safe roster and marks `Car01` / `Truck01` as blocked raw-spawn entries in the generated actor enum map.

## Commits

```text
4b245de2213267f400a7f9dd5d3f724da3097ff9
bb686654df78c4b218befdd7bf0051dbc28699c4
```

## User command after pulling

Run from repo root:

```powershell
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_vehicle_first_menu_data_windows.ps1 -GameRoot "D:\Games\Red Dead Redemption"
```

Expected in-game footer:

```text
Roster 1-7 / 7
```

Expected first item:

```text
ACTOR_RIDEABLE_ANIMAL_Horse01
```

Do not use a menu state that still shows `/ 11` or `/ 413` for this crash fix pass.

## Next safe test order

1. Horse
2. Mule
3. Buffalo
4. Stagecoach
5. Wagon02
6. Coach01
7. Cart01

## If wagons still crash

Then the problem is not only Car01/Truck01. The ASI spawn path or `CREATE_ACTOR_IN_LAYOUT` argument packing needs to be guarded before any vehicle actor is spawned.

## Correct next car lane

Do not re-add `Car01` or `Truck01` to `npc_roster.txt`.

Build the next car pass as one of these:

```text
1. WSI/WGD gringo correlator vehicle host
2. Vehicle_Generator / car_gringo test
3. Dedicated ASI action that creates vehicle, validates handle, calls GET_VEHICLE/START_VEHICLE, and only then enables enter/control behavior
```

The raw spawn menu is for safe actor/wagon probes only.
