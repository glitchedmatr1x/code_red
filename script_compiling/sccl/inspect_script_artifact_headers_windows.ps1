<#
Code RED script artifact header inspector.

Purpose:
- Compare generated SC-CL artifacts against extracted game script artifacts.
- Print extension, size, SHA1, and first bytes.
- Does not modify files or install/import anything into the game.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\inspect_script_artifact_headers_windows.ps1

Optional:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\inspect_script_artifact_headers_windows.ps1 -Root logs\content_rpf_full_extract_after_magic_names\content\release64 -Pattern "*.wsc" -Max 20
#>

param(
    [string]$RepoRoot = ".",
    [string[]]$Root = @(
        "script_compiling\sccl\output",
        "game\content_extracted",
        "logs\content_rpf_full_extract_after_magic_names\content",
        "logs\content_mp_singleplayer_build_probe\extracted_signals"
    ),
    [string]$Pattern = "*.*",
    [int]$Max = 80,
    [int]$Bytes = 16
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$extensions = @(".xsc", ".csc", ".wsc", ".sco", ".ysc")
$outDir = Join-Path $RepoRoot "script_compiling\sccl\output"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Get-HeadHex($Path, $Count) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        $take = [Math]::Min($Count, $bytes.Length)
        if ($take -le 0) { return "" }
        return (($bytes[0..($take - 1)] | ForEach-Object { $_.ToString("X2") }) -join " ")
    } catch {
        return ""
    }
}

function Get-ScriptKind($Head) {
    if ($Head -match '^85 43 53 52') { return 'XSC/CSR console marker 0x85' }
    if ($Head -match '^86 43 53 52') { return 'CSC/CSR console marker 0x86' }
    if ($Head -match '^87 43 53 52') { return 'CSR console marker 0x87 candidate' }
    if ($Head -match '^43 53 52') { return 'CSR marker without platform byte' }
    if ($Head -match '^52 53 43 85') { return 'WSC active RSC85 wrapper/header' }
    if ($Head -match '^52 53 43 86') { return 'RSC86 wrapper/header candidate' }
    if ($Head -match '^52 53 43 87') { return 'RSC87 wrapper/header candidate' }
    if ($Head -match '^52 53 43 37') { return 'RSC7 container candidate' }
    if ($Head -match '^53 43 52 02') { return 'SCO active/generated SCR02 header' }
    if ($Head -match '^53 43 4F') { return 'SCO ASCII marker candidate' }
    return 'unknown'
}

$files = New-Object System.Collections.Generic.List[object]
foreach ($r in $Root) {
    $path = if ([System.IO.Path]::IsPathRooted($r)) { $r } else { Join-Path $RepoRoot $r }
    if (-not (Test-Path $path)) { continue }
    Get-ChildItem -Path $path -Recurse -File -Filter $Pattern -ErrorAction SilentlyContinue |
        Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First $Max |
        ForEach-Object { $files.Add($_) }
}

$rows = @($files | Sort-Object FullName -Unique | Select-Object -First $Max | ForEach-Object {
    $head = Get-HeadHex $_.FullName $Bytes
    $sha = Get-FileHash -Path $_.FullName -Algorithm SHA1
    [pscustomobject]@{
        Extension = $_.Extension
        Kind = Get-ScriptKind $head
        Length = $_.Length
        HeadHex = $head
        SHA1 = $sha.Hash
        RelativePath = $_.FullName.Substring($RepoRoot.Length).TrimStart('\')
    }
})

$json = Join-Path $outDir "SCRIPT_ARTIFACT_HEADER_INSPECTION.json"
$txt = Join-Path $outDir "SCRIPT_ARTIFACT_HEADER_INSPECTION.txt"
$rows | ConvertTo-Json -Depth 5 | Set-Content -Path $json -Encoding UTF8
$rows | Format-Table -AutoSize | Out-String -Width 500 | Set-Content -Path $txt -Encoding UTF8

Write-Host "# Code RED Script Artifact Header Inspection"
Write-Host "Rows:" $rows.Count
$rows | Format-Table -AutoSize | Out-String -Width 500 | Write-Host
Write-Host "Report:" $txt
Write-Host "JSON:" $json
