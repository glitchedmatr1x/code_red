# Companion Controller 638 Spawn/Adopt Report

Scope: Code RED plugin/source only. No RPF, WSC, TR, tune, content, retail executable, or retail game files were modified.

## Reason For Redesign

The previous F8 route relied on `GET_TARGET_ACTOR`. Runtime logs showed that the ASI loaded and player resolution worked, but `GET_TARGET_ACTOR` did not return a valid actor even when actor 638 was visually in front of the player. Current-target/crosshair detection is therefore not reliable enough to be the main workflow.

## New Main Workflow

F7 now does the primary companion flow:

```text
F7
-> validate player actor
-> compute point 3m in front of player
-> STREAMING_REQUEST_ACTOR(638, TRUE, FALSE)
-> wait for STREAMING_IS_ACTOR_LOADED(638, 0), timeout 3000ms
-> CREATE_ACTOR_IN_LAYOUT(CodeREDPeerCompanion layout, enum 638, spawn point)
-> validate actor handle
-> store as Code RED-owned companion
-> SET_ACTOR_FACTION(companion, 20), if enabled
-> SET_ACTOR_IS_COMPANION(companion, TRUE), if enabled
-> TASK_FOLLOW_ACTOR(companion, player), if enabled
```

F8 no longer uses target/crosshair detection by default. It logs:

```text
[PeerCompanion] F8 nearest adopt skipped: no safe actor iterator available; use F7 spawn/adopt.
```

## SDK Signatures Found

From `D:\Games\Red Dead Redemption\ScriptHookRDR\sdk\inc\natives.h`:

| Native | Signature | Hash | Used |
|---|---|---:|---|
| `GET_POSITION` | `void GET_POSITION(Actor actor, Vector3* position)` | `0x99BD9D6F` | Existing player/spawn math |
| `GET_HEADING` | `float GET_HEADING(Actor actor)` | `0x42DE39F0` | Existing spawn direction |
| `GET_PLAYER_ACTOR` | `Actor GET_PLAYER_ACTOR(Player player)` | `0xE8CFDD53` | Player validation |
| `FIND_NAMED_LAYOUT` | `Layout FIND_NAMED_LAYOUT(const char* layoutName)` | `0x5699DE7E` | Layout reuse |
| `CREATE_LAYOUT` | `Layout CREATE_LAYOUT(const char* layoutName)` | `0x6CA53214` | Layout fallback |
| `CREATE_ACTOR_IN_LAYOUT` | `Actor CREATE_ACTOR_IN_LAYOUT(Layout layout, const char* layoutName, int actorEnum, Vector2 positionXY, float positionZ, Vector2 orientationXY, float orientationZ)` | `0x8D67F397` | F7 spawn |
| `STREAMING_REQUEST_ACTOR` | `void STREAMING_REQUEST_ACTOR(int actorEnum, BOOL p1, BOOL p2)` | `0xB0A79FEE` | F7 streaming request |
| `STREAMING_IS_ACTOR_LOADED` | `BOOL STREAMING_IS_ACTOR_LOADED(int actorEnum, int p1)` | `0x7DF72579` | F7 streaming wait |
| `STREAMING_EVICT_ACTOR` | `void STREAMING_EVICT_ACTOR(int actorEnum, int p1)` | `0x6661CF89` | Found, not used by default |
| `GET_ACTOR_ENUM` | `int GET_ACTOR_ENUM(Actor actor)` | `0x0B28E9EC` | Validation/logging |
| `GET_ACTOR_FACTION` | `int GET_ACTOR_FACTION(Actor actor)` | `0x52E2A611` | Logging |
| `SET_ACTOR_FACTION` | `void SET_ACTOR_FACTION(Actor actor, int faction)` | `0xCC63951A` | Enabled by default |
| `SET_ACTOR_IS_COMPANION` | `void SET_ACTOR_IS_COMPANION(Actor actor, BOOL toggle)` | `0x4C94EB9E` | Enabled by default in INI |
| `TASK_FOLLOW_ACTOR` | `void TASK_FOLLOW_ACTOR(Actor actor, Actor followActor)` | `0x12F0911A` | Enabled by default |
| `TASK_STAND_STILL` | `void TASK_STAND_STILL(Actor actor, float p1, int p2, int p3)` | `0x6F80965D` | Existing idle path |
| `TASK_CLEAR` | `void TASK_CLEAR(Actor actor)` | `0x16876A25` | Guard/release/follow reset |
| `TASK_PRIORITY_SET` | `void TASK_PRIORITY_SET(Any p0, Any p1)` | `0x3A95A656` | Compiled but disabled |
| `CREATE_OBJECT_ITERATOR` | `int CREATE_OBJECT_ITERATOR(Layout layout)` | `0xD8A12B74` | Found, not used |
| `START_OBJECT_ITERATOR` | `Object START_OBJECT_ITERATOR(Iterator iterator)` | `0xE96A0318` | Found, not used |
| `OBJECT_ITERATOR_NEXT` | `int OBJECT_ITERATOR_NEXT(Iterator iterator)` | `0xD88DC865` | Found, not used |
| `GET_ACTOR_FROM_OBJECT` | `int GET_ACTOR_FROM_OBJECT(Any p0)` | `0x34F0AD96` | Found, not used |

## Safe Actor Iterator Status

F8 nearest-adopt is intentionally disabled.

Reason: the SDK exposes object iterator primitives, but the safe layout/object filter for "nearby live actors around player" is not proven. Implementing it now would be guesswork and could create the same crash/error class as the target route.

## Source Changes

Updated:

- `tools/CodeRED_PeerCompanion/CodeRED_PeerCompanion.cpp`
- `tools/CodeRED_PeerCompanion/data/codered/peer_companion.ini`

Built:

- `tools/CodeRED_PeerCompanion/build/CodeRED_PeerCompanion.asi`
- `tools/CodeRED_PeerCompanion/build/build_log.txt`

## INI Defaults

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

## Build Result

Command:

```bat
powershell -ExecutionPolicy Bypass -File tools\CodeRED_PeerCompanion\build_peer_companion_windows.ps1
```

Result:

- Compile succeeded.
- Output: `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\CodeRED_PeerCompanion.asi`
- SHA1: `6D7DE5A062908D775CCF03932DDC7791E2D240E6`

## Expected F7 Log

```text
[PeerCompanion] F7 spawn/adopt requested
ENTER spawn_stage_streaming_request_actor
spawn_stage STREAMING_REQUEST_ACTOR call reached enum=638
EXIT spawn_stage_streaming_request_actor OK loaded
spawn_point player_xyz=...
spawn_stage CREATE_ACTOR_IN_LAYOUT call reached enum=638
spawn_stage create_actor_return=...
ENTER companion_apply_state
stage_c SET_ACTOR_FACTION call reached actor=... faction=20
stage_c SET_ACTOR_IS_COMPANION call reached enabled=true
stage_d TASK_FOLLOW_ACTOR call reached actor=... follow_actor=...
EXIT spawn_companion OK spawned_and_adopted
```

## If F7 Fails

Send back the last 100 lines around:

```text
[PeerCompanion] F7 spawn/adopt requested
spawn_stage_streaming_request_actor
spawn_stage_create_actor
create_actor_return
stage_c_set_actor_faction
stage_c_set_actor_is_companion
stage_d_task_follow_actor
```

Those lines identify whether the blocker is streaming, create actor, faction, companion flag, or follow task.
