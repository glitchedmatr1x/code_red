param(
    [Parameter(Mandatory=$true)]
    [string]$ModDir,
    [string]$GameDir = "%RDR_GAME_DIR%\game",
    [switch]$DryRun,
    [switch]$SwapIn,
    [switch]$AllowAdd
)

$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tool = Join-Path $AppRoot "CodeRED_RPF_Patcher_Lite.py"

$ArgsList = @("-3", $Tool, "--mod-dir", $ModDir, "--game-dir", $GameDir)
if ($DryRun) { $ArgsList += "--dry-run" }
if ($SwapIn) { $ArgsList += "--swap-in" }
if ($AllowAdd) { $ArgsList += "--allow-add" }

py @ArgsList
