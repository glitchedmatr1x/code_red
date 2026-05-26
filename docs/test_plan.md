# Code RED Remote Menu Test Plan

1. Copy `CodeRED_Remote_Menu.asi` beside `RDR.exe`.
2. Copy `data/codered/remote_menu.ini` beside `RDR.exe` preserving folders.
3. Launch single-player/offline and wait at least 60 seconds after loading.
4. Confirm `logs/codered_remote_menu.log` is created and contains `CodeRED heartbeat`.
5. Confirm the log shows `actor_scan_enabled=false`, `overlay_enabled=false`, and `teleport_write_enabled=false`.
6. Confirm no crash occurs with the default diagnostic gates.
7. Confirm `data/codered/link/local_player_state.json` appears and contains real coordinates.
8. Do not run the test client until local-state write survives at least 60 seconds.
9. In a separate console run:
   `py -3 D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\CodeRED_Link_TestClient.py`
10. Confirm `data/codered/link/remote_player_state.json` updates once per second.
11. Enable remote read in the INI and press `F11` after reloading config.
12. Press `F9` once to spawn one Code RED-owned puppet actor near the player.
13. Enable puppet sync and actor handle polling in the INI, then press `F12` after reloading config.
14. Confirm the log contains `CodeRED Link: puppet sync`.
15. Press `Backspace` and confirm the tracked puppet is released/hidden. This does not call an actor delete native.
16. Do not press `F8/E`; Soul Stealer actor scanning remains disabled.
17. Do not press `F6`; player teleport writing remains disabled unless explicitly re-enabled.
18. Do not enable blip or label modes until the log-marker spawn and file-sync paths are stable.

Optional LAN relay after local file test works:

1. On PC A:
   `py -3 D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\CodeRED_Link_LANRelay.py --peer PC_B_IP`
2. On PC B:
   `py -3 D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\CodeRED_Link_LANRelay.py --peer PC_A_IP`
3. Launch each game, wait for `local_player_state.json`, press `F9`, and watch for `CodeRED Link: puppet sync`.
4. Keep Windows Firewall/LAN port `47777/UDP` in mind if no packets arrive.

No RPF, WSC, multiplayer, actor stealing, world scanning, or sector toggles are involved in this pass.
