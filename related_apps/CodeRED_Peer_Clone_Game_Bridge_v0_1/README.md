# Code RED Peer Clone Game Bridge v0.1

This is a standalone ASI-side bridge for Peer Clone public tests. It reads:

- `bridge/local_player_state.json`
- `bridge/remote_players_state.json`
- `bridge/bridge_status.json`

It writes:

- `runtime/codered_peer_clone_game_bridge.jsonl`

Boundaries:

- Does not edit RPFs.
- Does not touch live `content.rpf`.
- Does not restore official multiplayer.
- Does not spawn vehicles.

## Modes

- `dry-run`: run `CodeRED_Peer_Clone_Game_Bridge_DryRun.py` outside the game.
- `log-only`: ASI reads remote state and writes local player state, but never spawns.
- `spawn-test`: ASI spawns one human clone near the local player.
- `move-test`: ASI spawns one human clone and interpolates it from remote player state.

Edit `CodeRED_Peer_Clone_Game_Bridge.ini` beside the ASI and set:

```ini
mode=move-test
```

For the first proof, start Red Dead with the ASI already loaded, then edit
`bridge/remote_players_state.json`. In `move-test`, the clone should move as the
remote `x`, `y`, `z`, and `heading` values change.

## Hotkeys

- `F11`: kill switch. Cleans up the clone and disables bridge actions until toggled again.
- `F12`: cleanup clone.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File related_apps\CodeRED_Peer_Clone_Game_Bridge_v0_1\build_peer_clone_game_bridge_windows.ps1
```

Output:

```text
related_apps\CodeRED_Peer_Clone_Game_Bridge_v0_1\build\CodeRED_Peer_Clone_Game_Bridge.asi
```
