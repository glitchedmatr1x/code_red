# Code RED Link File Bridge Report

Status: implemented and compiled; in-game runtime proof pending.

Build:
- ASI: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\build\CodeRED_Remote_Menu.asi`
- Installed ASI: `D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi`
- SHA1: `57524C344C8AA740945FA1536725390978AF42B8`
- Build result: `cl.exe exit: 0`

Implemented:
- ASI writes `D:\Games\Red Dead Redemption\data\codered\link\local_player_state.json`.
- ASI reads `D:\Games\Red Dead Redemption\data\codered\link\remote_player_state.json`.
- ASI syncs only the tracked `F9` puppet actor to fresh remote state.
- Remote state older than `stale_ms` is treated as disconnected.
- `CodeRED_Link_TestClient.py` writes a test orbit path for `remote_player_state.json`.

External test client proof:

```text
Code RED Link test client
local : D:\Games\Red Dead Redemption\data\codered\link\local_player_state.json
remote: D:\Games\Red Dead Redemption\data\codered\link\remote_player_state.json
[0001] remote pos=(0.000, 5.000, 0.000) heading=180.0 local=no
[0002] remote pos=(1.597, 4.738, 0.000) heading=198.6 local=no
[0003] remote pos=(3.067, 3.949, 0.000) heading=217.8 local=no
```

Runtime proof still needed:
- Launch game.
- Wait for `Native probe`.
- Confirm `local_player_state.json` is created by the ASI.
- Run test client.
- Press `F9`.
- Confirm `CodeRED Link: puppet sync` in `logs\codered_remote_menu.log`.
