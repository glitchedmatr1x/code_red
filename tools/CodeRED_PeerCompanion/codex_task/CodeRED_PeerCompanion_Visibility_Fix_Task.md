CODE RED TASK: Peer Companion Visibility Fix Pass

The user sees the overlay/UI and there are no crashes, but no actor appears after F8 spawn.
Do not pivot back to MP/WSC/RPF. Fix only the companion visibility/spawn path.

Do not edit content.rpf.
Do not edit RDR.exe.
Do not launch MP scripts.
Do not enable task natives by default.
Do not add hostile/combat behavior in this pass.

Start from the uploaded CodeRED_PeerCompanion project.
Apply the included source patch, then build a new ASI.

Changes required:
1. Default companion actor enum should be 369, not 111.
2. Spawn in a more visible spot:
   spawn_distance=4.0
   spawn_z_offset=1.0
3. Add config keys:
   visibility_nudge_enabled=true
   visibility_hold_ms=12000
   visibility_nudge_ms=750
4. After F8 spawn, nudge/teleport the companion in front of the player immediately.
5. For the first visibility_hold_ms after spawn, repeat the nudge every visibility_nudge_ms.
6. Log:
   ENTER visibility_nudge
   EXIT visibility_nudge OK reason=spawn_confirm actor=... x=... y=... z=...
   EXIT visibility_nudge OK reason=visibility_hold actor=... x=... y=... z=...
7. Overlay should include current companion enum.
8. Load config log should include companion_actor_enum, spawn_distance, spawn_z_offset, and visibility_nudge_enabled.

Validation:
- Build passes.
- ASI-only launch still shows overlay.
- F6 snapshot still works.
- F8 produces log line `EXIT spawn_companion OK actor=... enum=369`.
- F8 also produces visibility_nudge logs.
- F9 despawns safely.
- No crash after 5 minutes idle.

If F8 says actor handle valid but the actor remains invisible after visibility nudge, do not guess. Next diagnostic pass should prove actor streaming/model visibility:
- try one known trainer-safe actor enum list one at a time
- add a visible blip/name marker if a proven native is available
- inspect whether STREAMING_REQUEST_ACTOR / STREAMING_IS_ACTOR_LOADED native hashes are mapped before creating the actor
