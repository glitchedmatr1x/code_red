CODE RED TASK: Peer Companion Axis Visibility Fix

Problem:
The Peer Companion UI/ASI runs without crashes, but the user cannot see the spawned actor. The uploaded runtime_probe.log is from the old runtime/TES probe, not PeerCompanion. Inspect CodeRED_PeerCompanion logs/source instead.

Likely cause found from package smoke logs:
Player positions look like X/Z ground plane and Y height:
  player x=174.668 y=0 z=111.173
Current spawn math moves on X/Y and treats Z as height-ish, so the companion may be placed vertically/incorrectly depending on heading.

Required fix:
Use X/Z as horizontal/ground plane and Y as height.

Spawn target:
  dest.x = player.x + sin(heading) * spawn_distance
  dest.y = player.y + spawn_y_offset / spawn_z_offset config value
  dest.z = player.z + cos(heading) * spawn_distance

Apply this to:
- spawnCompanionNearPlayer
- CREATE_ACTOR_IN_LAYOUT position packing
- post-spawn TELEPORT_ACTOR
- teleportCompanionToPlayer
- any visibility nudge/reposition function

Keep safe defaults:
- no spawn on startup
- task_natives_enabled=false
- peer control off by default
- no MP calls
- no content.rpf/RDR.exe edits

Add/keep diagnostics:
- log player position, heading, target destination, created actor handle
- after spawn, run visibility_nudge once per second for 12 seconds
- each nudge teleports the companion to the fixed front-of-player position
- log ENTER/EXIT visibility_nudge

Deliver:
- rebuilt CodeRED_PeerCompanion.asi
- updated source
- updated config
- install package
- build log
- short test notes

Test:
1. Launch normal SP, wait 15 seconds.
2. F6 snapshot.
3. F8 spawn.
4. Confirm log has spawn_companion OK and visibility_nudge OK.
5. Confirm actor is visibly held in front of player.
6. If actor handle is valid but invisible, try companion_actor_enum=369 as alternate.
