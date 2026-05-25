# Code RED Link Next Pass Report

Status: implemented and compiled; in-game runtime proof still pending.

Changes:
- ASI timestamps now use Unix epoch milliseconds.
- ASI logs successful local state writes every 5 seconds.
- ASI logs successful remote state reads every 5 seconds.
- `CodeRED_Link_TestClient.py` now writes epoch timestamps.
- Added `CodeRED_Link_LANRelay.py` for external UDP relay testing.

Safety:
- No sockets were added to the ASI.
- No GameSpy, official MP backend, RPF, WSC, or content edits.
- Soul Stealer remains disabled.
- World actor scan remains disabled.
- Puppet sync still moves only the single tracked `F9` puppet handle.

Build:
- Output: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\build\CodeRED_Remote_Menu.asi`
- Installed: `D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi`

Next runtime proof:
1. Confirm game launches.
2. Confirm `logs\codered_remote_menu.log` shows `CodeRED Link: local state written`.
3. Run `CodeRED_Link_TestClient.py`.
4. Press `F9`.
5. Confirm `CodeRED Link: remote state read`.
6. Confirm `CodeRED Link: puppet sync`.
