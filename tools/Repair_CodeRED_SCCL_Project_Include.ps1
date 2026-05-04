<#
Repair Code RED SC-CL project include layout.

Why this exists:
The first SC-CL lane sorter copied headers to:
  script_compiling/sccl/include

The existing validator expects headers at:
  script_compiling/sccl/projects/vehicle_menu_probe/include

This repair copies the active include folder into the project-local include folder.
It does not delete or move source files.

Run from the Code_RED repo root:
  powershell -ExecutionPolicy Bypass -File tools\Repair_CodeRED_SCCL_Project_Include.ps1
#>

param([string]$RepoRoot = ".")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path

$from = Join-Path $RepoRoot "script_compiling\sccl\include"
$to = Join-Path $RepoRoot "script_compiling\sccl\projects\vehicle_menu_probe\include"

if (-not (Test-Path $from)) {
    throw "Missing active include folder: $from"
}

New-Item -ItemType Directory -Force -Path $to | Out-Null
Copy-Item -Path (Join-Path $from "*") -Destination $to -Recurse -Force

Write-Host "Copied SC-CL active include folder into project-local include folder."
Write-Host "From: $from"
Write-Host "To:   $to"
Write-Host ""
Write-Host "Next: py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py"
