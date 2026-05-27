# CodeRED Peer Companion Spawn-Near-Player Fix

This patch isolates the crash by removing the risky post-spawn teleport/visibility-nudge loop from the default path.

## Key change

The spawn point is calculated from the current player coordinates and uses the observed RDR coordinate convention:

```text
X/Z = ground plane
Y   = height
```

So F8 uses:

```text
spawn_x = player_x + sin(heading) * spawn_distance
spawn_y = player_y + spawn_z_offset
spawn_z = player_z + cos(heading) * spawn_distance
```

## Crash isolation

Defaults now keep these off:

```ini
task_natives_enabled=false
post_spawn_position_native_enabled=false
teleport_command_enabled=false
ai_companion_enabled=false
```

This means the first test only calls the spawn native, validates the handle, and logs the result. It does not force-position the actor every second.

## Test order

1. Rebuild the ASI with `source_patch/CodeRED_PeerCompanion.cpp`.
2. Install `dropin_config_safe`.
3. Launch normal single-player.
4. Wait for startup delay.
5. Press F6, then F8, then F6 again.
6. Check `logs/codered_peer_companion.log`.
7. If enum 111 is stable but invisible, try `dropin_config_alt_enum_369`.

Look for lines like:

```text
spawn_point player_xyz=... heading=... spawn_xyz=...
post_spawn_position_native skipped: disabled_by_config
EXIT spawn_companion OK actor=...
snapshot ... companion_xyz=...
```
