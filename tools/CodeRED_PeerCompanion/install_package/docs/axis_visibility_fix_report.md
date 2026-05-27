# CodeRED Peer Companion Axis/Visibility Fix

The uploaded `runtime_probe.log` is from the older TES/runtime probe, not the current peer-companion ASI. It does not contain companion spawn entries.

The included `CodeRED_PeerCompanion.zip` smoke logs still show the useful clue:

- Player snapshot example: `x=174.668 y=0 z=111.173`
- Spawned companion example: `x=177.11 y=0.535838 z=111.523`

That means the ASI is treating the wrong axis as the forward ground-plane axis. In observed RDR PC positions, **X/Z are ground-plane coordinates and Y is height**. The current source moves on X/Y and only offsets Z slightly. Depending on heading, the clone can be placed above/below/inside/near the player instead of visibly in front.

This patch changes companion placement to:

```cpp
x = player.x + sin(heading) * distance
y = player.y + height_offset
z = player.z + cos(heading) * distance
```

It also keeps the companion in front of the player once per second for 12 seconds after spawn so the user can visually confirm it.

## What changed

- Added `companionPointInFront()` helper using X/Z ground plane and Y height.
- Changed `CREATE_ACTOR_IN_LAYOUT` placement packing to use X/Z plus vertical Y.
- Changed post-spawn `TELEPORT_ACTOR` destination to X/Z ground plane and Y height.
- Changed `teleport_to_player` command to use the same fixed placement.
- Added a 12-second `visibility_nudge` loop after spawn.

## Test order

1. Rebuild the ASI from `source_patch/CodeRED_PeerCompanion.cpp`.
2. Install the rebuilt ASI beside `RDR.exe`.
3. Use `dropin_config_safe_111` first.
4. Launch normal single-player and wait past startup delay.
5. Press `F6`, then `F8`.
6. Watch directly in front of the player. The clone should be held there for 12 seconds.
7. Check `logs/codered_peer_companion.log` for `visibility_nudge` entries.
8. If actor handle is valid but still not visible, test `dropin_config_alt_369`.

## Need from user if still invisible

Send:

```text
logs/codered_peer_companion.log
data/codered/link/host_status.json
```

Do not send the old `runtime_probe.log` for this issue; it belongs to the previous sector probe ASI.
