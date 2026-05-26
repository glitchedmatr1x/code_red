# No winmm Control Launch Smoke
Started: 05/25/2026 22:47:29
LauncherProcessId: 25916
AnyRDRProcessAliveAfter130Seconds: False
Result: FAIL without winmm - no RDR process survived past 2 minutes.

## asiloader.log
[22:47:29] Mod loader by kepmehz
[22:47:29] Loading mods in RDR directory
[22:47:29] No .asi mods found, self loading ScriptHookRDR.dll
[22:47:29] Loaded ScriptHookRDR.dll

## ScriptHookRDR.log
[22:47:29] [INIT] Initializing ScriptHook for Red Dead Redemption
[22:47:29] Build: Sat Jan 18 21:53:16 2025 Version: 1.5.2 MASTER
[22:47:39] [InputHook] Found window 'Red Dead Redemption', HWND: F81464
[22:47:39] [POOLS] Scanning all patterns...
[22:47:39] [POOLS] Scanned all patterns
[22:47:39] [THREADS] Scanning all patterns...
[22:47:39] [THREADS] Scanned all patterns
[22:47:39] [VARS] Scanning all patterns...
[22:47:39] [VARS] Scanned all patterns
[22:47:39] [INIT] Hooking functions...
[22:47:39] [HOOKS] Created hook rage::scrThread::Run
[22:47:39] [HOOKS] Created hook rage::scrThread::Reset
[22:47:39] [HOOKS] Created hook ConvertThreadToFiber
[22:47:39] [INIT] Finished hooking functions
[22:47:50] [DX12] Starting DX12 hook setup
[22:47:50] [Scripts] No scripts registered, not adding any new thread stacks!
[22:48:27] [Scripts] Unloading all scripts...
[22:48:27] [Scripts] Unloaded all scripts
