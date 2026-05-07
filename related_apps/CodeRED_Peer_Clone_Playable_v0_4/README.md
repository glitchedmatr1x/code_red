# Code RED Peer Clone Playable v0.4

Portable two-player playable sandbox plus bridge-prep files for the future in-game clone actor hook.

This is not the final Red Dead game hook. It proves the network/control/clone loop first and now writes bridge files that a future ASI/script bridge can read.

## New in v0.4

- `bridge/local_player_state.json`
- `bridge/remote_players_state.json`
- `bridge/bridge_status.json`
- host-with-bot test for testing without another person
- bridge watcher utility
- same playable two-player top-down sandbox

## Run order

Host / Player A:

```bat
Run_Doctor.bat
Run_Host_And_Play_A.bat
```

Client / Player B:

```bat
Run_Join_Player_B.bat
```

Solo bot proof:

```bat
Run_Host_With_Bot_Test.bat
```

Bridge watcher:

```bat
Run_Bridge_Watch.bat
```

## Controls

- WASD / arrows: move
- Shift: boost
- Space: pulse
- B: force bridge file update
- Q: quit

## Boundary

Do not put this in the game folder yet. It is a playable connection proof before the in-game clone actor bridge.
