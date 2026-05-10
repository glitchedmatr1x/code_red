<#
Code RED WSC/SCO pair mapper.

Purpose:
- Map active extracted script files that exist as both .wsc and .sco.
- Highlight missing multiplayer script bases that may be viable SCO candidates.
- Write full CSV/JSON/Markdown reports without truncating console paths.
- Does not modify or install anything into the game.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\map_wsc_sco_pairs_windows.ps1
#>

param(
    [string]$RepoRoot = ".",
    [string]$SourceRoot = "game\content_extracted\release64",
    [string]$OutDir = "script_compiling\sccl\output",
    [int]$ConsoleTop = 80
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$SourceRootPath = if ([System.IO.Path]::IsPathRooted($SourceRoot)) { $SourceRoot } else { Join-Path $RepoRoot $SourceRoot }
$OutPath = if ([System.IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $RepoRoot $OutDir }
New-Item -ItemType Directory -Force -Path $OutPath | Out-Null

if (-not (Test-Path $SourceRootPath)) {
    throw "Missing source root: $SourceRootPath"
}

function Rel($Path) {
    return $Path.Substring($RepoRoot.Length).TrimStart('\')
}
function HeadHex($Path, $Count = 8) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        $take = [Math]::Min($Count, $bytes.Length)
        if ($take -le 0) { return "" }
        return (($bytes[0..($take - 1)] | ForEach-Object { $_.ToString("X2") }) -join " ")
    } catch { return "" }
}

$scriptFiles = @(Get-ChildItem -Recurse $SourceRootPath -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension.ToLowerInvariant() -in @('.wsc', '.sco') })

$groups = $scriptFiles | Group-Object { $_.FullName.Substring(0, $_.FullName.Length - $_.Extension.Length) }

$rows = @($groups | ForEach-Object {
    $wsc = @($_.Group | Where-Object { $_.Extension.ToLowerInvariant() -eq '.wsc' } | Select-Object -First 1)
    $sco = @($_.Group | Where-Object { $_.Extension.ToLowerInvariant() -eq '.sco' } | Select-Object -First 1)
    $base = $_.Name
    [pscustomobject]@{
        BasePath = Rel $base
        HasWSC = [bool]$wsc.Count
        HasSCO = [bool]$sco.Count
        WSCBytes = if ($wsc.Count) { $wsc[0].Length } else { $null }
        SCOBytes = if ($sco.Count) { $sco[0].Length } else { $null }
        WSCHead = if ($wsc.Count) { HeadHex $wsc[0].FullName 8 } else { "" }
        SCOHead = if ($sco.Count) { HeadHex $sco[0].FullName 8 } else { "" }
    }
})

$pairs = @($rows | Where-Object { $_.HasWSC -and $_.HasSCO } | Sort-Object BasePath)
$wscOnly = @($rows | Where-Object { $_.HasWSC -and -not $_.HasSCO } | Sort-Object BasePath)
$scoOnly = @($rows | Where-Object { $_.HasSCO -and -not $_.HasWSC } | Sort-Object BasePath)

$targetNames = @(
    'multiplayer_update_thread',
    'multiplayer_system_thread',
    'mp_idle',
    'freemode',
    'main_z',
    'sp_idle',
    'init_zombiepack',
    'long_update_thread_z',
    'medium_update_thread_z',
    'short_update_thread_z',
    'player_z'
)
$targets = @($rows | Where-Object {
    $bp = $_.BasePath.ToLowerInvariant()
    foreach ($t in $targetNames) {
        if ($bp.EndsWith($t.ToLowerInvariant()) -or $bp -match [regex]::Escape($t.ToLowerInvariant())) { return $true }
    }
    return $false
} | Sort-Object BasePath)

$csvPairs = Join-Path $OutPath "WSC_SCO_PAIRS.csv"
$csvWscOnly = Join-Path $OutPath "WSC_ONLY_SCRIPTS.csv"
$csvScoOnly = Join-Path $OutPath "SCO_ONLY_SCRIPTS.csv"
$csvTargets = Join-Path $OutPath "WSC_SCO_TARGET_SCRIPT_STATUS.csv"
$json = Join-Path $OutPath "WSC_SCO_PAIR_MAP.json"
$md = Join-Path $OutPath "WSC_SCO_PAIR_MAP.md"

$pairs | Export-Csv -Path $csvPairs -NoTypeInformation -Encoding UTF8
$wscOnly | Export-Csv -Path $csvWscOnly -NoTypeInformation -Encoding UTF8
$scoOnly | Export-Csv -Path $csvScoOnly -NoTypeInformation -Encoding UTF8
$targets | Export-Csv -Path $csvTargets -NoTypeInformation -Encoding UTF8

$summary = [ordered]@{
    source_root = Rel $SourceRootPath
    generated_at = (Get-Date).ToString('s')
    total_script_bases = $rows.Count
    pair_count = $pairs.Count
    wsc_only_count = $wscOnly.Count
    sco_only_count = $scoOnly.Count
    target_script_status = $targets
    reports = [ordered]@{
        pairs_csv = Rel $csvPairs
        wsc_only_csv = Rel $csvWscOnly
        sco_only_csv = Rel $csvScoOnly
        targets_csv = Rel $csvTargets
    }
}
$summary | ConvertTo-Json -Depth 10 | Set-Content -Path $json -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Code RED WSC/SCO Pair Map")
$lines.Add("")
$lines.Add("Source root: $(Rel $SourceRootPath)")
$lines.Add("Total script bases: $($rows.Count)")
$lines.Add("WSC/SCO pairs: $($pairs.Count)")
$lines.Add("WSC-only: $($wscOnly.Count)")
$lines.Add("SCO-only: $($scoOnly.Count)")
$lines.Add("")
$lines.Add("## Target script status")
$lines.Add("")
if ($targets.Count -eq 0) {
    $lines.Add("No target rows found.")
} else {
    foreach ($t in $targets) {
        $lines.Add("- $($t.BasePath) | WSC=$($t.HasWSC) SCO=$($t.HasSCO) WSCBytes=$($t.WSCBytes) SCOBytes=$($t.SCOBytes)")
    }
}
$lines.Add("")
$lines.Add("## Reports")
$lines.Add("- $(Rel $csvPairs)")
$lines.Add("- $(Rel $csvWscOnly)")
$lines.Add("- $(Rel $csvScoOnly)")
$lines.Add("- $(Rel $csvTargets)")
$lines -join "`n" | Set-Content -Path $md -Encoding UTF8

Write-Host "# Code RED WSC/SCO Pair Map"
Write-Host "Source root:" (Rel $SourceRootPath)
Write-Host "Total script bases:" $rows.Count
Write-Host "WSC/SCO pairs:" $pairs.Count
Write-Host "WSC-only:" $wscOnly.Count
Write-Host "SCO-only:" $scoOnly.Count
Write-Host "Target status:"
$targets | Select-Object -First $ConsoleTop | Format-Table -AutoSize | Out-String -Width 500 | Write-Host
Write-Host "Reports:"
Write-Host "  $csvPairs"
Write-Host "  $csvWscOnly"
Write-Host "  $csvScoOnly"
Write-Host "  $csvTargets"
Write-Host "  $md"
Write-Host "  $json"
