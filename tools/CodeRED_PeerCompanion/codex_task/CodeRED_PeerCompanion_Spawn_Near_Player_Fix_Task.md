CODE RED TASK: Peer Companion Spawn Near Player Crash Fix

Problem:
The UI/ASI loads and no longer crashes at startup, but F8 companion spawn either creates no visible actor or crashes after the latest visibility-nudge attempt.

Do not add new features.
Do not touch content.rpf, WSC, SCXML, RDR.exe, GameSpy, or multiplayer scripts.
Fix only the companion spawn placement and crash isolation.

Required changes:
1. Keep F8 spawn manual only.
2. Compute spawn point from the current player coordinates.
   Observed player coordinate logs look like:
      x=177.242 y=0.000 z=111.149
   so treat X/Z as ground plane and Y as height.
3. Spawn the actor near the player:
      spawn_x = player_x + sin(heading) * spawn_distance
      spawn_y = player_y + spawn_z_offset
      spawn_z = player_z + cos(heading) * spawn_distance
4. Pass that point to CREATE_ACTOR_IN_LAYOUT.
5. Do not call TELEPORT_ACTOR or any repeated visibility nudge after spawn by default.
   The nudge/teleport path is the likely crash source.
6. Add config gates:
      post_spawn_position_native_enabled=false
      teleport_command_enabled=false
      spawn_use_xz_ground_plane=true
7. Keep task natives disabled by default:
      task_natives_enabled=false
      ai_companion_enabled=false
8. Add logging before and after spawn:
      player_xyz
      heading
      calculated spawn_xyz
      actor enum
      actor handle
      whether post_spawn_position_native was skipped/called
9. Update F6 snapshot to log companion coordinates if the handle is valid.
10. Build and test with:
      companion_actor_enum=111 first
      then companion_actor_enum=369 if 111 does not visibly spawn.

Success:
- F8 logs player_xyz and spawn_xyz.
- spawn_xyz is within 3–4 meters of the player coordinates.
- Game does not crash for 2 minutes after F8.
- If actor is valid but still invisible, F6 must show companion_xyz so we can tell where it actually went.
