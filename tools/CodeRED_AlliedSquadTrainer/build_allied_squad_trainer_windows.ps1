<#
Build CodeRED_AlliedSquadTrainer.asi.

Run from Code_RED repo root:
  powershell -ExecutionPolicy Bypass -File tools\CodeRED_AlliedSquadTrainer\build_allied_squad_trainer_windows.ps1
#>

param(
    [string]$RepoRoot = ".",
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$AppDir = Join-Path $RepoRoot "tools\CodeRED_AlliedSquadTrainer"
$Source = Join-Path $AppDir "CodeRED_AlliedSquadTrainer.cpp"
$BuildDir = Join-Path $AppDir "build"
$ObjDir = Join-Path $BuildDir "obj"
$OutAsi = Join-Path $BuildDir "CodeRED_AlliedSquadTrainer.asi"
$BuildLog = Join-Path $BuildDir "build_log.txt"
$SourceIni = Join-Path $AppDir "data\codered\allied_squad_trainer.ini"
$InstallPackage = Join-Path $BuildDir "install_package"
$InstallDataDir = Join-Path $InstallPackage "data\codered"
$SdkRoot = "D:\Games\Red Dead Redemption\ScriptHookRDR\sdk"
$SdkInc = Join-Path $SdkRoot "inc"
$SdkLib = Join-Path $SdkRoot "lib\ScriptHookRDR.lib"

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
    foreach ($path in @(
        "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat",
        "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat",
        "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
    )) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

Require-File $Source "CodeRED Allied Squad Trainer source"
Require-File $SourceIni "CodeRED Allied Squad Trainer INI"
Require-File $SdkLib "ScriptHookRDR import library"
Require-File (Join-Path $SdkInc "main.h") "ScriptHookRDR main.h"
Require-File (Join-Path $SdkInc "natives.h") "ScriptHookRDR natives.h"
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $ObjDir | Out-Null

$vsDevCmd = Find-VsDevCmd
if (-not $vsDevCmd) {
    throw "Could not find VsDevCmd.bat. Install Visual Studio 2022 Build Tools with C++ Desktop workload."
}

$defineFlags = "/DWIN32 /D_WINDOWS /D_USRDLL /D_CRT_SECURE_NO_WARNINGS"
$commonFlags = "/nologo /std:c++20 /EHsc /LD /O2 /MT $defineFlags /I`"$SdkInc`""
$linkFlags = "/link /DLL /NOLOGO user32.lib `"$SdkLib`" /OUT:`"$OutAsi`""
$cmd = "call `"$vsDevCmd`" -arch=amd64 -host_arch=amd64 >nul && cd /d `"$AppDir`" && cl.exe $commonFlags /Fo`"$ObjDir\\`" /Fe`"$OutAsi`" `"$Source`" $linkFlags"

"# CodeRED_AlliedSquadTrainer build" | Set-Content -Path $BuildLog -Encoding UTF8
"Source: $Source" | Add-Content -Path $BuildLog -Encoding UTF8
"Output: $OutAsi" | Add-Content -Path $BuildLog -Encoding UTF8
"SDK include: $SdkInc" | Add-Content -Path $BuildLog -Encoding UTF8
"SDK lib: $SdkLib" | Add-Content -Path $BuildLog -Encoding UTF8
"VsDevCmd: $vsDevCmd" | Add-Content -Path $BuildLog -Encoding UTF8

Write-Host "# CodeRED_AlliedSquadTrainer ASI Build"
Write-Host "Source:" $Source
Write-Host "Output:" $OutAsi
Write-Host "VsDevCmd:" $vsDevCmd

cmd.exe /c $cmd 2>&1 | Tee-Object -FilePath $BuildLog -Append
$exitCode = $LASTEXITCODE
Write-Host "[CodeRED] cl.exe exit:" $exitCode
if ($exitCode -ne 0) { exit $exitCode }
if (-not (Test-Path $OutAsi)) { throw "Build completed but output .asi was not found: $OutAsi" }

New-Item -ItemType Directory -Force -Path $InstallDataDir | Out-Null
Copy-Item -Force -Path $OutAsi -Destination (Join-Path $InstallPackage "CodeRED_AlliedSquadTrainer.asi")
Copy-Item -Force -Path $SourceIni -Destination (Join-Path $InstallDataDir "allied_squad_trainer.ini")

$hash = Get-FileHash -Path $OutAsi -Algorithm SHA1
$iniHash = Get-FileHash -Path $SourceIni -Algorithm SHA1
$report = [ordered]@{
    source = $Source
    output = $OutAsi
    install_package = $InstallPackage
    length = (Get-Item $OutAsi).Length
    sha1 = $hash.Hash
    ini = $SourceIni
    ini_sha1 = $iniHash.Hash
    configuration = $Configuration
    sdk_inc = $SdkInc
    sdk_lib = $SdkLib
    built = (Get-Date).ToString('s')
}
$reportPath = Join-Path $BuildDir "CodeRED_AlliedSquadTrainer_build_report.json"
$report | ConvertTo-Json -Depth 5 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "Built:" $OutAsi
Write-Host "SHA1:" $hash.Hash
Write-Host "Install package:" $InstallPackage
Write-Host "Report:" $reportPath
