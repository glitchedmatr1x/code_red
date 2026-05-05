# Code RED source/decompiled export
# Source: related_apps/Code_RED_ScriptHookRDR_AI_Menu/README.md
# SHA1: 6fa05834740f9d0a28da3f053cf3f3e557286841

# CodeRED ScriptHookRDR AI Menu

Source scaffold for an in-game CodeRED AI companion menu for Red Dead Redemption PC using ScriptHookRDR. This pass adds a data-driven actor enum map so actors can be edited from CSV/Python after one rebuild.


## Native bridge source note

The compiled `CodeRED_AI_Menu.asi` in the uploaded package shows the native bridge is newer than the bundled C++ source. The bundled `CodeRED_AI_Menu.cpp` is kept for reference, but it does not contain the native spawn bridge. Do not rebuild it alone unless Codex has first merged the current native bridge source.

For this actor enum pass, use:

```text
patches/CodeRED_native_bridge_merge_notes.md
patches/CodeRED_AI_Menu_actor_enum_loader.diff
patches/CodeRED_AI_Menu_actor_enum_loader_reference.cpp
```

Merge that loader into the current native bridge source, rebuild once, then actor edits become CSV/Python-only.

This first pass is intentionally conservative:

- Proves ScriptHookRDR script registration.
- Proves keyboard input capture.
- Proves `drawRect` / `drawText` overlay rendering.
- Loads editable roster/config text files.
- Loads `data/codered/actor_enum_map.csv` for actor enum resolution.
- Supports inline `label|actor_enum` roster entries for quick tests.
- Writes a selected action plan to `scratch/codered_ai_action_plan.json` with `actor_enum` resolution fields.
- The source-side resolver is intentionally data-driven so actor rows can be updated without changing C++ again.
- The included compiled ASI from the uploaded package is the previous runtime copy; rebuild once to activate this source update.

## Codex target

Ask Codex to compile `main` and focus only this folder:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/
```

Primary file:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp
```

Build helper:

```bat
related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_bridge.bat
```

Expected output:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/build/CodeRED_AI_Menu.asi
```

The source is intentionally written to use `GetProcAddress` for ScriptHookRDR exports. It should not require `ScriptHookRDR.lib` or any extra import library.

## Codex validation checklist

Codex should verify:

```text
1. cl.exe can compile CodeRED_AI_Menu.cpp as x64 DLL output named CodeRED_AI_Menu.asi.
2. The build does not require ScriptHookRDR.lib.
3. The build output folder is created automatically.
4. The source does not call actor spawn/combat/delete natives yet.
5. The plugin writes scratch/codered_ai_action_plan.json when ENTER is pressed in the menu.
6. The repo contains data/codered/npc_roster.txt for roster loading.
7. The repo contains data/codered/actor_enum_map.csv for actor enum lookup.
8. F5 reloads both the roster and actor enum map.
```

## Why source-only first?

The current crash reports show the game can fail during hook loading. This pass should be used to build a small, low-risk `.asi` plugin that only draws and writes files. Once the overlay is stable in-game, the next pass can wire spawn/follow/defend natives.

## Runtime flow

```text
RDR.exe
-> dinput8.dll
-> ScriptHookRDR.dll
-> CodeRED_AI_Menu.asi
-> reads data/codered/npc_roster.txt
-> draws in-game overlay
-> writes scratch/codered_ai_action_plan.json
```

## Install layout after build

Copy these into the folder where `RDR.exe` is located:

```text
CodeRED_AI_Menu.asi
CodeRED_AI_Menu.ini
```

Keep these folders next to `RDR.exe`:

```text
data/codered/npc_roster.txt
data/codered/actor_enum_map.csv
scratch/
```

## Controls

Default controls:

```text
F8      open/close menu
INSERT  open/close menu
UP      previous item
DOWN    next item
LEFT    previous NPC model
RIGHT   next NPC model
ENTER   write selected action plan
F5      reload roster and actor enum map
BACK    close menu
ESC     close menu
```

## First-pass menu actions

```text
Spawn selected NPC request
Follow player request
Guard position request
Defend player request
Attack nearest hostile request
Regroup near player request
Dismiss AI guest request
Status request
```

In this pass, these actions only write JSON requests. The next pass will add real ScriptHookRDR native behavior execution.


## Actor enum CSV workflow

After rebuilding the ASI once, use this file to edit actors without recompiling:

```text
data/codered/actor_enum_map.csv
```

CSV format:

```csv
label,actor_enum,category,source,aliases,notes
amb_prostitute,12345,ambient,manual,,known-good enum
player_marston,0x00003039,player_like,manual,marston|john_marston,known-good enum
```

Then press **F5** in the in-game menu. The selected NPC line will show either:

```text
ENUM: 12345 / 0x00003039
```

or:

```text
ENUM: unresolved - add row in data/codered/actor_enum_map.csv
```

Python helper:

```bat
py -3 tools\codered_actor_enum_workbench.py validate
py -3 tools\codered_actor_enum_workbench.py list --filter army
py -3 tools\codered_actor_enum_workbench.py set amb_prostitute 12345
py -3 tools\codered_actor_enum_workbench.py build-roster --resolved-only
```

Full workflow doc:

```text
docs/codered/actor_enum_editing_workflow.md
```

## Build

Use Visual Studio Developer Command Prompt or another compiler configured for Windows DLL builds.

From the repository root:

```bat
related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_bridge.bat
```

## Safety notes

- Do not load the old Smart Menu files live while testing this scaffold.
- Test with only ScriptHookRDR + this one plugin.
- If RDR crashes before the menu opens, temporarily rename `dinput8.dll` to confirm whether the hook chain is the source.
- Check `ScriptHookRDR.log` after every crash.
