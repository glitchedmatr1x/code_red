<#
Inspect Code RED SC-CL camp car probe compile outputs.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\inspect_camp_car_output_windows.ps1
#>

param([string]$RepoRoot = ".")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$OutRoot = Join-Path $Lane "output"
$ProbeOut = Join-Path $OutRoot "camp_car_probe"
New-Item -ItemType Directory -Force -Path $ProbeOut | Out-Null

$files = @()
$files += Get-ChildItem -Path $OutRoot -Recurse -File -Filter "camp_car_probe*.xsc" -ErrorAction SilentlyContinue
$files += Get-ChildItem -Path $OutRoot -Recurse -File -Filter "camp_car_probe*.sco" -ErrorAction SilentlyContinue
$files = @($files | Sort-Object FullName -Unique)

$rows = @()
foreach ($f in $files) {
    $hash = Get-FileHash -Path $f.FullName -Algorithm SHA1
    $rows += [ordered]@{
        full_name = $f.FullName
        relative_path = $f.FullName.Substring($RepoRoot.Length).TrimStart('\\')
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
    boundary = "Runtime proof only. Not installed/imported into the game."
}

$jsonPath = Join-Path $OutRoot "camp_car_probe_output_report.json"
$mdPath = Join-Path $OutRoot "camp_car_probe_output_report.md"
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$Text = "") { [void]$lines.Add($Text) }

Add-Line "# Code RED Camp Car Probe Output Report"
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
    Add-Line "No camp_car_probe .xsc or .sco artifacts were found."
}
$lines -join "`n" | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "# Code RED Camp Car Probe Output Report"
Write-Host "Output root:" $OutRoot
Write-Host "Artifact count:" $rows.Count
foreach ($row in $rows) {
    Write-Host ("  {0}  length={1} sha1={2}" -f $row.relative_path, $row.length, $row.sha1)
}
Write-Host "Report:" $mdPath
Write-Host "JSON:" $jsonPath
