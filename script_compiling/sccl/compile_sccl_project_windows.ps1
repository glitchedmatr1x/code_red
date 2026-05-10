<#
Code RED generic SC-CL project compiler.

Purpose:
- Compile a named project under script_compiling/sccl/projects/<ProjectName>.
- Preserve the existing vehicle_menu_probe lane while enabling one-script probes.
- Inspect only real .xsc/.sco outputs and record hashes.
- Do not install/import anything into the game.

Run from repo root, example:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\compile_sccl_project_windows.ps1 -ProjectName multiplayer_update_thread_probe -OutputName multiplayer_update_thread
#>

param(
    [string]$RepoRoot = ".",
    [Parameter(Mandatory=$true)][string]$ProjectName,
    [string]$OutputName = "",
    [string]$SourceRelPath = "src\main.c",
    [string]$Target = "RDR_#SC",
    [string]$Platform = "X360",
    [switch]$SkipHeaderPromotion,
    [switch]$SkipRuntimeStage
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$Project = Join-Path $Lane "projects\$ProjectName"
$Source = Join-Path $Project $SourceRelPath
$ProjectInclude = Join-Path $Project "include"
$ProjectNativeHeader = Join-Path $ProjectInclude "RDR\natives32.h"
$OutRoot = Join-Path $Lane "output"
$Out = Join-Path $OutRoot $ProjectName
$Compiler = Join-Path $OutRoot "SC-CL.exe"
$Promote = Join-Path $Lane "promote_real_sccl_headers_windows.ps1"
$Stage = Join-Path $Lane "stage_sccl_runtime_windows.ps1"

if (-not $OutputName) { $OutputName = $ProjectName }

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
function HashFile($Path) {
    $hash = Get-FileHash -Path $Path -Algorithm SHA1
    return [ordered]@{
        path = $Path
        relative_path = $Path.Substring($RepoRoot.Length).TrimStart('\')
        length = (Get-Item $Path).Length
        sha1 = $hash.Hash
    }
}
function RequireFile($Path, $Label) {
    if (-not (Test-Path $Path)) {
        throw "Missing ${Label}: $Path"
    }
}

RequireFile $Source "SC-CL source"

if (-not (Test-Path $ProjectNativeHeader)) {
    if (-not $SkipHeaderPromotion -and (Test-Path $Promote)) {
        Write-Host "[CodeRED] Project headers missing; promoting real SC-CL headers..."
        powershell -ExecutionPolicy Bypass -File $Promote -RepoRoot $RepoRoot
    }
}

if (-not (Test-Path $ProjectNativeHeader)) {
    $laneInclude = Join-Path $Lane "include"
    if (Test-Path (Join-Path $laneInclude "RDR\natives32.h")) {
        Write-Host "[CodeRED] Copying lane include folder into project include..."
        New-Item -ItemType Directory -Force -Path $ProjectInclude | Out-Null
        Copy-Item -Path (Join-Path $laneInclude "*") -Destination $ProjectInclude -Recurse -Force
    }
}

RequireFile $ProjectNativeHeader "project native header"

if (IsFakeHeader $ProjectNativeHeader) {
    if ($SkipHeaderPromotion) {
        throw "Project header is a fake/proof shim and -SkipHeaderPromotion was set: $ProjectNativeHeader"
    }
    RequireFile $Promote "header promotion script"
    Write-Host "[CodeRED] Fake/proof shim header detected; promoting real SC-CL headers..."
    powershell -ExecutionPolicy Bypass -File $Promote -RepoRoot $RepoRoot
}

if (IsFakeHeader $ProjectNativeHeader) {
    throw "Project header is still fake after promotion: $ProjectNativeHeader"
}
if (-not (LooksRealHeader $ProjectNativeHeader)) {
    throw "Project header does not look like a real SC-CL RDR header: $ProjectNativeHeader"
}

if (-not (Test-Path $Compiler)) {
    if (-not $SkipRuntimeStage -and (Test-Path $Stage)) {
        Write-Host "[CodeRED] SC-CL.exe missing from output; staging runtime..."
        powershell -ExecutionPolicy Bypass -File $Stage -RepoRoot $RepoRoot
    }
}
RequireFile $Compiler "staged SC-CL compiler"

New-Item -ItemType Directory -Force -Path $Out | Out-Null

# SC-CL/Clang command-line parsing can break when a quoted Windows path ends in a single backslash.
# Match the proven vehicle probe behavior by passing a doubled trailing slash.
$OutArg = "$Out\\"

# Remove stale artifacts for this output name so inspection cannot pass on an old compile.
$stale = @(
    (Join-Path $OutRoot "$ProjectName$OutputName.xsc"),
    (Join-Path $OutRoot "$ProjectName$OutputName.sco"),
    (Join-Path $Out "$OutputName.xsc"),
    (Join-Path $Out "$OutputName.sco")
)
foreach ($s in $stale) { Remove-Item -LiteralPath $s -Force -ErrorAction SilentlyContinue }

$report = [ordered]@{
    project_name = $ProjectName
    output_name = $OutputName
    source = $Source
    include = $ProjectInclude
    compiler = $Compiler
    target = $Target
    platform = $Platform
    out_dir = $Out
    started = (Get-Date).ToString('s')
    command = @($Compiler, "-target=$Target", "-platform=$Platform", "-out-dir=$OutArg", "-name=$OutputName", "-extra-arg=-I$ProjectInclude", $Source)
}

Write-Host "# Code RED Generic SC-CL Compile"
Write-Host "Project:" $ProjectName
Write-Host "Output name:" $OutputName
Write-Host "Compiler:" $Compiler
Write-Host "Source:" $Source
Write-Host "Include:" $ProjectInclude
Write-Host "Target/platform:" "$Target / $Platform"
Write-Host "Output:" $OutArg

& $Compiler "-target=$Target" "-platform=$Platform" "-out-dir=$OutArg" "-name=$OutputName" "-extra-arg=-I$ProjectInclude" $Source
$exitCode = $LASTEXITCODE
$report.exit_code = $exitCode
$report.finished = (Get-Date).ToString('s')

if ($exitCode -eq -1073741515) {
    Write-Host "[CodeRED] Windows status 0xC0000135: SC-CL.exe launched but a required DLL was missing."
    Write-Host "[CodeRED] Run: powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1"
}

$artifactFiles = @()
$artifactFiles += Get-ChildItem -Path $OutRoot -Recurse -File -Filter "*.xsc" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match [regex]::Escape($OutputName) }
$artifactFiles += Get-ChildItem -Path $OutRoot -Recurse -File -Filter "*.sco" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match [regex]::Escape($OutputName) }
$artifactFiles = @($artifactFiles | Sort-Object FullName -Unique)
$artifacts = @($artifactFiles | ForEach-Object { HashFile $_.FullName })
$report.artifact_count = $artifacts.Count
$report.artifacts = $artifacts
$report.note = "Only .xsc and .sco files are counted as compiled artifacts. This script does not install/import anything into the game."

