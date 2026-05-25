# Code RED Remote Menu Native Probe Report

Status: implemented, build verified, runtime probe pending user launch.

Build:
- Source: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\CodeRED_Remote_Menu.cpp`
- Output: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\build\CodeRED_Remote_Menu.asi`
- Installed ASI: `D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi`
- SHA1: `D44D1B15F1B1FFA08CA0703114AD455DD17A680E`

Read-only probe behavior:
- Runs once after ScriptHook registration and `startup_delay_ms`.
- Reads player actor with `GET_PLAYER_ACTOR`.
- Validates player actor with `IS_ACTOR_VALID`.
- Reads player position with `GET_POSITION`.
- Reads player heading with `GET_HEADING`.
- Logs one `Native probe:` line to `D:\Games\Red Dead Redemption\logs\codered_remote_menu.log`.

Safety gates:
- `overlay_enabled=false`
- `actor_scan_enabled=false`
- `teleport_write_enabled=false`
- No world actor scan is performed.
- No content RPF, WSC, XML, save, or multiplayer file is modified.

Expected runtime proof line:

```text
Native probe: player_actor=<handle> valid=1 position_read=1 pos=<x>,<y>,<z> heading=<heading> actor_scan_enabled=0 overlay_enabled=0
```
