param(
    [switch]$DryRun,
    [switch]$SwapIn,
    [string]$CodeRedRoot = "%RDR_GAME_DIR%\Code_RED",
    [string]$SourceRpf = "%RDR_GAME_DIR%\game\content.rpf",
    [string]$DropIn = ""
)

$ErrorActionPreference = "Stop"
Set-Location $CodeRedRoot
$env:PYTHONPATH = "."
$toolPath = Join-Path $CodeRedRoot "tools\codered_mp_freeroam_pass3_installer.py"
if (!(Test-Path $toolPath)) {
    Write-Host "Installer Python tool not found at: $toolPath"
    Write-Host "Copy codered_mp_freeroam_pass3_installer.py into Code_RED\tools first."
    exit 1
}
$argsList = @("-3", $toolPath, "--code-red", $CodeRedRoot, "--source-rpf", $SourceRpf)
if ($DropIn -ne "") { $argsList += @("--dropin", $DropIn) }
if ($DryRun) { $argsList += "--dry-run" }
if ($SwapIn) { $argsList += "--swap-in" }
py @argsList
