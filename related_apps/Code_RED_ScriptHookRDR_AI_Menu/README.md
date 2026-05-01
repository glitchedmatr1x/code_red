# CodeRED ScriptHookRDR AI Menu

Source-only scaffold for an in-game CodeRED AI companion menu for Red Dead Redemption PC using ScriptHookRDR.

This first pass is intentionally conservative:

- Proves ScriptHookRDR script registration.
- Proves keyboard input capture.
- Proves `drawRect` / `drawText` overlay rendering.
- Loads editable roster/config text files.
- Writes a selected action plan to `scratch/codered_ai_action_plan.json`.
- Does **not** spawn actors yet.
- Does **not** call risky actor/native spawn functions yet.

## Why source-only first?

The current crash reports show the game can fail during hook loading. This pass should be used to build a small, low-risk `.asi` plugin that only draws and writes files. Once the overlay is stable in-game, the next pass can wire spawn/follow/defend natives.

## Runtime flow

```text
RDR.exe
-> dinput8.dll
-> ScriptHookRDR.dll
-> CodeRED_AI_Menu.asi
-> reads data/codered/npc_roster.txt
-> reads data/codered/ai_menu_config.ini
-> draws in-game overlay
-> writes scratch/codered_ai_action_plan.json
```

## Install layout after build

Copy these into the folder where `RDR.exe` is located:

```text
CodeRED_AI_Menu.asi
CodeRED_AI_Menu.ini
```

Keep these folders next to `RDR.exe`, or update `CodeRED_AI_Menu.ini` paths:

```text
data/codered/npc_roster.txt
data/codered/ai_menu_config.ini
scratch/
```

## Controls

Default controls:

```text
F8      open/close menu
UP      previous item
DOWN    next item
LEFT    previous NPC model
RIGHT   next NPC model
ENTER   write selected action plan
BACK    close menu
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

## Build

Use Visual Studio Developer Command Prompt or another compiler configured for Windows DLL builds.

The batch file is a template:

```bat
build_bridge.bat
```

You may need to adjust `SCRIPT_HOOK_RDR_SDK` and compiler paths for your machine.

## Safety notes

- Do not load the old Smart Menu files live while testing this scaffold.
- Test with only ScriptHookRDR + this one plugin.
- If RDR crashes before the menu opens, temporarily rename `dinput8.dll` to confirm whether the hook chain is the source.
- Check `ScriptHookRDR.log` after every crash.
