# Companion Controller 638 F8 Error Fix Report

Scope: Code RED source/tool/plugin files only. No RPF, WSC, TR, tune, content, or retail game files were modified.

## Files Inspected

- `tools/CodeRED_PeerCompanion/CodeRED_PeerCompanion.cpp`
- `tools/CodeRED_PeerCompanion/data/codered/peer_companion.ini`
- `tools/CodeRED_PeerCompanion/build/build_log.txt`
- `D:\Games\Red Dead Redemption\logs\codered_peer_companion.log`
- `research/deep_search_outputs/Companion_Controller_638_Implementation_Report.md`
- `research/deep_search_outputs/Companion_Controller_638_Test_Plan.md`

## Runtime Failure Point Found

The available runtime log does not show a crash inside `SET_ACTOR_FACTION`, `SET_ACTOR_IS_COMPANION`, `TASK_FOLLOW_ACTOR`, or squad calls. It shows F8 reached the adoption path, resolved the player actor, then failed because the target actor was not a valid/live actor:

```text
ENTER adopt_nearest_638
ENTER resolve_player_actor
EXIT resolve_player_actor OK
ENTER adopt_actor_638
EXIT adopt_actor_638 FAILED reason=invalid_or_dead_candidate
adopt_nearest_638 nearest_scan_status=unsupported_no_safe_global_actor_iterator
EXIT adopt_nearest_638 FAILED reason=no_candidate
```

The root cause from the current evidence is target acquisition: `GET_TARGET_ACTOR` did not provide a valid actor handle when F8 was pressed. The previous code did not log the target handle before validating it, so the user-facing error was too vague.

The log also showed:

```text
load_config defaulted reason=missing_ini path=D:\Games\Red Dead Redemption\data\codered\peer_companion.ini
```

That means the installed game folder did not have the updated INI. The ASI still runs with compiled defaults, but testing should install the INI so the new kill switches are explicit.

## Source Changes Made

Updated:

- `tools/CodeRED_PeerCompanion/CodeRED_PeerCompanion.cpp`
- `tools/CodeRED_PeerCompanion/data/codered/peer_companion.ini`

Generated:

- `tools/CodeRED_PeerCompanion/build/CodeRED_PeerCompanion.asi`
- `tools/CodeRED_PeerCompanion/build/build_log.txt`
- `tools/CodeRED_PeerCompanion/build/CodeRED_PeerCompanion_build_report.json`

## Defensive F8 Stages Added

F8 now logs each stage:

```text
[PeerCompanion] F8 key detected: adopt/follow requested
ENTER stage_a_get_target_actor
stage_a target native call reached GET_TARGET_ACTOR hash=0x0EF7427B
stage_a target_actor_handle=...
ENTER adopt_actor_638
adopt_candidate source=GET_TARGET_ACTOR actor=... enum=... distance=... xyz=...
ENTER companion_apply_state
stage_c SET_ACTOR_FACTION call reached ...
stage_c SET_ACTOR_IS_COMPANION call reached ...
stage_d TASK_FOLLOW_ACTOR call reached ...
```

If target acquisition fails, it now logs exactly:

```text
[PeerCompanion] F8 adopt failed: no valid targeted actor.
EXIT stage_a_get_target_actor FAILED reason=invalid_target_actor
EXIT adopt_nearest_638 FAILED reason=no_valid_targeted_actor
```

## Native Safety Changes

Added low-level SEH-wrapped native helpers for F8-stage calls:

- `GET_TARGET_ACTOR`
- `TASK_CLEAR`
- `SET_ACTOR_FACTION`
- `SET_ACTOR_IS_COMPANION`
- `TASK_FOLLOW_ACTOR`

These wrappers log native exceptions as stage-specific failures instead of letting F8 fail without context.

## New INI Toggles

Added requested names:

```ini
enable_set_faction=true
enable_set_companion=false
enable_task_follow=true
enable_task_priority=false
enable_squad_route=false
debug_adopt_only=false
allow_any_target=false
```

Existing internal names remain supported for compatibility:

```ini
set_companion_faction_enabled=true
set_companion_flag_enabled=false
task_priority_enabled=false
squad_route_enabled=false
fallback_follow_enabled=true
```

## Default Native State

Enabled by default:

- `GET_PLAYER_ACTOR`
- `GET_TARGET_ACTOR`
- `GET_ACTOR_ENUM`
- `GET_ACTOR_FACTION`
- `SET_ACTOR_FACTION`
- `TASK_CLEAR`
- `TASK_FOLLOW_ACTOR`

Disabled/gated by default:

- `SET_ACTOR_IS_COMPANION`
- `TASK_PRIORITY_SET`
- `CREATE_SQUAD_IN_LAYOUT`
- `SQUAD_JOIN`
- `SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION`

Reason:

- `SET_ACTOR_IS_COMPANION` is safe-looking in the SDK but not required for the first proof.
- `TASK_PRIORITY_SET` uses `Any` parameters.
- The squad route uses `Any` parameters and still needs isolated runtime proof.

## Build Result

Command:

```bat
powershell -ExecutionPolicy Bypass -File tools\CodeRED_PeerCompanion\build_peer_companion_windows.ps1
```

Result:

- Compile succeeded.
- Output: `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\CodeRED_PeerCompanion.asi`
- SHA1: `4BA15D2512352CE471831DA8FC8666BA98029D46`

## Remaining Risk

The current implementation still uses the safe target-actor path, not a global actor scan. If the game does not expose actor 638 through `GET_TARGET_ACTOR`, F8 will now fail cleanly and log the target handle failure. A true nearest-actor scan should only be added after a proven ScriptHookRDR actor iterator/objectset method is identified.

## Exact Log Line To Send Back If Still Broken

Send the last 80-120 lines around F8, especially any of:

```text
[PeerCompanion] F8 key detected: adopt/follow requested
stage_a target_actor_handle=...
[PeerCompanion] F8 adopt failed: no valid targeted actor.
adopt_candidate source=GET_TARGET_ACTOR actor=... enum=... distance=...
stage_c_set_actor_faction exception=...
stage_c_set_actor_is_companion exception=...
stage_d_task_follow_actor exception=...
```
