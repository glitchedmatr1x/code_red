# Companion Controller 638 Test Plan

This test plan is for the no-TR-patch ScriptHookRDR companion prototype.

## Install

Copy only these files beside `RDR.exe`:

- `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\CodeRED_PeerCompanion.asi`
- `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\data\codered\peer_companion.ini` to `data\codered\peer_companion.ini`

Do not install old trainers or extra ASIs for this test.

## Baseline Config

Use these defaults first:

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
```

This tests the safe fallback route first:

```text
SET_ACTOR_FACTION
SET_ACTOR_IS_COMPANION
TASK_CLEAR
TASK_FOLLOW_ACTOR
```

## Test A: ASI Load

1. Launch normal single-player.
2. Wait at least `startup_delay_ms`.
3. Press `F12`.
4. Confirm overlay/help appears.
5. Confirm log exists:
   - `logs\codered_peer_companion.log`

Expected:

- No crash.
- Log shows registration success and heartbeat.

## Test B: Snapshot

1. Press `F6`.
2. Open `logs\codered_peer_companion.log`.

Expected:

- `snapshot player_valid=true`
- Player actor, coordinates, heading, health are logged.

## Test C: Adopt Actor 638

1. Stand near actor 638 / son / Jack test actor.
2. Aim/target the actor so `GET_TARGET_ACTOR` can see it.
3. Press `F8`.

Expected log sequence:

```text
ENTER adopt_nearest_638
ENTER adopt_actor_638
adopt_candidate source=GET_TARGET_ACTOR actor=... enum=638 distance=...
ENTER companion_apply_state
companion_apply_state ... faction_before=...
companion_apply_state faction_after=...
ENTER companion_squad_route
EXIT companion_squad_route SKIPPED squad_route_enabled=false
ENTER companion_fallback_follow
EXIT companion_fallback_follow OK
EXIT adopt_actor_638 OK
```

Expected behavior:

- Actor 638 should start following or at least stop immediately returning to hotspot fallback.
- If it does not follow, the log should identify whether the failure was target resolution, enum mismatch, distance, invalid actor, or task route.

## Test D: Guard / Wait

1. After successful adoption, press `F9`.

Expected:

- Log shows `guard_wait_638`.
- Actor should stop following or pause at current position.

## Test E: Regroup / Follow Again

1. Press `F10`.

Expected:

- Log shows `regroup_follow_638`.
- `TASK_FOLLOW_ACTOR` fallback runs again.

## Test F: Release / Dismiss

1. Press `Backspace`.

Expected:

- Log shows `despawn skipped destroy for adopted retail actor`.
- Actor 638 is not deleted or killed.
- Stored companion handle clears.

## Optional Test G: Task Priority Probe

Only after A-F do not crash:

1. Set:

```ini
task_priority_enabled=true
companion_follow_priority=1
```

2. Repeat C-E.

Purpose:

- Determine whether `TASK_PRIORITY_SET(companion, 1)` helps beat hotspot fallback.

Risk:

- SDK signature uses `Any`, so keep this isolated.

## Optional Test H: Squad Route Probe

Only after fallback follow works:

1. Set:

```ini
squad_route_enabled=true
```

2. Repeat C.

Purpose:

- Test whether `CREATE_SQUAD_IN_LAYOUT`, `SQUAD_JOIN`, and `SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION` wake the TR squad predicates.

Risk:

- `SQUAD_JOIN` and squad goal argument semantics are not proven. If this crashes or no-ops, turn `squad_route_enabled=false` again.

## What To Send Back

After a test, send:

- Last 100 lines of `logs\codered_peer_companion.log`
- Whether actor 638 was targetable
- Whether the log showed `enum=638`
- Whether fallback follow moved the actor
- Whether hotspot fallback still happened
- Whether enabling task priority changed behavior
- Whether enabling squad route crashed, no-oped, or worked
