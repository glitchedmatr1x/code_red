<#
Build Code RED Runtime Probe as a ScriptHookRDR .asi DLL.

Run from Code_RED repo root:
  powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_Runtime_Probe\build_runtime_probe_asi_windows.ps1 -RepoRoot .
#>
param(
    [string]$RepoRoot = ".",
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$AppDir = Join-Path $RepoRoot "related_apps\Code_RED_Runtime_Probe"
$Source = Join-Path $AppDir "CodeRED_Runtime_Probe.cpp"
$BuildDir = Join-Path $AppDir "build"
$ObjDir = Join-Path $BuildDir "obj"
$OutAsi = Join-Path $BuildDir "CodeRED_Runtime_Probe.asi"
$BuildLog = Join-Path $BuildDir "build_log.txt"

function Find-VsDevCmd {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -eq 0 -and $install) {
            $candidate = Join-Path $install "Common7\Tools\VsDevCmd.bat"
            if (Test-Path $candidate) { return $candidate }
        }
    }
    foreach ($path in @(
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat",
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat",
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
    )) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

if (-not (Test-Path $Source)) { throw "Missing source: $Source" }
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $ObjDir | Out-Null
$vsDevCmd = Find-VsDevCmd
if (-not $vsDevCmd) { throw "Visual Studio 2022 C++ VsDevCmd.bat was not found." }

$defineFlags = "/DWIN32 /D_WINDOWS /D_USRDLL /D_CRT_SECURE_NO_WARNINGS"
$commonFlags = "/nologo /std:c++17 /EHsc /LD /O2 /MT $defineFlags"
$linkFlags = "/link /DLL /NOLOGO user32.lib /OUT:`"$OutAsi`""
$cmd = "call `"$vsDevCmd`" -arch=amd64 -host_arch=amd64 >nul && cd /d `"$AppDir`" && cl.exe $commonFlags /Fo`"$ObjDir\\`" /Fe`"$OutAsi`" `"$Source`" $linkFlags"

"# Code RED Runtime Probe ASI Build" | Set-Content -Path $BuildLog -Encoding UTF8
"Source: $Source" | Add-Content -Path $BuildLog -Encoding UTF8
"Output: $OutAsi" | Add-Content -Path $BuildLog -Encoding UTF8
"VsDevCmd: $vsDevCmd" | Add-Content -Path $BuildLog -Encoding UTF8
"Command: $cmd" | Add-Content -Path $BuildLog -Encoding UTF8

Write-Host "# Code RED Runtime Probe ASI Build"
Write-Host "Source:" $Source
Write-Host "Output:" $OutAsi
Write-Host "VsDevCmd:" $vsDevCmd
cmd.exe /c $cmd 2>&1 | Tee-Object -FilePath $BuildLog -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path $OutAsi)) { throw "Build completed without ASI output: $OutAsi" }

$hash = Get-FileHash -Path $OutAsi -Algorithm SHA1
[ordered]@{
    source = $Source
    output = $OutAsi
    length = (Get-Item $OutAsi).Length
    sha1 = $hash.Hash
    configuration = $Configuration
    built = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $BuildDir "CodeRED_Runtime_Probe_build_report.json") -Encoding UTF8
Write-Host "Built:" $OutAsi
Write-Host "SHA1:" $hash.Hash
