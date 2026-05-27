<#
Build Code RED ScriptHookRDR AI Menu as a .asi plugin.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_ai_menu_asi_windows.ps1

Requirements:
- Visual Studio 2022 Build Tools or Community with C++ tools installed.
- Windows SDK.

Output:
  related_apps\Code_RED_ScriptHookRDR_AI_Menu\build\CodeRED_AI_Menu.asi
#>

param(
    [string]$RepoRoot = ".",
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$AppDir = Join-Path $RepoRoot "related_apps\Code_RED_ScriptHookRDR_AI_Menu"
$Source = Join-Path $AppDir "CodeRED_AI_Menu.bridge_candidate.cpp"
$BuildDir = Join-Path $AppDir "build"
$ObjDir = Join-Path $BuildDir "obj"
$OutAsi = Join-Path $BuildDir "CodeRED_AI_Menu.asi"

function Require-File($Path, $Label) {
    if (-not (Test-Path $Path)) {
        throw ("Missing {0}: {1}" -f $Label, $Path)
    }
}

function Find-VsDevCmd {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -eq 0 -and $install) {
            $candidate = Join-Path $install "Common7\Tools\VsDevCmd.bat"
            if (Test-Path $candidate) { return $candidate }
        }
    }

    $fallbacks = @(
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat",
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat",
        "%LOCAL_PATH% Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
    )
    foreach ($path in $fallbacks) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

Require-File $Source "AI menu C++ source"
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $ObjDir | Out-Null

$vsDevCmd = Find-VsDevCmd
if (-not $vsDevCmd) {
    throw "Could not find VsDevCmd.bat. Install Visual Studio 2022 Build Tools with C++ Desktop workload, or open a Developer PowerShell and run this script again."
}

$defineFlags = "/DWIN32 /D_WINDOWS /D_USRDLL /D_CRT_SECURE_NO_WARNINGS"
$commonFlags = "/nologo /std:c++17 /EHsc /LD /O2 /MT $defineFlags"
# GetAsyncKeyState is provided by User32.lib. Keep the build explicit so plain
# PowerShell builds behave the same as Developer Command Prompt builds.
$linkFlags = "/link /DLL /NOLOGO user32.lib /OUT:`"$OutAsi`""
$cmd = "call `"$vsDevCmd`" -arch=amd64 -host_arch=amd64 >nul && cd /d `"$AppDir`" && cl.exe $commonFlags /Fo`"$ObjDir\\`" /Fe`"$OutAsi`" `"$Source`" $linkFlags"

Write-Host "# Code RED AI Menu ASI Build"
Write-Host "Source:" $Source
Write-Host "Output:" $OutAsi
Write-Host "VsDevCmd:" $vsDevCmd
Write-Host "Link libs: user32.lib"

cmd.exe /c $cmd
$exitCode = $LASTEXITCODE
Write-Host "[CodeRED] cl.exe exit:" $exitCode
if ($exitCode -ne 0) { exit $exitCode }

if (-not (Test-Path $OutAsi)) {
    throw "Build completed but output .asi was not found: $OutAsi"
}

$hash = Get-FileHash -Path $OutAsi -Algorithm SHA1
$report = [ordered]@{
    source = $Source
    output = $OutAsi
    length = (Get-Item $OutAsi).Length
    sha1 = $hash.Hash
    configuration = $Configuration
    link_libs = @("user32.lib")
    built = (Get-Date).ToString('s')
}
$reportPath = Join-Path $BuildDir "CodeRED_AI_Menu_build_report.json"
$report | ConvertTo-Json -Depth 5 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "Built:" $OutAsi
Write-Host "Length:" $report.length
Write-Host "SHA1:" $hash.Hash
Write-Host "Report:" $reportPath
