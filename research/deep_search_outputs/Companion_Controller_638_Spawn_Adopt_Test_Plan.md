# Companion Controller 638 Spawn/Adopt Test Plan

## Install

Copy:

```text
D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\CodeRED_PeerCompanion.asi
```

beside `RDR.exe`.

Copy:

```text
D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\data\codered\peer_companion.ini
```

to:

```text
D:\Games\Red Dead Redemption\data\codered\peer_companion.ini
```

Confirm the INI exists in the game folder. A previous runtime log showed it was missing.

## Controls

| Key | Action |
|---|---|
| `F6` | Snapshot log |
| `F7` | Spawn actor 638 near/in front of player and adopt/follow |
| `F8` | Nearest adopt intentionally skipped until safe iterator exists |
| `F9` | Guard/wait |
| `F10` | Regroup/follow again |
| `Backspace` | Release/dismiss; destroys only Code RED-spawned actor |
| `F12` | Help |

## Safe Default INI

```ini
enable_spawn_638=true
spawn_actor_enum=638
spawn_distance=3.0
enable_set_faction=true
companion_faction=20
enable_set_companion=true
enable_task_follow=true
enable_task_priority=false
enable_squad_route=false
enable_target_adopt=false
enable_nearest_scan=false
debug_adopt_only=false
```

## Test A: Load

1. Launch normal single-player.
2. Wait 15 seconds.
3. Press `F12`.

Expected:

- Overlay/help appears.
- `logs\codered_peer_companion.log` exists.

## Test B: Snapshot

1. Press `F6`.

Expected:

```text
snapshot player_valid=true
```

## Test C: Spawn / Adopt

1. Stand in open ground.
2. Press `F7` once.

Expected:

- Actor 638 appears near/in front of player.
- Log shows `STREAMING_REQUEST_ACTOR`, `CREATE_ACTOR_IN_LAYOUT`, and `TASK_FOLLOW_ACTOR`.
- The spawned actor is stored as the companion.

## Test D: Regroup

1. Move away a little.
2. Press `F10`.

Expected:

- Follow task is reissued.

## Test E: Guard / Wait

1. Press `F9`.

Expected:

- Current task clears.
- Companion should pause/wait if the engine accepts the clear/stand path.

## Test F: Release

1. Press `Backspace`.

Expected:

- Because F7 spawned the actor, the cleanup path may destroy that Code RED-owned actor.
- Retail actors are not destroyed by release.

## F8 Behavior

Pressing F8 should not error. It should log:

```text
[PeerCompanion] F8 nearest adopt skipped: no safe actor iterator available; use F7 spawn/adopt.
```

## If F7 Fails

Send the last 100 lines of:

```text
D:\Games\Red Dead Redemption\logs\codered_peer_companion.log
```

Most important lines:

```text
[PeerCompanion] F7 spawn/adopt requested
spawn_stage STREAMING_REQUEST_ACTOR call reached enum=638
EXIT spawn_stage_streaming_request_actor FAILED reason=...
spawn_stage CREATE_ACTOR_IN_LAYOUT call reached enum=638
spawn_stage create_actor_return=...
EXIT spawn_companion FAILED reason=...
stage_c_set_actor_faction exception=...
stage_c_set_actor_is_companion exception=...
stage_d_task_follow_actor exception=...
```

## Isolation Switches

If F7 spawns but errors afterward:

### Spawn/adopt handle only

```ini
debug_adopt_only=true
```

### Disable companion flag

```ini
enable_set_companion=false
```

### Disable follow task

```ini
enable_task_follow=false
```

### Disable streaming request if actor 638 never reports loaded

```ini
enable_streaming_request=false
```

Only change one switch per test so the log identifies the failing stage.
