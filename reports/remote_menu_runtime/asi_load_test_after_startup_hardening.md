# Code RED Remote Menu ASI Load Test After Startup Hardening

Generated: 2026-05-23T23:03:41
Executable: `
D:\Games\Red Dead Redemption\PlayRDR.exe
`
Installed ASI SHA1: `3A306AC79E71B4F43D5C27D24688B37E00926486`

## Launch Result
```text
start_error=
launcher_started=True
launcher_exit_code=0
rdr_processes_alive_after_60s=False
cleanup_action=stopped_any_remaining_RDR_or_PlayRDR_processes
```

## Processes Alive Before Cleanup
```text
ProcessId Name    ExecutablePath                       CommandLine                            
--------- ----    --------------                       -----------                            
    25028 RDR.exe D:\Games\Red Dead Redemption\RDR.exe "D:\Games\Red Dead Redemption\RDR.exe"
```

## Event Viewer Check
```text
(no matching Application Error/Windows Error Reporting event found during ASI load smoke window)
```

## codered_remote_menu.log
```text
[2026-05-23 23:02:41] ASI attached: Code RED Remote Menu
[2026-05-23 23:02:41] Registration worker started
[2026-05-23 23:02:41] Config loaded: probe_only=1 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:02:41] ScriptHookRDR.dll found
[2026-05-23 23:02:41] Registration succeeded; Remote Menu hotkeys active after startup_delay_ms=30000
[2026-05-23 23:03:08] Config loaded: probe_only=1 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:03:08] Config reloaded before runtime-ready
[2026-05-23 23:03:11] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:12] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:13] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:14] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:15] Menu opened
[2026-05-23 23:03:15] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:16] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:17] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:18] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:19] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:20] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:21] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:22] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:23] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:24] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:25] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:26] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:27] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:28] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:29] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:30] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:31] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:32] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:33] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:34] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:35] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:36] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:37] Soul Stealer armed: press E near an NPC
[2026-05-23 23:03:37] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:38] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:39] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:40] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:03:41] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
```

## asiloader.log
```text
[23:2:41] Mod loader by kepmehz
[23:2:41] Loading mods in RDR directory
[23:2:41] Loaded CodeRED_Remote_Menu.asi
```

## ScriptHookRDR.log
```text
[23:2:41] [INIT] Initializing ScriptHook for Red Dead Redemption
[23:2:41] Build: Sat Jan 18 21:53:16 2025 Version: 1.5.2 MASTER
[23:2:50] [InputHook] Found window 'Red Dead Redemption', HWND: E20964
[23:2:50] [POOLS] Scanning all patterns...
[23:2:50] [POOLS] Scanned all patterns
[23:2:50] [THREADS] Scanning all patterns...
[23:2:50] [THREADS] Scanned all patterns
[23:2:50] [VARS] Scanning all patterns...
[23:2:50] [VARS] Scanned all patterns
[23:2:50] [INIT] Hooking functions...
[23:2:50] [HOOKS] Created hook rage::scrThread::Run
[23:2:50] [HOOKS] Created hook rage::scrThread::Reset
[23:2:50] [HOOKS] Created hook ConvertThreadToFiber
[23:2:50] [INIT] Finished hooking functions
[23:3:1] [DX12] Starting DX12 hook setup
[23:3:1] [SCRIPTS] Incrementing capacity of Stacks with size 1536 by 1
[23:3:1] [SCRIPTS] Starting TRAFFICDEBUGTHREAD thread for D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi with Id 26
```
