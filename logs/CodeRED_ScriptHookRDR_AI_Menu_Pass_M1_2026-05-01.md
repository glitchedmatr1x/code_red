# CodeRED ScriptHookRDR AI Menu — Pass M1

Date: 2026-05-01
Branch: `main`

## Goal

Prepare a conservative in-game CodeRED AI menu scaffold for Red Dead Redemption PC using ScriptHookRDR.

## Added / updated

- `related_apps/Code_RED_ScriptHookRDR_AI_Menu/README.md`
- `related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp`
- `related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.ini`
- `related_apps/Code_RED_ScriptHookRDR_AI_Menu/build_bridge.bat`
- `data/codered/npc_roster.txt`

## Safety profile

This pass is source-only and intentionally avoids risky native calls.

It only:

- Resolves ScriptHookRDR exports dynamically with `GetProcAddress`.
- Registers a ScriptHookRDR script loop.
- Registers a keyboard handler.
- Draws a CodeRED overlay with `drawRect` / `drawText`.
- Loads a plain text NPC roster.
- Writes a JSON action-plan request.

It does not:

- Spawn actors.
- Delete actors.
- Modify world state.
- Call task/combat natives.
- Load the old Smart Menu into the live game.

## Test plan for user machine

1. Confirm RDR boots without any old Smart Menu runtime files.
2. Confirm clean ScriptHookRDR boot with only `dinput8.dll` and `ScriptHookRDR.dll`.
3. Build `CodeRED_AI_Menu.asi` using `build_bridge.bat`.
4. Copy only the built `.asi`, its `.ini`, and the `data/codered` / `scratch` folders beside `RDR.exe`.
5. Launch RDR.
6. Press F8.
7. Confirm CodeRED menu appears.
8. Use LEFT/RIGHT to cycle NPC names.
9. Use UP/DOWN to select action.
10. Press ENTER and verify `scratch/codered_ai_action_plan.json` is written.

## Next pass

Pass M2 should add one low-risk ScriptHookRDR state proof:

- detect local player actor
- read player position
- write state JSON

Spawn natives should wait until the menu and state proof are stable.
