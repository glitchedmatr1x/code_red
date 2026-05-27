# CodeRED Peer Companion Test Plan

Test on the original `D:\Games\Red Dead Redemption` install only.

## Test A: ASI load and snapshot

1. Install only `CodeRED_PeerCompanion.asi`.
2. Launch normal single-player.
3. Wait at least 30 seconds.
4. Press F6.
5. Confirm `logs/codered_peer_companion.log` reports player actor, position,
   heading, health, and companion state.

## Test B: Local companion spawn

1. Wait at least 15 seconds after single-player loads.
2. Press F6 once.
3. Press F8 once.
4. Do not press other companion keys for 60 seconds.
5. Confirm one human companion appears within about 3 meters of the player.
6. Confirm there is no ScriptHook error box and no crash.
7. Press F9 only after the 60-second check.

## Test C: AI mode

Skipped for the spawn-fix pass. Task/follow natives remain disabled by default
until the visible spawn path is proven.

Legacy test:

1. Press F8.
2. Press F10.
3. Confirm the log toggles AI companion mode.
4. The companion should follow player when AI mode is on and idle when off.

## Test D: Peer app command path

1. Run `CodeRED_Peer_App.py`.
2. Start local server.
3. In game press F11 to enable peer-control.
4. Send commands: `follow_player`, `idle`, `friendly`, `hostile`,
   `teleport_to_player`.
5. Confirm each command appears in `logs/codered_peer_companion.log`.

## Test E: stability

Leave the game running for 10 minutes with the ASI loaded. There should be no
automatic spawns, no official multiplayer calls, no repeated invalid handle
calls, and no crash.
