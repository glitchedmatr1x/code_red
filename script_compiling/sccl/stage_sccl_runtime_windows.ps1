<#
Stage SC-CL.exe and nearby runtime files into the active Code RED SC-CL lane.

Why:
Exit -1073741515 / 0xC0000135 means Windows found SC-CL.exe but could not load a required DLL.
A lone drop-folder SC-CL.exe is often not enough; the DLLs beside the built EXE must travel with it.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1

Then compile:
  script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
#>

param(
    [string]$RepoRoot = ".",
    [string]$PreferredSource = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$SccLRoot = Join-Path $RepoRoot "script_compiling\sccl"
$Dest = Join-Path $SccLRoot "output"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

$candidates = @()
if ($PreferredSource) { $candidates += $PreferredSource }
$candidates += @(
    (Join-Path $RepoRoot "SC-CL-master\bin"),
    (Join-Path $RepoRoot "SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin"),
    (Join-Path $SccLRoot "obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1"),
    (Join-Path $RepoRoot "resources\SC-CL_DROP_HERE")
)

$source = $null
foreach ($candidate in $candidates) {
    if (-not $candidate) { continue }
    $candidatePath = Resolve-Path $candidate -ErrorAction SilentlyContinue
    if (-not $candidatePath) { continue }
    $candidatePath = $candidatePath.Path
    if (Test-Path (Join-Path $candidatePath "SC-CL.exe")) {
        $source = $candidatePath
        break
    }
}

if (-not $source) {
    Write-Host "[CodeRED] Could not find an SC-CL.exe source folder." -ForegroundColor Yellow
    Write-Host "[CodeRED] Checked:"
    $candidates | ForEach-Object { Write-Host "  $_" }
    exit 3
}

Write-Host "[CodeRED] Staging SC-CL runtime from:" $source
Write-Host "[CodeRED] Destination:" $Dest

$patterns = @("SC-CL.exe", "*.dll", "*.pdb", "*.json", "*.toml", "*.ini", "*.txt")
$copied = @()
foreach ($pattern in $patterns) {
    Get-ChildItem -Path $source -Filter $pattern -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination (Join-Path $Dest $_.Name) -Force
        $copied += $_.Name
    }
}

if (-not (Test-Path (Join-Path $Dest "SC-CL.exe"))) {
    Write-Host "[CodeRED] Failed to stage SC-CL.exe." -ForegroundColor Red
    exit 4
}

$report = [ordered]@{
    source = $source
    destination = $Dest
    copied = $copied | Sort-Object -Unique
    staged_sccl = (Join-Path $Dest "SC-CL.exe")
    note = "If compile still exits -1073741515, install/repair Microsoft Visual C++ Redistributable 2015-2022 x64 or copy missing LLVM/clang runtime DLLs beside SC-CL.exe."
}

$reportPath = Join-Path $SccLRoot "output\SC_CL_RUNTIME_STAGE_REPORT.json"
$report | ConvertTo-Json -Depth 5 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "[CodeRED] Staged SC-CL.exe to:" (Join-Path $Dest "SC-CL.exe")
Write-Host "[CodeRED] Copied files:"
($report.copied) | ForEach-Object { Write-Host "  $_" }
Write-Host "[CodeRED] Report:" $reportPath
