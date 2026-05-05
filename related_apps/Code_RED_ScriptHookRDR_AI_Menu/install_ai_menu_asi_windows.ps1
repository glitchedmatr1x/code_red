<#
Install/stage the built Code RED AI Menu .asi beside a Red Dead Redemption game executable.

This copies only:
- CodeRED_AI_Menu.asi
- CodeRED_AI_Menu.ini
- data/codered/*.csv and *.txt

It does not edit RPF archives.

Run from repo root, replacing GameRoot with your real game folder:
  powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_ai_menu_asi_windows.ps1 -GameRoot "D:\Games\Red Dead Redemption"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$GameRoot,
    [string]$RepoRoot = "."
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$GameRoot = (Resolve-Path $GameRoot).Path
$AppDir = Join-Path $RepoRoot "related_apps\Code_RED_ScriptHookRDR_AI_Menu"
$BuildAsi = Join-Path $AppDir "build\CodeRED_AI_Menu.asi"
$IniSource = Join-Path $AppDir "CodeRED_AI_Menu.ini"
$DataSource = Join-Path $RepoRoot "data\codered"
$DataDest = Join-Path $GameRoot "data\codered"
$InstallReport = Join-Path $AppDir "build\CodeRED_AI_Menu_install_report.json"

function Require-File($Path, $Label) {
    if (-not (Test-Path $Path)) { throw ("Missing {0}: {1}" -f $Label, $Path) }
}
function Require-Dir($Path, $Label) {
    if (-not (Test-Path $Path)) { throw ("Missing {0}: {1}" -f $Label, $Path) }
}
function Hash-File($Path) {
    $hash = Get-FileHash -Path $Path -Algorithm SHA1
    return [ordered]@{ path = $Path; length = (Get-Item $Path).Length; sha1 = $hash.Hash }
}

Require-File $BuildAsi "built AI menu ASI"
Require-Dir $DataSource "Code RED data/codered folder"

$gameExes = @(Get-ChildItem -Path $GameRoot -File -Filter "*.exe" -ErrorAction SilentlyContinue)
if ($gameExes.Count -eq 0) {
    Write-Warning "No .exe found directly in GameRoot. Confirm this is the folder beside the game executable."
}

$DestAsi = Join-Path $GameRoot "CodeRED_AI_Menu.asi"
Copy-Item -Path $BuildAsi -Destination $DestAsi -Force

if (Test-Path $IniSource) {
    Copy-Item -Path $IniSource -Destination (Join-Path $GameRoot "CodeRED_AI_Menu.ini") -Force
} else {
    $iniText = @"
[paths]
roster=data/codered/npc_roster.txt
actor_enum_map=data/codered/actor_enum_map.csv
behavior_actions=data/codered/ai_behavior_actions.csv
action_plan=scratch/codered_ai_action_plan.json
"@
    $iniText | Set-Content -Path (Join-Path $GameRoot "CodeRED_AI_Menu.ini") -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path $DataDest | Out-Null
Copy-Item -Path (Join-Path $DataSource "*") -Destination $DataDest -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $GameRoot "scratch") | Out-Null

$report = [ordered]@{
    installed = (Get-Date).ToString('s')
    game_root = $GameRoot
    dest_asi = Hash-File $DestAsi
    ini = Join-Path $GameRoot "CodeRED_AI_Menu.ini"
    data_dest = $DataDest
    game_exes = @($gameExes | ForEach-Object { $_.FullName })
    note = "Install/stage only. RPF archives were not modified."
}
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $InstallReport -Encoding UTF8

Write-Host "# Code RED AI Menu Install"
Write-Host "GameRoot:" $GameRoot
Write-Host "ASI:" $DestAsi
Write-Host "INI:" (Join-Path $GameRoot "CodeRED_AI_Menu.ini")
Write-Host "Data:" $DataDest
Write-Host "Report:" $InstallReport
Write-Host "Next: launch the game, open the Code RED AI menu, select ACTOR_VEHICLE_Car01, run Spawn Selected NPC."
