# Code RED Remote Menu Hotkey / Teleport / Probe Smoke Test

Generated: 2026-05-23T23:06:43
Executable: `
D:\Games\Red Dead Redemption\PlayRDR.exe
`
Installed ASI SHA1: `045ABBB808E13F905A52FF612B27091ED2E00C2A`

## Input Attempt
```text
app_activate=True
sent_keys=F7, Insert, F5, F6, F8, E, Backspace
errors=
```

## Runtime Result
```text
rdr_processes_alive_after_hotkeys=False
cleanup_action=stopped_any_remaining_RDR_or_PlayRDR_processes
```

## Processes Before Cleanup
```text
ProcessId Name    ExecutablePath                       CommandLine                            
--------- ----    --------------                       -----------                            
    16244 RDR.exe D:\Games\Red Dead Redemption\RDR.exe "D:\Games\Red Dead Redemption\RDR.exe"
```

## Event Viewer Check
```text
(no matching Application Error/Windows Error Reporting event found during hotkey smoke window)
```

## codered_remote_menu.log
```text
[2026-05-23 23:05:31] ASI attached: Code RED Remote Menu
[2026-05-23 23:05:31] Registration worker started
[2026-05-23 23:05:31] Config loaded: probe_only=1 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:05:31] ScriptHookRDR.dll found
[2026-05-23 23:05:31] Registration succeeded; Remote Menu hotkeys active after startup_delay_ms=30000
[2026-05-23 23:06:01] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:06:01] Config loaded: probe_only=1 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:06:03] Menu opened
[2026-05-23 23:06:11] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:06:17] Soul Stealer armed: press E near an NPC
[2026-05-23 23:06:21] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:06:26] Menu closed
[2026-05-23 23:06:27] Menu opened
[2026-05-23 23:06:28] Saved teleport slot 0: 370.42, 0.00, 103.40 heading=170.90
[2026-05-23 23:06:28] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:29] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:30] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:31] Soul Stealer armed: press E near an NPC
[2026-05-23 23:06:31] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:32] Soul Stealer ProbeOnly captured actor=3256 distance=1.45 pos=363.50,0.00,103.40
[2026-05-23 23:06:32] Ghost blip stub: name=Remote Player source=captured_actor pos=363.77,0.00,103.51 status=stub_only
[2026-05-23 23:06:33] Soul Stealer cancelled
[2026-05-23 23:06:33] Ghost blip stub: name=Remote Player source=captured_actor pos=363.46,0.00,103.71 status=stub_only
[2026-05-23 23:06:34] Ghost blip stub: name=Remote Player source=captured_actor pos=362.63,0.00,103.94 status=stub_only
[2026-05-23 23:06:35] Ghost blip stub: name=Remote Player source=captured_actor pos=361.50,0.00,104.21 status=stub_only
[2026-05-23 23:06:36] Ghost blip stub: name=Remote Player source=captured_actor pos=360.46,0.00,104.57 status=stub_only
[2026-05-23 23:06:37] Ghost blip stub: name=Remote Player source=captured_actor pos=359.48,0.00,105.01 status=stub_only
[2026-05-23 23:06:38] Ghost blip stub: name=Remote Player source=captured_actor pos=358.19,0.00,105.49 status=stub_only
[2026-05-23 23:06:39] Ghost blip stub: name=Remote Player source=captured_actor pos=356.55,0.00,106.18 status=stub_only
[2026-05-23 23:06:40] Ghost blip stub: name=Remote Player source=captured_actor pos=354.20,0.00,106.93 status=stub_only
[2026-05-23 23:06:41] Soul Stealer armed: press E near an NPC
[2026-05-23 23:06:41] Ghost blip stub: name=Remote Player source=captured_actor pos=351.89,0.00,107.67 status=stub_only
[2026-05-23 23:06:42] Ghost blip stub: name=Remote Player source=captured_actor pos=350.56,0.00,107.99 status=stub_only
```
