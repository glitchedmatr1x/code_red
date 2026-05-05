<#
Stage the latest Code RED camp-car proof artifacts into one local kit folder.

This script only copies files from script_compiling/sccl/output into a new
script_compiling/sccl/output/playtest_kits folder. It does not modify game files,
archives, extracted RPF folders, or any external mod folder.

Run from repo root after:
  script_compiling\sccl\compile_camp_car_probe_all_windows.bat
  script_compiling\sccl\export_camp_car_wsc_candidate_windows.bat
#>

param([string]$RepoRoot = ".")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$OutRoot = Join-Path $Lane "output"
$Xsc = Join-Path $OutRoot "camp_car_probe\camp_car_probe.xsc"
$Sco = Join-Path $OutRoot "camp_car_probe_sco\camp_car_probe.sco"
$Wsc = Join-Path $OutRoot "camp_car_probe_wsc\camp_car_probe.wsc"
$WscReport = Join-Path $OutRoot "camp_car_probe_wsc\camp_car_probe_wsc_candidate_report.json"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$KitRoot = Join-Path $OutRoot "playtest_kits\camp_car_artifacts_$Stamp"
$ZipPath = "$KitRoot.zip"

function Require-File($Path, $Label) {
    if (-not (Test-Path $Path)) {
        throw ("Missing {0}: {1}" -f $Label, $Path)
    }
}

function Hash-File($Path) {
    $hash = Get-FileHash -Path $Path -Algorithm SHA1
    return [ordered]@{
        path = $Path
        relative_path = $Path.Substring($RepoRoot.Length).TrimStart('\\')
        length = (Get-Item $Path).Length
        sha1 = $hash.Hash
    }
}

Require-File $Xsc "camp car XSC"
Require-File $Sco "camp car SCO"
Require-File $Wsc "camp car WSC candidate"

New-Item -ItemType Directory -Force -Path $KitRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $KitRoot "artifacts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $KitRoot "reports") | Out-Null

Copy-Item -Path $Xsc -Destination (Join-Path $KitRoot "artifacts\camp_car_probe.xsc") -Force
Copy-Item -Path $Sco -Destination (Join-Path $KitRoot "artifacts\camp_car_probe.sco") -Force
Copy-Item -Path $Wsc -Destination (Join-Path $KitRoot "artifacts\camp_car_probe.wsc") -Force
if (Test-Path $WscReport) {
    Copy-Item -Path $WscReport -Destination (Join-Path $KitRoot "reports\camp_car_probe_wsc_candidate_report.json") -Force
}

$artifactRows = @(
    Hash-File $Xsc
    Hash-File $Sco
    Hash-File $Wsc
)

$manifest = [ordered]@{
    package = "camp_car_artifacts"
    created = (Get-Date).ToString('s')
    repo_root = $RepoRoot
    kit_root = $KitRoot
    artifacts = $artifactRows
    controls = @(
        "F5 = spawn ACTOR_VEHICLE_Car01 near player/camp",
        "F6 = put player in spawned car",
        "F7 = re-apply vehicle tuning",
        "F8 = delete probe car",
        "F9 = delete/re-spawn farther away",
        "F10 = show help"
    )
    boundary = "Local staging only. This script does not modify game files, archives, extracted RPF folders, or external mod folders."
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $KitRoot "ARTIFACT_MANIFEST.json") -Encoding UTF8

$readme = @"
# Code RED Camp Car Artifacts

This folder contains the latest staged camp-car proof artifacts.

## Files

~~~text
artifacts/camp_car_probe.xsc
artifacts/camp_car_probe.sco
artifacts/camp_car_probe.wsc
reports/camp_car_probe_wsc_candidate_report.json
ARTIFACT_MANIFEST.json
~~~

## In-game controls if loaded by a compatible script path

~~~text
F5 = spawn ACTOR_VEHICLE_Car01 near player/camp
F6 = put player in spawned car
F7 = re-apply vehicle tuning
F8 = delete probe car
F9 = delete/re-spawn farther away
F10 = show help
~~~

## Boundary

This staging script only copies proof artifacts into this local kit folder.
It does not modify game files, archives, extracted RPF folders, or external mod folders.
"@
$readme | Set-Content -Path (Join-Path $KitRoot "README_ARTIFACTS.md") -Encoding UTF8

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $KitRoot "*") -DestinationPath $ZipPath -Force
$zipHash = Get-FileHash -Path $ZipPath -Algorithm SHA1

Write-Host "# Code RED Camp Car Artifact Kit"
Write-Host "Kit:" $KitRoot
Write-Host "ZIP:" $ZipPath
Write-Host "ZIP SHA1:" $zipHash.Hash
foreach ($artifact in $artifactRows) {
    Write-Host ("Artifact: {0} length={1} sha1={2}" -f $artifact.relative_path, $artifact.length, $artifact.sha1)
}
Write-Host "Boundary: local staging only. No game/archive files modified."
