# Code RED Remote Menu 10-Second Crash Diagnostic Report

Status: diagnostic build installed.

Build outputs:
- Updated ASI: `D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi`
- Build ASI: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\build\CodeRED_Remote_Menu.asi`
- Diagnostic ASI copy: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_Remote_Menu\build\CodeRED_Remote_Menu_diag.asi`
- SHA1: `7E481CD58545C8BFB1AAAD9477345F0945B21881`
- Build result: `cl.exe exit: 0`

What changed:
- Added kill-switches for local state write, remote state read, puppet sync, ghost/blip update, periodic logging, stale checks, and actor handle polling.
- Added staged startup: at least 15 seconds of log/heartbeat only before native/file bridge work can begin.
- Remote state read and puppet sync no longer run automatically. They require config enablement and manual hotkey arming.
- Added `ENTER <stage>` / `EXIT <stage> OK` logging around timed stages.
- Added heartbeat logging every 5 seconds with enabled flags.

Default enabled state:

```ini
[diagnostics]
local_state_write_enabled=true
remote_state_read_enabled=false
puppet_sync_enabled=false
ghost_blip_enabled=false
periodic_log_enabled=true
stale_check_enabled=false
actor_handle_poll_enabled=false

[link]
write_local_state=true
read_remote_state=false
puppet_sync_enabled=false

[runtime]
startup_delay_ms=15000
```

Manual hotkeys:
- `F11`: arm/disarm remote JSON reads, only if `remote_state_read_enabled=true`.
- `F12`: arm/disarm puppet sync, only if `puppet_sync_enabled=true` and `actor_handle_poll_enabled=true`.
- `F3`: arm/disarm ghost/blip update, only if `ghost_blip_enabled=true`.

Test order:
1. Run with current defaults. Expected: heartbeat logs immediately, then local state write starts after 15 seconds.
2. Do not run `CodeRED_Link_TestClient.py` until local state write survives at least 60 seconds.
3. If it crashes, inspect `logs\codered_remote_menu.log`.
4. The last `ENTER stage_name` without matching `EXIT stage_name OK` is the suspected crash stage.
5. Only after local write is stable, set `remote_state_read_enabled=true` and `read_remote_state=true`, reload config, then press `F11`.
6. Only after remote read is stable, enable `puppet_sync_enabled=true`, `actor_handle_poll_enabled=true`, `link.puppet_sync_enabled=true`, spawn with `F9`, then press `F12`.
7. Test ghost/blip last.

Previous log evidence:
- Older builds registered cleanly and reached the delayed native probe.
- The old logs did not have stage markers, so this report cannot name the exact crash stage yet.
- The likely area is the first post-delay timed native/file bridge stage after registration.

Last-100-lines snapshot:
- Saved to `D:\Games\Red Dead Redemption\Code_RED\reports\remote_menu_runtime\codered_remote_menu_last100.log`
