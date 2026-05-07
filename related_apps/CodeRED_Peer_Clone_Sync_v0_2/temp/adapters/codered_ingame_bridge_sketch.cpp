// Code RED Peer Clone Sync - in-game bridge sketch
// This is NOT build-ready. It documents the minimum ScriptHook/plugin side.
//
// Local player loop:
//   GET_PLAYER_ACTOR(0)
//   GET_POSITION(player, &pos)
//   read heading/action
//   send JSON state to relay
//
// Remote player loop:
//   receive JSON states
//   if clone missing, CREATE_ACTOR_IN_LAYOUT with safe actor enum
//   TELEPORT_ACTOR(clone, &remote_pos, true, true, true)
//   SET_ACTOR_HEADING(clone, remote_heading, true)
//
// First build target:
//   visible clone position sync only.
//   No vehicles, no combat, no ragdolls, no mission state.
