# Peer Companion Link Pass 1 Report

Built outputs:

- `build/CodeRED_PeerCompanion.asi`
- `CodeRED_Peer_App.py`
- `CodeRED_Link_Server.py`
- `data/codered/peer_companion.ini`
- `install_package/`

Final installed ASI SHA1:

`C5B6348278BB7B8DDCF12BD838206FBDC22B7E7A`

Validation completed:

- ASI compiled with Visual Studio 2022 C++ toolchain.
- Python files passed `py_compile`.
- Local relay accepted a `spawn_companion` command and wrote
  `data/codered/link/peer_command_inbox.json` in a test root.
- Initial in-game ASI-only smoke exposed an unsafe startup native read and
  crashed at 10 seconds. The startup native read is now gated behind the
  15-second startup delay.
- Follow-up in-game ASI-only smoke no longer hit the startup crash. It resolved
  the player actor and spawned a companion actor through F8 before the game
  closed with exit code `0` at 55 seconds. Treat this as functional proof of the
  native path, not as the 10-minute stability pass.
- User test did not show the clone and another key produced a native error box.
  The latest build adds a top-left debug overlay, switches default companion
  enum to `111` (`ACTOR_CAUCASIAN_MALE_Farmer01`), and disables task/follow/idle
  natives by default because ScriptHook reported errors for `TASK_FOLLOW_ACTOR`
  and `TASK_STAND_STILL`.
- Final installed smoke showed `CodeRED_PeerCompanion.asi` loading without
  ScriptHook native error lines. It was stopped by the test harness after the
  process remained running long enough for the smoke window.
- Spawn-fix build now uses the Code RED AI Menu `spawnSelectedNpc()` convention
  exactly for `CREATE_ACTOR_IN_LAYOUT` and disables all post-spawn action
  natives by default. Test log confirmed `actor_enum=369`,
  `using_spawn_method=CodeRED_AI_Menu::spawnSelectedNpc`,
  `create_actor_return=2880`, and `is_actor_valid_after_create=true`.

Runtime not forced in this report:

- The install package is ready for the original Red Dead Redemption PC folder.
- First in-game test should be ASI-only, with other trainers disabled, then F6
  snapshot before any spawn command.
