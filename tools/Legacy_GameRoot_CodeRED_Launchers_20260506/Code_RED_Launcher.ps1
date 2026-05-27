$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BridgeDir = Join-Path $Root 'Code_RED_Launch'
$Target = 'PlayRDR.exe'
if ($args.Count -gt 0 -and $args[0] -eq 'play') { $Target = 'PlayRDR.exe' }
if ($args.Count -gt 0 -and $args[0] -eq 'direct') { $Target = 'RDR.exe' }
$env:CODERED_BRIDGE_DIR = $BridgeDir
$env:CODERED_ACTIVE_SESSION = Join-Path $BridgeDir 'active_session.json'
$env:CODERED_LAUNCH_PLAN = Join-Path $BridgeDir 'launch_plan.json'
$env:CODERED_HOOK_BOOTSTRAP = Join-Path (Join-Path $Root 'Code_RED_HookBridge') 'hook_bootstrap.json'
$env:CODERED_HOOK_PACK_DIR = Join-Path $Root 'Code_RED_HookBridge'
$runtimeScript = Join-Path $BridgeDir 'codered_bridge_runtime.py'
if (Test-Path $runtimeScript) {
  Start-Process -WindowStyle Hidden -FilePath 'py' -ArgumentList @('-3', $runtimeScript, $BridgeDir) -ErrorAction SilentlyContinue
}
$targetPath = Join-Path $Root $Target
if (Test-Path $targetPath) {
  Start-Process -FilePath $targetPath
} else {
  Write-Host "Target executable not found: $targetPath"
}
