<#
Promote real SC-CL headers into the active Code RED SC-CL lane.

Why:
Some early Code RED proof folders used minimal shim headers that only proved symbol names.
Those shims are not valid compile headers for real SC-CL output.

This script copies the real SC-CL include library from a complete SC-CL source/bin tree into:
  script_compiling/sccl/include
  script_compiling/sccl/projects/vehicle_menu_probe/include

It preserves old fake headers under:
  script_compiling/sccl/obsolete/headers_<timestamp>

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\promote_real_sccl_headers_windows.ps1
#>

param(
    [string]$RepoRoot = ".",
    [string]$PreferredInclude = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$LaneInclude = Join-Path $Lane "include"
$ProjectInclude = Join-Path $Lane "projects\vehicle_menu_probe\include"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ObsoleteHeaders = Join-Path $Lane "obsolete\headers_$Stamp"

$candidates = @()
if ($PreferredInclude) { $candidates += $PreferredInclude }
$candidates += @(
    (Join-Path $RepoRoot "resources\SC-CL_bitbucket_source\bin\include"),
    (Join-Path $RepoRoot "SC-CL-master\bin\include"),
    (Join-Path $RepoRoot "SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\Include"),
    (Join-Path $Lane "obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\include")
)

function Test-RealInclude($Path) {
    $natives = Join-Path $Path "RDR\natives32.h"
    $consts = Join-Path $Path "RDR\consts32.h"
    if (-not (Test-Path $natives)) { return $false }
    if (-not (Test-Path $consts)) { return $false }
    $txt = Get-Content $natives -Raw -ErrorAction SilentlyContinue
    if ($txt -match "Minimal Code RED proof natives") { return $false }
    if ($txt -notmatch "SC-CL's include library" -and $txt -notmatch "_native") { return $false }
    if ($txt -notmatch "CREATE_ACTOR_IN_LAYOUT") { return $false }
    return $true
}

$source = $null
foreach ($candidate in $candidates) {
    if (-not $candidate) { continue }
    $resolved = Resolve-Path $candidate -ErrorAction SilentlyContinue
    if (-not $resolved) { continue }
    $candidatePath = $resolved.Path
    if (Test-RealInclude $candidatePath) {
        $source = $candidatePath
        break
    }
}

if (-not $source) {
    Write-Host "[CodeRED] Could not find real SC-CL include folder." -ForegroundColor Red
    Write-Host "[CodeRED] Checked:"
    $candidates | ForEach-Object { Write-Host "  $_" }
    exit 3
}

Write-Host "[CodeRED] Real SC-CL include source:" $source

New-Item -ItemType Directory -Force -Path $ObsoleteHeaders | Out-Null
if (Test-Path $LaneInclude) {
    Copy-Item -Path $LaneInclude -Destination (Join-Path $ObsoleteHeaders "lane_include") -Recurse -Force
}
if (Test-Path $ProjectInclude) {
    Copy-Item -Path $ProjectInclude -Destination (Join-Path $ObsoleteHeaders "project_include") -Recurse -Force
}

if (Test-Path $LaneInclude) { Remove-Item $LaneInclude -Recurse -Force }
if (Test-Path $ProjectInclude) { Remove-Item $ProjectInclude -Recurse -Force }
New-Item -ItemType Directory -Force -Path $LaneInclude | Out-Null
New-Item -ItemType Directory -Force -Path $ProjectInclude | Out-Null

Copy-Item -Path (Join-Path $source "*") -Destination $LaneInclude -Recurse -Force
Copy-Item -Path (Join-Path $source "*") -Destination $ProjectInclude -Recurse -Force

$report = [ordered]@{
    source = $source
    lane_include = $LaneInclude
    project_include = $ProjectInclude
    obsolete_backup = $ObsoleteHeaders
    promoted_native_header = (Join-Path $ProjectInclude "RDR\natives32.h")
}
$reportPath = Join-Path $Lane "output\SC_CL_HEADER_PROMOTION_REPORT.json"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
$report | ConvertTo-Json -Depth 5 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "[CodeRED] Promoted real SC-CL headers into active lane."
Write-Host "[CodeRED] Backup:" $ObsoleteHeaders
Write-Host "[CodeRED] Report:" $reportPath
Write-Host "[CodeRED] Next: py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py"
