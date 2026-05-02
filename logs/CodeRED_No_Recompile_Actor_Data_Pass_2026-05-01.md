# CodeRED No-Recompile Actor Data Pass

Date: 2026-05-01
Branch: `codered-build-assistant-pass1`

## Goal

Make actor spawn data editable without recompiling the ScriptHookRDR AI Menu.

This pass adds a Python actor enum tool and replaces the default roster/map with a small verified seed so the first runtime install starts from resolved values instead of unresolved research labels.

## Added

```text
tools/codered_actor_enum_tool.py
```

The tool can:

- seed a minimal known-good `data/codered/actor_enum_map.csv`
- rebuild the full enum map from a local `Enums.h`
- validate `data/codered/npc_roster.txt` against the enum map
- write `logs/CodeRED_Actor_Enum_Validation_Report.json`
- export `data/codered/npc_roster_safe_verified.txt`

## Updated

```text
data/codered/actor_enum_map.csv
data/codered/npc_roster.txt
```

The default map now includes the known corrected Army Easy01 value plus the main rideable/vehicle candidates:

```text
ACTOR_CAUCASIAN_ARMY_Easy01 = 369 / 0x00000171
ACTOR_RIDEABLE_ANIMAL_Horse01 = 976 / 0x000003D8
ACTOR_RIDEABLE_ANIMAL_MEX_Mule01 = 1000 / 0x000003E8
ACTOR_RIDEABLE_ANIMAL_Buffalo = 1004 / 0x000003EC
ACTOR_VEHICLE_Stagecoach = 1177 / 0x00000499
ACTOR_VEHICLE_Cart01 = 1183 / 0x0000049F
ACTOR_VEHICLE_Canoe01 = 1189 / 0x000004A5
ACTOR_VEHICLE_Raft01 = 1192 / 0x000004A8
ACTOR_VEHICLE_Truck01 = 1193 / 0x000004A9
ACTOR_VEHICLE_Car01 = 1194 / 0x000004AA
ACTOR_VEHICLE_Wagon02 = 1199 / 0x000004AF
ACTOR_VEHICLE_Coach01 = 1202 / 0x000004B2
```

## Usage

Seed known-good data:

```bat
py -3 tools\codered_actor_enum_tool.py seed --safe-roster --replace
```

Validate roster/map:

```bat
py -3 tools\codered_actor_enum_tool.py validate
```

Generate a safe resolved roster:

```bat
py -3 tools\codered_actor_enum_tool.py safe-roster --replace
```

Rebuild full map from local `Enums.h` after the user adds it locally:

```bat
py -3 tools\codered_actor_enum_tool.py rebuild --enums-h "D:\Path\To\Enums.h" --replace
```

## Safety note

The repo does not need to commit `Enums.h`. The tool is designed to consume the user's local `Enums.h` path and write the CSV the ASI menu already reads.

## Next runtime improvement

The next C++ compile pass should make the menu write `scratch/codered_actor_resolution.json` before native spawn. That would prove what label resolved to which enum value before the game receives it.
