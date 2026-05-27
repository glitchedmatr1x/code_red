# Known Blockers

- Faction values are configurable but not fully mapped in this pass. Friendly,
  neutral, and hostile commands call `SET_ACTOR_FACTION` with config values and
  log the result path.
- Task natives are disabled by default because ScriptHook reported native
  errors for `TASK_FOLLOW_ACTOR` and `TASK_STAND_STILL` during live testing.
  This pass now prioritizes visible spawn plus overlay/log proof. Re-enable only
  with `task_natives_enabled=true` when testing task signatures.
- `guard_player` is conservative. With task natives disabled it gives the
  configured basic weapon and logs that follow is skipped.
- No blip or overhead name marker is enabled in this pass.
- No socket code runs inside the ASI. LAN command routing is external; the ASI
  reads the local JSON inbox only after F11 enables peer-control.
- No official multiplayer scripts, GameSpy, `net.EnterOnline`, WSC, SCXML, RPF,
  or EXE patches are involved.
