# Test Instructions

## Test A: config-only fix, no rebuild

1. Restore your current working `CodeRED_PeerCompanion.asi`.
2. Copy `dropin_config_only/data` into the RDR game folder beside `RDR.exe`.
3. Confirm this file exists:

```text
<RDR game folder>\data\codered\peer_companion.ini
```

4. Launch normal single-player.
5. Wait at least 15 seconds after player control.
6. Press F6 once. Confirm the overlay/log still works.
7. Press F8 once.
8. Look directly in front of the player, about 4 meters away.
9. Press F9 to despawn.

Check:

```text
<RDR game folder>\logs\codered_peer_companion.log
```

Useful lines:

```text
load_config ... companion_actor_enum=369
ENTER spawn_companion
EXIT spawn_companion OK actor=... enum=369 ...
```

If it says `CREATE_ACTOR_IN_LAYOUT returned invalid actor`, enum 369 is not spawnable in your runtime/context.
If it says spawn OK but nothing appears, rebuild the source patch so the visibility nudge loop can keep the clone in front of you.

## Test B: rebuilt source patch

Build with your existing Windows build bridge after replacing `CodeRED_PeerCompanion.cpp` with `source_patch/CodeRED_PeerCompanion.cpp`.

Then retest F8. The log should include:

```text
ENTER visibility_nudge
EXIT visibility_nudge OK reason=spawn_confirm ...
EXIT visibility_nudge OK reason=visibility_hold ...
```

If those appear and you still see nothing, the next problem is likely actor asset streaming or the native signature, not the spawn position.
