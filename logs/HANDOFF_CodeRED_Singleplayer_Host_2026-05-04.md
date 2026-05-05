# HANDOFF — Code RED Singleplayer Host — 2026-05-04

## Verdict

A standalone-style singleplayer host still exists in the repo through:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/
```

It is the ScriptHookRDR `.asi` host lane, not the SC-CL lane.

## Current safe status

Working/proven from recent handoff trail:

```text
- ASI build path exists.
- ASI menu was previously proven to load in-game.
- Native bridge source is in CodeRED_AI_Menu.bridge_candidate.cpp.
- SC-CL full menu is not trusted and should not be used as the host.
```

Current caution:

```text
Raw CREATE_ACTOR_IN_LAYOUT vehicle spawns for Car01/Truck01 crashed.
The current safe setup disables spawn actions and installs a 7-entry safe roster.
```

## Fix made in this pass

The old batch build helper pointed at stale source:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp
```

It now delegates to the current PowerShell build helper, which builds:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp
```

Updated:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/build_bridge.bat
```

Added standalone-style setup wrapper:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/Run_CodeRED_Singleplayer_Host.bat
```

## How to use

From repo root after pulling:

```bat
related_apps\Code_RED_ScriptHookRDR_AI_Menu\Run_CodeRED_Singleplayer_Host.bat "D:\Games\Red Dead Redemption"
```

Or double-click it if the game root is:

```text
D:\Games\Red Dead Redemption
```

The wrapper runs:

```text
1. build_ai_menu_asi_windows.ps1
2. install_ai_menu_asi_windows.ps1
3. install_vehicle_first_menu_data_windows.ps1
```

## Expected in-game result

Open the menu with:

```text
F8 or INSERT
```

Expected footer:

```text
Roster 1-7 / 7
```

Do not use or trust:

```text
Roster ... / 413
```

That is the old large roster and was tied to crash risk.

## Important boundary

This host setup does not edit RPF archives.

It only installs:

```text
CodeRED_AI_Menu.asi
CodeRED_AI_Menu.ini
data/codered/*.csv
data/codered/*.txt
scratch/
```

## Next best pass

Re-enable only one spawn action at a time after adding hard guards around native actor creation.

Do not put Car01 or Truck01 back into the raw spawn roster. Those belong in the WGD/gringo vehicle-generator lane.
