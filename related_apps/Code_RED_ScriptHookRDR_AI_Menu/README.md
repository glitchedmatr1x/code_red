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
F5      reload roster
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
