# CodeRED AI Menu Behavior/Faction Pass

Date: 2026-05-02

## Scope

This pass keeps the current ScriptHookRDR native bridge and the existing
`CREATE_ACTOR_IN_LAYOUT` spawn path. It does not replace the working spawn
implementation.

## Changes

- Added editable menu actions at `data/codered/ai_behavior_actions.csv`.
- Updated `CodeRED_AI_Menu.ini` so the runtime loads the action table through
  `behavior_actions=data/codered/ai_behavior_actions.csv`.
- Kept `data/codered/npc_roster.txt` as the human-readable label list.
- Kept `data/codered/actor_enum_map.csv` as the local enum resolver source.
- F5 now reloads roster, actor enum map, and behavior actions.
- Added native actions for:
  - spawn selected NPC
  - follow player
  - stand guard / idle
  - wander
  - regroup near player
  - make spawned actors US lawmen
  - join lawman side
  - join gang side
  - restore player faction
  - dismiss spawned actors
  - status
- Added optional `worldGetAllActors` export lookup for hostile scans.
- Added nearest-hostile attack dispatch using `AI_IS_HOSTILE_OR_ENEMY` and
  `TASK_KILL_CHAR` for CodeRED-spawned actors only.

## Faction Notes

Local enum research from `Enums.h` showed these useful factions:

- `FACTION_Player = 2`
- `FACTION_USLawEnforcement = 8`
- `FACTION_GenericCriminal = 13`

The menu uses US law faction for lawman immunity and generic criminal for gang
side testing. The restore action returns the player to the original saved
faction when available, otherwise the player faction.

## Validation

- `python tools\codered_actor_enum_tool.py validate --replace`
  - roster entries: 13
  - resolved: 13
  - unresolved: 0
  - sanity errors: 0
- `related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_bridge.bat`
  completed from a Visual Studio 2022 x64 developer environment.

## Runtime Files Deployed

Copied to `D:\Games\Red Dead Redemption\RDR-SteamGG.NET`:

- `CodeRED_AI_Menu.asi`
- `CodeRED_AI_Menu.ini`
- `data\codered\npc_roster.txt`
- `data\codered\actor_enum_map.csv`
- `data\codered\ai_behavior_actions.csv`

## Test Notes

Use F8 or Insert to open the menu. Use F5 after editing roster, enum map, or
action CSV. Start with `Spawn Selected NPC`, then `Make Spawned Actors Lawmen`,
then `Follow Player` or `Attack Nearest Hostile`.
