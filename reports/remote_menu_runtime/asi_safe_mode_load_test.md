# Code RED Remote Menu Safe-Mode Load Smoke

Generated: 2026-05-23T23:10:35
Installed ASI SHA1: `BD25B808A73EBD1F54A502EED3A3508271C6F8D3`

## Runtime Result
```text
rdr_processes_alive_after_50s=False
cleanup_action=stopped_any_remaining_RDR_or_PlayRDR_processes
```

## Processes Before Cleanup
```text
ProcessId Name    ExecutablePath                       CommandLine                            
--------- ----    --------------                       -----------                            
    14236 RDR.exe D:\Games\Red Dead Redemption\RDR.exe "D:\Games\Red Dead Redemption\RDR.exe"
```

## Event Viewer Check
```text
(no matching Application Error/Windows Error Reporting event found during safe-mode smoke window)
```

## codered_remote_menu.log
```text
[2026-05-23 23:09:44] ASI attached: Code RED Remote Menu
[2026-05-23 23:09:44] Registration worker started
[2026-05-23 23:09:44] Config loaded: probe_only=1 actor_scan=0 max_capture_distance=35.0 fallback=0 teleport_write=0 overlay=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:09:44] ScriptHookRDR.dll found
[2026-05-23 23:09:44] Registration succeeded; Remote Menu hotkeys active after startup_delay_ms=30000
[2026-05-23 23:10:14] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:10:15] Config loaded: probe_only=1 actor_scan=0 max_capture_distance=35.0 fallback=0 teleport_write=0 overlay=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:10:16] Soul Stealer armed: press E near an NPC
[2026-05-23 23:10:16] Menu opened
[2026-05-23 23:10:17] F6 skipped: teleport slot 0 is empty
[2026-05-23 23:10:18] Saved teleport slot 0: 338.72, 0.00, 111.01 heading=156.62
[2026-05-23 23:10:18] F6 blocked: teleport_write_enabled=false target=338.72, 0.00, 111.01 heading=156.62
[2026-05-23 23:10:18] Config loaded: probe_only=1 actor_scan=0 max_capture_distance=35.0 fallback=0 teleport_write=0 overlay=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:10:18] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:19] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:20] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:21] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:22] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:23] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:24] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:25] Soul Stealer blocked: actor_scan_enabled=false
[2026-05-23 23:10:25] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:26] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:27] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:28] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:29] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:30] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:31] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:32] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:33] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
[2026-05-23 23:10:34] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=338.72,0.00,111.01 status=stub_only
```

## Decision
Soul Stealer actor scan, teleport write, and overlay drawing are disabled by default after the user reported a crash/interference. This build is for safe load/log validation only.
