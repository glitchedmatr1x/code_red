<#
Code RED SC-CL runtime diagnostic.

Purpose:
- Find every SC-CL.exe under the repo and nearby parent folder.
- Score each candidate by nearby DLL/runtime files and real SC-CL include folders.
- Extract likely imported DLL names from the executable when dumpbin is unavailable.
- Test-launch each candidate with a timeout and report 0xC0000135 missing-DLL failures.

This script is read-only. It does not move, delete, or rewrite files.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\diagnose_sccl_runtime_windows.ps1
#>

param(
    [string]$RepoRoot = ".",
    [string]$SearchRoot = "",
    [int]$LaunchTimeoutMs = 4000,
    [switch]$SkipLaunchTest
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
if (-not $SearchRoot) {
    $parent = Split-Path -Parent $RepoRoot
    $SearchRoot = $parent
}
$SearchRoot = (Resolve-Path $SearchRoot).Path

$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$OutDir = Join-Path $Lane "output"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Read-TextSafe($Path) {
    if (Test-Path $Path) { return Get-Content $Path -Raw -ErrorAction SilentlyContinue }
    return ""
}

function Test-RealScclIncludeFolder($Folder) {
    if (-not $Folder) { return $false }
    $natives = Join-Path $Folder "RDR\natives32.h"
    $consts = Join-Path $Folder "RDR\consts32.h"
    if (-not (Test-Path $natives)) { return $false }
    if (-not (Test-Path $consts)) { return $false }
    $txt = Read-TextSafe $natives
    if ($txt -match "Minimal Code RED proof natives") { return $false }
    return (($txt -match "SC-CL's include library" -or $txt -match "_native") -and $txt -match "CREATE_ACTOR_IN_LAYOUT")
}

function Find-IncludeNearExe($ExePath) {
    $dir = Split-Path -Parent $ExePath
    $checks = @(
        (Join-Path $dir "include"),
        (Join-Path $dir "Include"),
        (Join-Path (Split-Path -Parent $dir) "include"),
        (Join-Path (Split-Path -Parent $dir) "Include"),
        (Join-Path (Split-Path -Parent (Split-Path -Parent $dir)) "include"),
        (Join-Path (Split-Path -Parent (Split-Path -Parent $dir)) "Include")
    )
    foreach ($c in $checks) {
        if (Test-RealScclIncludeFolder $c) { return $c }
    }
    return $null
}

function Get-PrintableStrings($Path, [int]$MinLen = 4) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $sb = New-Object System.Text.StringBuilder
    $strings = New-Object System.Collections.Generic.List[string]
    foreach ($b in $bytes) {
        if ($b -ge 32 -and $b -le 126) {
            [void]$sb.Append([char]$b)
        } else {
            if ($sb.Length -ge $MinLen) { $strings.Add($sb.ToString()) }
            [void]$sb.Clear()
        }
    }
    if ($sb.Length -ge $MinLen) { $strings.Add($sb.ToString()) }
    return $strings
}

function Get-LikelyImportedDlls($ExePath) {
    $dumpbin = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
    if ($dumpbin) {
        try {
            $out = & $dumpbin.Source /DEPENDENTS $ExePath 2>$null
            $dlls = $out | Where-Object { $_ -match '\.dll\s*$' } | ForEach-Object { $_.Trim() }
            if ($dlls) { return @($dlls | Sort-Object -Unique) }
        } catch {}
    }

    try {
        $strings = Get-PrintableStrings $ExePath 4
        $dlls = $strings | ForEach-Object { [regex]::Matches($_, '[A-Za-z0-9_\-\.]+\.dll') } | ForEach-Object { $_.Value }
        return @($dlls | Sort-Object -Unique)
    } catch {
        return @()
    }
}

