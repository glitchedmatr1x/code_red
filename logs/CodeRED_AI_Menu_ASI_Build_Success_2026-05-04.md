# Code RED AI Menu ASI Build Success — 2026-05-04

## Command

```powershell
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_ai_menu_asi_windows.ps1
```

## Result

```text
[CodeRED] cl.exe exit: 0
Built: D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_ScriptHookRDR_AI_Menu\build\CodeRED_AI_Menu.asi
Length: 379904
SHA1: A68CCB9F518BF85B70A52D41C2A6B6CE58FAE484
Report: D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_ScriptHookRDR_AI_Menu\build\CodeRED_AI_Menu_build_report.json
```

## Link fix included

The successful build used `user32.lib`, required for `GetAsyncKeyState`.

## Next step

Install/stage the `.asi` beside the game executable using:

```powershell
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_ai_menu_asi_windows.ps1 -GameRoot "D:\Games\Red Dead Redemption"
```

Then test in-game:

```text
Open Code RED AI Menu
Select ACTOR_VEHICLE_Car01
Run Spawn Selected NPC
```

## Boundary

Build only. This command did not install files into the game folder and did not modify RPF archives.
