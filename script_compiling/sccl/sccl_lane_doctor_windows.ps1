<#
Code RED SC-CL lane doctor.

Read-only diagnostic for the active script-compiling lane.
It does not move, delete, or rewrite files.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\sccl_lane_doctor_windows.ps1
#>

param([string]$RepoRoot = ".")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$Project = Join-Path $Lane "projects\vehicle_menu_probe"
$ReportDir = Join-Path $Lane "output"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

function Exists($Path) { return [bool](Test-Path $Path) }
function ReadText($Path) {
    if (Test-Path $Path) { return Get-Content $Path -Raw -ErrorAction SilentlyContinue }
    return ""
}
function IsFakeHeader($Path) {
    $txt = ReadText $Path
    return ($txt -match "Minimal Code RED proof natives" -or $txt -match "source-proof shims")
}
function LooksRealHeader($Path) {
    $txt = ReadText $Path
    return (($txt -match "SC-CL's include library" -or $txt -match "_native") -and $txt -match "CREATE_ACTOR_IN_LAYOUT" -and $txt -notmatch "Minimal Code RED proof natives")
}

$compilerCandidates = @(
    (Join-Path $Lane "output\SC-CL.exe"),
    (Join-Path $RepoRoot "SC-CL-master\bin\SC-CL.exe"),
    (Join-Path $RepoRoot "SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\SC-CL.exe"),
    (Join-Path $Lane "obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe"),
    (Join-Path $RepoRoot "resources\SC-CL_DROP_HERE\SC-CL.exe")
)

$includeCandidates = @(
    (Join-Path $Project "include\RDR\natives32.h"),
    (Join-Path $Lane "include\RDR\natives32.h"),
    (Join-Path $RepoRoot "resources\SC-CL_bitbucket_source\bin\include\RDR\natives32.h"),
    (Join-Path $RepoRoot "SC-CL-master\bin\include\RDR\natives32.h")
)

$main = Join-Path $Project "src\main.c"
$validator = Join-Path $Project "scripts\validate_vehicle_menu_probe.py"

$mainText = ReadText $main
$items = [ordered]@{
    repo_root = $RepoRoot
    lane = $Lane
    project = $Project
    active_source_exists = Exists $main
    active_validator_exists = Exists $validator
    active_project_header_exists = Exists (Join-Path $Project "include\RDR\natives32.h")
    active_lane_header_exists = Exists (Join-Path $Lane "include\RDR\natives32.h")
    project_header_is_fake = IsFakeHeader (Join-Path $Project "include\RDR\natives32.h")
    lane_header_is_fake = IsFakeHeader (Join-Path $Lane "include\RDR\natives32.h")
    project_header_looks_real = LooksRealHeader (Join-Path $Project "include\RDR\natives32.h")
    lane_header_looks_real = LooksRealHeader (Join-Path $Lane "include\RDR\natives32.h")
    source_uses_loose_float_create_actor = ($mainText -match "CREATE_ACTOR_IN_LAYOUT\(g_codeRedLayout, \"CodeREDMenuVehicle\", actorModel, 0\.0f")
    source_uses_vector3_create_actor = ($mainText -match "CREATE_ACTOR_IN_LAYOUT\(g_codeRedLayout, \"CodeREDMenuVehicle\", actorModel, spawnPos, spawnRot\)")
    source_uses_real_print_subtitle_shape = ($mainText -match "_PRINT_SUBTITLE\(text, 3000\.0f, true, 1, 0, 0, 0, 0\)")
    compiler_candidates = @($compilerCandidates | ForEach-Object { [ordered]@{ path = $_; exists = Exists $_ } })
    include_candidates = @($includeCandidates | ForEach-Object { [ordered]@{ path = $_; exists = Exists $_; fake = IsFakeHeader $_; looks_real = LooksRealHeader $_ } })
}

$actions = @()
if (-not $items.project_header_looks_real -or $items.project_header_is_fake) {
    $actions += "Run: powershell -ExecutionPolicy Bypass -File script_compiling\\sccl\\promote_real_sccl_headers_windows.ps1"
}
if (-not ($compilerCandidates | Where-Object { Test-Path $_ })) {
    $actions += "Restore/build SC-CL.exe or place it under script_compiling\\sccl\\output\\SC-CL.exe"
}
if ($items.source_uses_loose_float_create_actor) {
    $actions += "Update main.c to use vector3 Position/Rotation for CREATE_ACTOR_IN_LAYOUT"
}
if ($actions.Count -eq 0) {
    $actions += "Run validator, then compile_vehicle_menu_probe_windows.bat"
}
$items.actions = $actions

$reportJson = Join-Path $ReportDir "SC_CL_LANE_DOCTOR_REPORT.json"
$items | ConvertTo-Json -Depth 10 | Set-Content -Path $reportJson -Encoding UTF8

Write-Host "# Code RED SC-CL Lane Doctor"
Write-Host "Repo:" $RepoRoot
Write-Host "Project header exists:" $items.active_project_header_exists
Write-Host "Project header fake:" $items.project_header_is_fake
Write-Host "Project header real-looking:" $items.project_header_looks_real
Write-Host "Source uses vector3 create actor:" $items.source_uses_vector3_create_actor
Write-Host "Source uses loose float create actor:" $items.source_uses_loose_float_create_actor
Write-Host "Compiler candidates:"
$items.compiler_candidates | ForEach-Object { Write-Host "  [$($_.exists)] $($_.path)" }
Write-Host "Actions:"
$actions | ForEach-Object { Write-Host "  - $_" }
Write-Host "Report:" $reportJson