$jsonPath = Join-Path $OutRoot "$ProjectName`_compile_report.json"
$mdPath = Join-Path $OutRoot "$ProjectName`_compile_report.md"
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Code RED SC-CL Compile Report")
$lines.Add("")
$lines.Add("Project: $ProjectName")
$lines.Add("Output: $OutputName")
$lines.Add("Target/platform: $Target / $Platform")
$lines.Add("Exit code: $exitCode")
$lines.Add("Artifact count: $($artifacts.Count)")
$lines.Add("")
foreach ($a in $artifacts) {
    $lines.Add("## $($a.relative_path)")
    $lines.Add("- length: $($a.length)")
    $lines.Add("- sha1: $($a.sha1)")
    $lines.Add("")
}
if ($artifacts.Count -eq 0) {
    $lines.Add("No .xsc or .sco artifacts were found for this output name.")
    $lines.Add("")
    $lines.Add("Check compiler stdout/stderr, source syntax, target/platform, and output path parsing.")
}
$lines -join "`n" | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "[CodeRED] SC-CL exit:" $exitCode
Write-Host "[CodeRED] Artifact count:" $artifacts.Count
Write-Host "[CodeRED] Report:" $mdPath
Write-Host "[CodeRED] JSON:" $jsonPath

exit $exitCode
