# Companion Controller 638 Spawn Crash Recovery Test Plan

Install only the package contents from:

```text
D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\install_package
```

Expected installed files beside `RDR.exe`:

```text
CodeRED_PeerCompanion.asi
data\codered\peer_companion.ini
```

Do not stack this with Silent Virtues, JediJosh, old Remote Menu, old PeerCompanion builds, or other trainer ASIs for this test.

## Baseline INI

Use the included INI first:

```ini
spawn_actor_enum=638
spawn_use_xz_ground_plane=false
post_spawn_position_native_enabled=false
teleport_command_enabled=false
set_companion_faction_enabled=true
set_companion_flag_enabled=true
fallback_follow_enabled=true
task_priority_enabled=false
squad_route_enabled=false
give_weapon_enabled=false
clear_weapons_enabled=false
```

## Test Order

1. Launch normal single-player.
2. Wait at least 15 seconds.
3. Press `F12`.
4. Press `F6`.
5. Press `F7` once.
6. Do not press other keys for 30 seconds.
7. Press `F6` again.
8. If actor 638 is visible, press `F10` to regroup/follow.
9. Press `F9` to guard/wait.
10. Press `Backspace` to release/destroy only the Code RED-owned spawned actor.

## Expected F7 Log

```text
[PeerCompanion] F7 spawn/adopt requested
spawn_point ... xz_ground_plane=false coordinate_mode=sdk_xy_ground_z_height
spawn_stage CREATE_ACTOR_IN_LAYOUT call reached enum=638
spawn_stage create_actor_return=<positive handle>
spawn_stage actual_actor_xyz=...
distance_to_player=...
distance_to_requested=...
stage_c SET_ACTOR_FACTION call reached
stage_c SET_ACTOR_IS_COMPANION call reached
stage_d TASK_FOLLOW_ACTOR call reached
EXIT spawn_companion OK spawned_and_adopted
```

## If F7 Still Does Not Show Actor

Send back the last 120 lines from:

```text
D:\Games\Red Dead Redemption\logs\codered_peer_companion.log
```

The most important lines are:

```text
load_config
spawn_point
create_actor_return
actual_actor_xyz
distance_to_player
distance_to_requested
stage_c_set_actor_is_companion
stage_d_task_follow_actor
```

If `distance_to_requested` is large, placement is wrong. If the handle is invalid, streaming/create failed. If `SET_ACTOR_IS_COMPANION` or `TASK_FOLLOW_ACTOR` logs an exception, turn off only that INI toggle and retest.

## Alternate Coordinate Probe

Only if SDK mode returns a valid actor handle but the actual actor position is still wrong, set:

```ini
spawn_use_xz_ground_plane=true
```

Retest F7 once and compare `actual_actor_xyz` / `distance_to_player`.

## Squad/Vehicle/Turret Next Step

Do not enable these until basic spawn/follow is visible:

```ini
squad_route_enabled=true
task_priority_enabled=true
```

Driving and turret work should be separate passes. The SDK exposes `TASK_MOUNT`, `TASK_USE_TURRET`, and `TASK_USE_TURRET_AGAINST_*`, but their `Any` argument meanings need donor WSC/TR or trainer proof before enabling them in the default path.
