@echo off
setlocal
set ROOT=%~dp0
set BRIDGE_DIR=%ROOT%Code_RED_Launch
set TARGET=PlayRDR.exe
if /I "%~1"=="play" set TARGET=PlayRDR.exe
if /I "%~1"=="direct" set TARGET=RDR.exe
set CODERED_BRIDGE_DIR=%BRIDGE_DIR%
set CODERED_ACTIVE_SESSION=%BRIDGE_DIR%\active_session.json
set CODERED_LAUNCH_PLAN=%BRIDGE_DIR%\launch_plan.json
set CODERED_HOOK_BOOTSTRAP=%ROOT%Code_RED_HookBridge\hook_bootstrap.json
set CODERED_HOOK_PACK_DIR=%ROOT%Code_RED_HookBridge
if exist "%BRIDGE_DIR%\codered_bridge_runtime.py" (
  where py >nul 2>&1 && start "Code RED Runtime Bridge" /min py -3 "%BRIDGE_DIR%\codered_bridge_runtime.py" "%BRIDGE_DIR%"
  if errorlevel 1 where python >nul 2>&1 && start "Code RED Runtime Bridge" /min python "%BRIDGE_DIR%\codered_bridge_runtime.py" "%BRIDGE_DIR%"
)
if exist "%ROOT%%TARGET%" (
  start "" "%ROOT%%TARGET%"
) else (
  echo Target executable not found: %ROOT%%TARGET%
)
endlocal
