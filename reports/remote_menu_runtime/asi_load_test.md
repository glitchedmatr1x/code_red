# Code RED Remote Menu ASI Load Test

Generated: 2026-05-23T23:01:19
Executable: `
D:\Games\Red Dead Redemption\PlayRDR.exe
`
Installed ASI: `D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi`

## Launch Result
```text
start_error=
launcher_started=True
launcher_exit_code=0
rdr_processes_alive_after_50s=False
cleanup_action=stopped_any_remaining_RDR_or_PlayRDR_processes
```

## Processes Alive Before Cleanup
```text
(no RDR/PlayRDR processes alive at end of smoke window)
```

## Event Viewer Check
```text
TimeCreated  : 5/23/2026 11:01:02 PM
Id           : 1001
ProviderName : Windows Error Reporting
Message      : Fault bucket 1522932158592165819, type 5
               Event Name: BEX64
               Response: Not available
               Cab Id: 0
               
               Problem signature:
               P1: RDR.exe
               P2: 1.0.40.57107
               P3: 6711591d
               P4: CodeRED_Remote_Menu.asi
               P5: 0.0.0.0
               P6: 6a1293c5
               P7: 0000000000006281
               P8: c0000409
               P9: 0000000000000002
               P10: 
               
               Attached files:
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERE256.tmp.dmp
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERE361.tmp.WERInternalMetadata.xml
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERE3B0.tmp.xml
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERE3AE.tmp.csv
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERE3CE.tmp.txt
               
               These files may be available here:
               \\?\C:\ProgramData\Microsoft\Windows\WER\ReportArchive\AppCrash_RDR.exe_eb521b601d5c8ce36736e08947946687946b10e8_80ebd3a5_9adcf281-6eda-4a7f-910c-c9a05293552b
               
               Analysis symbol: 
               Rechecking for solution: 0
               Report Id: 191d9eff-68d8-4eb0-a156-6590ec74949c
               Report Status: 268435456
               Hashed bucket: 3fac5dd0aede2042f5228abab9e7a7bb
               Cab Guid: 0

TimeCreated  : 5/23/2026 11:01:01 PM
Id           : 1000
ProviderName : Application Error
Message      : Faulting application name: RDR.exe, version: 1.0.40.57107, time stamp: 0x6711591d
               Faulting module name: CodeRED_Remote_Menu.asi, version: 0.0.0.0, time stamp: 0x6a1293c5
               Exception code: 0xc0000409
               Fault offset: 0x0000000000006281
               Faulting process id: 0x6510
               Faulting application start time: 0x01dceb429f6364f0
               Faulting application path: D:\Games\Red Dead Redemption\RDR.exe
               Faulting module path: D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi
               Report Id: 191d9eff-68d8-4eb0-a156-6590ec74949c
               Faulting package full name: 
               Faulting package-relative application ID:
```

## codered_remote_menu.log
```text
[2026-05-23 23:00:28] ASI attached: Code RED Remote Menu
[2026-05-23 23:00:28] Registration worker started
[2026-05-23 23:00:28] Config loaded: probe_only=0 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:00:28] ScriptHookRDR.dll found
[2026-05-23 23:00:28] Registration succeeded; Remote Menu hotkeys active after startup_delay_ms=30000
[2026-05-23 23:00:52] Menu opened
[2026-05-23 23:00:52] Soul Stealer armed: press E near an NPC
[2026-05-23 23:00:55] Config loaded: probe_only=0 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:00:56] F6 skipped: startup delay/native bridge not ready
[2026-05-23 23:00:56] Soul Stealer armed: press E near an NPC
[2026-05-23 23:00:58] Ghost blip stub: name=Remote Player source=player pos=348.60,0.00,103.40 status=stub_only
```

## asiloader.log
```text
[23:0:28] Mod loader by kepmehz
[23:0:28] Loading mods in RDR directory
[23:0:28] Loaded CodeRED_Remote_Menu.asi
```

## ScriptHookRDR.log
```text
[23:0:28] [INIT] Initializing ScriptHook for Red Dead Redemption
[23:0:28] Build: Sat Jan 18 21:53:16 2025 Version: 1.5.2 MASTER
[23:0:37] [InputHook] Found window 'Red Dead Redemption', HWND: F003FC
[23:0:37] [POOLS] Scanning all patterns...
[23:0:37] [POOLS] Scanned all patterns
[23:0:37] [THREADS] Scanning all patterns...
[23:0:37] [THREADS] Scanned all patterns
[23:0:37] [VARS] Scanning all patterns...
[23:0:37] [VARS] Scanned all patterns
[23:0:37] [INIT] Hooking functions...
[23:0:37] [HOOKS] Created hook rage::scrThread::Run
[23:0:37] [HOOKS] Created hook rage::scrThread::Reset
[23:0:37] [HOOKS] Created hook ConvertThreadToFiber
[23:0:37] [INIT] Finished hooking functions
[23:0:47] [DX12] Starting DX12 hook setup
[23:0:47] [SCRIPTS] Incrementing capacity of Stacks with size 1536 by 1
[23:0:47] [SCRIPTS] Starting TRAFFICDEBUGTHREAD thread for D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi with Id 26
```
