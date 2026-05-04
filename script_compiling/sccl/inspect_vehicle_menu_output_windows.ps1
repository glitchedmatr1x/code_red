<#
Inspect Code RED SC-CL vehicle menu compile outputs.

Purpose:
SC-CL can return exit 0 while writing output somewhere unexpected when output paths are malformed.
This inspector searches the active output area for real .xsc/.sco artifacts and records hashes.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\inspect_vehicle_menu_output_windows.ps1
#>

param([string]$RepoRoot = ".")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$OutRoot = Join-Path $Lane "output"
$ProbeOut = Join-Path $OutRoot "vehicle_menu_probe"
New-Item -ItemType Directory -Force -Path $ProbeOut | Out-Null

$files = @()
$files += Get-ChildItem -Path $OutRoot -Recurse -File -Filter "*.xsc" -ErrorAction SilentlyContinue
$files += Get-ChildItem -Path $OutRoot -Recurse -File -Filter "*.sco" -ErrorAction SilentlyContinue
$files = @($files | Sort-Object FullName -Unique)

$rows = @()
foreach ($f in $files) {
    $hash = Get-FileHash -Path $f.FullName -Algorithm SHA1
    $rows += [ordered]@{
        full_name = $f.FullName
        relative_path = $f.FullName.Substring($RepoRoot.Length).TrimStart('\')
        length = $f.Length
        last_write_time = $f.LastWriteTime.ToString('s')
        sha1 = $hash.Hash
    }
}

$report = [ordered]@{
    repo_root = $RepoRoot
    output_root = $OutRoot
    expected_folder = $ProbeOut
    artifact_count = $rows.Count
    artifacts = $rows
    note = "Only .xsc and .sco files are counted as compiled artifacts. JSON/MD reports are intentionally excluded."
}

$jsonPath = Join-Path $OutRoot "vehicle_menu_probe_output_report.json"
$mdPath = Join-Path $OutRoot "vehicle_menu_probe_output_report.md"
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$Text = "") { [void]$lines.Add($Text) }

Add-Line "# Code RED Vehicle Menu Probe Output Report"
Add-Line ""
Add-Line ("Output root: {0}" -f $OutRoot)
Add-Line ("Expected folder: {0}" -f $ProbeOut)
Add-Line ("Artifact count: {0}" -f $rows.Count)
Add-Line ""
foreach ($row in $rows) {
    Add-Line ("## {0}" -f $row.relative_path)
    Add-Line ("- length: {0}" -f $row.length)
    Add-Line ("- sha1: {0}" -f $row.sha1)
    Add-Line ("- last write: {0}" -f $row.last_write_time)
    Add-Line ""
}
if ($rows.Count -eq 0) {
    Add-Line "No .xsc or .sco artifacts were found under the SC-CL output root."
    Add-Line ""
    Add-Line "Try rerunning compile after confirming the batch passes a doubled trailing slash to -out-dir."
}
$lines -join "`n" | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "# Code RED Vehicle Menu Probe Output Report"
Write-Host "Output root:" $OutRoot
Write-Host "Artifact count:" $rows.Count
foreach ($row in $rows) {
    Write-Host ("  {0}  length={1} sha1={2}" -f $row.relative_path, $row.length, $row.sha1)
}
Write-Host "Report:" $mdPath
Write-Host "JSON:" $jsonPath
