# Code RED Peer Clone Playable v0.3

Portable two-player playable sandbox for Code RED peer/clone sync.

This is not the final Red Dead game hook. It proves the network and control loop first: host, join, move, see the remote clone, and capture runtime logs.

Read first from the repo root:

```text
READ_FIRST_CodeRED_Peer_Clone_Playable_v0_3_PUBLIC_TEST.txt
```

Or read the local package file:

```text
READ_FIRST_PLAYABLE_TEST.txt
```

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

## Controls

- WASD / arrows: move
- Shift: boost
- Space: pulse
- Q: quit

## Boundary

Do not put this in the game folder yet. It is a playable connection proof before the in-game clone actor bridge.
