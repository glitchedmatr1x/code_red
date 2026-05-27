# CodeRED Peer Companion Visibility Fix Pass

Problem reported:
- UI/overlay appears.
- No crash.
- F8 spawn path does not show a visible actor.

Most likely causes from the uploaded package:
1. The installed config uses `companion_actor_enum=111`, while the prior smoke report logged a successful spawn with enum `369`.
2. The ASI reports actor-handle success but has no visible blip/name marker, so if the actor spawns slightly behind/under/away from camera, the user gets no obvious confirmation.
3. Task/follow natives are disabled by default, so the actor may not be held in a visible position after spawn.

Immediate config-only fix:
- Switch default companion actor enum to `369`.
- Spawn farther and higher: `spawn_distance=4.0`, `spawn_z_offset=1.0`.
- Keep task natives disabled for safety.

Source patch for next rebuilt ASI:
- Adds `visibility_nudge_enabled`, `visibility_hold_ms`, and `visibility_nudge_ms` config keys.
- After spawn, and for the first 12 seconds, nudges the companion in front of the player every 750ms.
- Logs `visibility_nudge` ENTER/EXIT stages so we can tell whether the actor is being repositioned.
- Shows the companion enum in the overlay.
- Logs important config values at load.

This package does not include a rebuilt ASI because the sandbox does not have the Windows/MSVC toolchain needed to compile ScriptHookRDR ASIs.
