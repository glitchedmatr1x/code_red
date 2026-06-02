# Companion Controller 638 Implementation Report

Read-only content pass: no RPF, WSC, TR, tune, content, or retail game files were modified.

## Scope

Implemented a minimal no-TR-patch companion controller prototype in:

- `tools/CodeRED_PeerCompanion/CodeRED_PeerCompanion.cpp`
- `tools/CodeRED_PeerCompanion/data/codered/peer_companion.ini`
- `tools/CodeRED_PeerCompanion/build_bridge.bat`
- `tools/CodeRED_PeerCompanion/build_peer_companion_windows.ps1`

The prototype is limited to actor enum `638` by default.

## Build Result

Build command:

```bat
powershell -ExecutionPolicy Bypass -File tools\CodeRED_PeerCompanion\build_peer_companion_windows.ps1
```

Result:

- Build completed successfully.
- Output: `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\CodeRED_PeerCompanion.asi`
- SHA1: `E18F7EB26F6FD8B7B0030AE5B7E4C2BEB73BCF4C`
- Build log: `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\build_log.txt`

## SDK Signatures Used

From `D:\Games\Red Dead Redemption\ScriptHookRDR\sdk\inc\natives.h`:

| Native | SDK signature | Hash | Status |
|---|---|---:|---|
| `GET_PLAYER_ACTOR` | `Actor GET_PLAYER_ACTOR(Player player)` | `0xE8CFDD53` | Used |
| `GET_ACTOR_ENUM` | `int GET_ACTOR_ENUM(Actor actor)` | `0x0B28E9EC` | Used |
| `GET_ACTOR_FACTION` | `int GET_ACTOR_FACTION(Actor actor)` | `0x52E2A611` | Used |
| `SET_ACTOR_FACTION` | `void SET_ACTOR_FACTION(Actor actor, int faction)` | `0xCC63951A` | Used |
| `SET_ACTOR_IS_COMPANION` | `void SET_ACTOR_IS_COMPANION(Actor actor, BOOL toggle)` | `0x4C94EB9E` | Used |
| `TASK_FOLLOW_ACTOR` | `void TASK_FOLLOW_ACTOR(Actor actor, Actor followActor)` | `0x12F0911A` | Used |
| `TASK_PRIORITY_SET` | `void TASK_PRIORITY_SET(Any p0, Any p1)` | `0x3A95A656` | Compiled, config-gated |
| `CREATE_SQUAD_IN_LAYOUT` | `int CREATE_SQUAD_IN_LAYOUT(Layout layout, const char* squadName)` | `0xF7277A0F` | Compiled, config-gated |
| `SQUAD_JOIN` | `void SQUAD_JOIN(Any p0, Any p1)` | `0xB14302C8` | Compiled, config-gated |
| `SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION` | `int SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION(Any p0, Any p1, Any p2, Any p3, Any p4, Any p5)` | `0x1AC03C80` | Compiled, config-gated |

Additional already-used runtime helpers:

| Helper | Hash | Use |
|---|---:|---|
| `IS_ACTOR_VALID` | `0xBA6C3E92` | Actor handle validation |
| `IS_ACTOR_ALIVE` | `0x2F232639` | Adoption safety |
| `GET_TARGET_ACTOR` | `0x0EF7427B` | Safe target-actor adoption path |
| actor position getter used by existing ASI | `0x99BD9D6F` | Distance and logging |
| `TASK_CLEAR` | `0x16876A25` | Release/guard/wait cleanup |

## Implemented Behavior

### Adopt/follow actor 638

Hotkey: `F8`

Behavior:

1. Resolves player actor.
2. Uses `GET_TARGET_ACTOR` to inspect the currently targeted actor.
3. Requires the candidate to be valid, alive, non-player, enum `638`, and within `adopt_radius`.
4. Stores the actor handle as the current companion.
5. Marks it as borrowed/adopted, not Code RED-owned.
6. Logs enum, faction, position, distance, and adoption source.
7. Applies companion state:
   - `SET_ACTOR_FACTION(companion, 20)` when enabled.
   - `SET_ACTOR_IS_COMPANION(companion, true)` when enabled.
   - Squad route first only when explicitly enabled.
   - Fallback `TASK_FOLLOW_ACTOR(companion, player)` when squad route is skipped or fails.

### Guard/wait near current position

Hotkey: `F9`

Behavior:

- Clears the companion task.
- Optionally applies configured task priority.
- Does not call unknown guard-position natives by default.

### Regroup/follow again

Hotkey: `F10`

Behavior:

- Re-applies the same companion state and follow route to the adopted actor.

### Release/dismiss

Hotkey: `Backspace`

Behavior:

- Clears task.
- Clears companion flag if enabled.
- If the actor was spawned by Code RED, destroys it.
- If the actor was adopted from retail/mission content, does not destroy it.
- Clears stored handles.

## Command Bridge Additions

The existing file-command path now accepts:

- `adopt_638`
- `adopt_follow_638`
- `guard_wait_638`
- `regroup_638`
- `release_638`

## Config Additions

Added to `tools/CodeRED_PeerCompanion/data/codered/peer_companion.ini`:

```ini
companion_controller_enabled=true
adopt_target_actor_enabled=true
set_companion_faction_enabled=true
set_companion_flag_enabled=true
task_priority_enabled=false
squad_route_enabled=false
fallback_follow_enabled=true

adopt_actor_enum=638
adopt_radius=8.0
companion_faction=20
companion_follow_priority=1
```

## Squad Route Status

The squad route compiles, but it is disabled by default.

Reason: the SDK exposes `SQUAD_JOIN` and `SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION` with `Any` parameters. The hash and arity are known, but the exact argument semantics still need runtime proof. The code only calls them if `squad_route_enabled=true`.

When enabled, the current experimental call order is:

```text
CREATE_SQUAD_IN_LAYOUT(layout, "CodeREDCompanion638Squad")
SQUAD_JOIN(squad, player)
SQUAD_JOIN(squad, companion)
SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION(squad, player, 0, 0, 0, 0)
```

This is intentionally logged as an explicitly enabled `Any` route.

## Fallback Route Status

The fallback route compiles and is enabled by default:

```text
TASK_CLEAR(companion)
TASK_FOLLOW_ACTOR(companion, player)
```

`TASK_PRIORITY_SET` is compiled but disabled by default because its parameters are `Any`.

## Logging

Logs are written to:

- `logs\codered_peer_companion.log`

Important stages:

- `adopt_nearest_638`
- `adopt_actor_638`
- `companion_apply_state`
- `companion_squad_route`
- `companion_fallback_follow`
- `guard_wait_638`
- `regroup_follow_638`
- `despawn_companion`

## Important Limitation

The prototype does not perform a true all-world nearest actor scan yet.

Reason: no safe, proven global actor iterator path was found in the current ASI code. The SDK has iterator/objectset natives, but using them without a proven layout/object filter would be guesswork. For this pass, the safe adoption path is:

```text
target or aim at the nearby actor 638
-> press F8
-> ASI validates enum and distance
```

The log records this as:

```text
nearest_scan_status=unsupported_no_safe_global_actor_iterator
```

## Files Changed

- `tools/CodeRED_PeerCompanion/CodeRED_PeerCompanion.cpp`
- `tools/CodeRED_PeerCompanion/data/codered/peer_companion.ini`
- `tools/CodeRED_PeerCompanion/build_bridge.bat`
- `tools/CodeRED_PeerCompanion/build_peer_companion_windows.ps1`

## No Files Modified

- No RPF files.
- No WSC files.
- No TR files.
- No tune files.
- No retail game executable or retail content files.