function Invoke-ScclLaunchTest($ExePath, [int]$TimeoutMs) {
    if ($SkipLaunchTest) {
        return [ordered]@{ attempted = $false; exit_code = $null; timed_out = $false; status = "skipped" }
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $ExePath
    $psi.Arguments = "--help"
    $psi.WorkingDirectory = Split-Path -Parent $ExePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    try {
        [void]$p.Start()
        if (-not $p.WaitForExit($TimeoutMs)) {
            try { $p.Kill() } catch {}
            return [ordered]@{ attempted = $true; exit_code = $null; timed_out = $true; status = "timeout" }
        }
        $code = $p.ExitCode
        $status = "exit_$code"
        if ($code -eq -1073741515) { $status = "missing_dll_0xC0000135" }
        return [ordered]@{ attempted = $true; exit_code = $code; timed_out = $false; status = $status }
    } catch {
        return [ordered]@{ attempted = $true; exit_code = $null; timed_out = $false; status = "launch_exception: $($_.Exception.Message)" }
    } finally {
        if ($p) { $p.Dispose() }
    }
}

$exeFiles = Get-ChildItem -Path $SearchRoot -Recurse -Filter "SC-CL.exe" -File -ErrorAction SilentlyContinue
$candidates = @()
foreach ($exe in $exeFiles) {
    $dir = $exe.Directory.FullName
    $dlls = @(Get-ChildItem -Path $dir -Filter "*.dll" -File -ErrorAction SilentlyContinue)
    $pdbs = @(Get-ChildItem -Path $dir -Filter "*.pdb" -File -ErrorAction SilentlyContinue)
    $include = Find-IncludeNearExe $exe.FullName
    $imports = @(Get-LikelyImportedDlls $exe.FullName)
    $launch = Invoke-ScclLaunchTest $exe.FullName $LaunchTimeoutMs
    $score = 0
    $score += 100
    $score += [Math]::Min($dlls.Count, 20) * 5
    if ($include) { $score += 40 }
    if ($dir -match 'SC-CL-master\\bin$') { $score += 20 }
    if ($dir -match 'resources\\SC-CL_DROP_HERE$') { $score -= 20 }
    if ($launch.status -eq 'missing_dll_0xC0000135') { $score -= 50 }
    if ($launch.status -eq 'timeout') { $score -= 5 }

    $candidates += [ordered]@{
        exe = $exe.FullName
        folder = $dir
        size_bytes = $exe.Length
        last_write_time = $exe.LastWriteTime.ToString('s')
        dll_count = $dlls.Count
        dlls = @($dlls | Select-Object -ExpandProperty Name | Sort-Object)
        pdb_count = $pdbs.Count
        include_folder = $include
        likely_imported_dlls = $imports
        launch_test = $launch
        score = $score
    }
}

$ranked = @($candidates | Sort-Object -Property score -Descending)
$best = if ($ranked.Count) { $ranked[0] } else { $null }
$report = [ordered]@{
    repo_root = $RepoRoot
    search_root = $SearchRoot
    candidate_count = $ranked.Count
    best_candidate = $best
    candidates = $ranked
    notes = @(
        "Exit -1073741515 means 0xC0000135: SC-CL.exe was found but Windows could not load a required DLL.",
        "Prefer a complete bin folder with nearby DLLs over a drop-only SC-CL.exe folder.",
        "If all launch tests fail with 0xC0000135, repair Microsoft Visual C++ Redistributable 2015-2022 x64 or stage the imported DLLs beside SC-CL.exe."
    )
}

$jsonPath = Join-Path $OutDir "SC_CL_RUNTIME_DIAGNOSTIC_REPORT.json"
$mdPath = Join-Path $OutDir "SC_CL_RUNTIME_DIAGNOSTIC_REPORT.md"
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8

$md = New-Object System.Collections.Generic.List[string]
$md.Add("# Code RED SC-CL Runtime Diagnostic")
$md.Add("")
$md.Add("Search root: `$SearchRoot`")
$md.Add("Candidates: $($ranked.Count)")
$md.Add("")
if ($best) {
    $md.Add("## Best candidate")
    $md.Add("")
    $md.Add("```text")
    $md.Add($best.exe)
    $md.Add("score=$($best.score) dll_count=$($best.dll_count) launch=$($best.launch_test.status)")
    $md.Add("```")
    $md.Add("")
}
$md.Add("## Candidates")
$md.Add("")
foreach ($c in $ranked) {
    $md.Add("### $($c.exe)")
    $md.Add("- score: $($c.score)")
    $md.Add("- dll count: $($c.dll_count)")
    $md.Add("- include folder: $($c.include_folder)")
    $md.Add("- launch status: $($c.launch_test.status)")
    if ($c.likely_imported_dlls.Count) {
        $md.Add("- likely imported DLLs: $([string]::Join(', ', $c.likely_imported_dlls))")
    }
    $md.Add("")
}
$md -join "`n" | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "# Code RED SC-CL Runtime Diagnostic"
Write-Host "Search root:" $SearchRoot
Write-Host "Candidates:" $ranked.Count
if ($best) {
    Write-Host "Best candidate:" $best.exe
    Write-Host "Best score:" $best.score
    Write-Host "Best launch:" $best.launch_test.status
}
Write-Host "Report:" $mdPath
Write-Host "JSON:" $jsonPath
