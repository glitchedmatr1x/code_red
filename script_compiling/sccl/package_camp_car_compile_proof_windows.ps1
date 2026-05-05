<#
Package the Code RED SC-CL camp-car runtime proof.

Purpose:
- Collect the compiled camp_car_probe.xsc artifact.
- Record hashes for the compiled output, source, active project headers, and staged compiler.
- Create a proof-only ZIP package.
- Do not install/import anything into the game.

Run from repo root after a successful compile:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\package_camp_car_compile_proof_windows.ps1
#>

param([string]$RepoRoot = ".")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$Project = Join-Path $Lane "projects\camp_car_probe"
$OutputRoot = Join-Path $Lane "output"
$Artifact = Join-Path $OutputRoot "camp_car_probe\camp_car_probe.xsc"
$Compiler = Join-Path $OutputRoot "SC-CL.exe"
$Source = Join-Path $Project "src\main.c"
$ProjectInclude = Join-Path $Project "include"
$PackageRoot = Join-Path $OutputRoot "proof_packages"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ProofDir = Join-Path $PackageRoot "camp_car_probe_compile_proof_$Stamp"
$ZipPath = "$ProofDir.zip"

function Require-File($Path, $Label) {
    if (-not (Test-Path $Path)) {
        throw ("Missing {0}: {1}" -f $Label, $Path)
    }
}

function Hash-File($Path) {
    $hash = Get-FileHash -Path $Path -Algorithm SHA1
    return [ordered]@{
        path = $Path
        relative_path = $Path.Substring($RepoRoot.Length).TrimStart('\\')
        length = (Get-Item $Path).Length
        sha1 = $hash.Hash
    }
}

Require-File $Artifact "compiled camp-car artifact"
Require-File $Compiler "staged compiler"
Require-File $Source "camp-car source"
Require-File (Join-Path $ProjectInclude "RDR\natives32.h") "project native header"
Require-File (Join-Path $ProjectInclude "RDR\consts32.h") "project constants header"

New-Item -ItemType Directory -Force -Path $ProofDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ProofDir "artifact") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ProofDir "source") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ProofDir "headers") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ProofDir "reports") | Out-Null

Copy-Item -Path $Artifact -Destination (Join-Path $ProofDir "artifact\camp_car_probe.xsc") -Force
Copy-Item -Path $Source -Destination (Join-Path $ProofDir "source\main.c") -Force
Copy-Item -Path $ProjectInclude -Destination (Join-Path $ProofDir "headers\include") -Recurse -Force

$optionalReports = @(
    "camp_car_probe_output_report.json",
    "camp_car_probe_output_report.md",
    "SC_CL_HEADER_PROMOTION_REPORT.json",
    "SC_CL_RUNTIME_STAGE_REPORT.json",
    "SC_CL_RUNTIME_DIAGNOSTIC_REPORT.json",
    "SC_CL_RUNTIME_DIAGNOSTIC_REPORT.md",
    "SC_CL_LANE_DOCTOR_REPORT.json"
)
foreach ($name in $optionalReports) {
    $path = Join-Path $OutputRoot $name
    if (Test-Path $path) {
        Copy-Item -Path $path -Destination (Join-Path $ProofDir "reports\$name") -Force
    }
}

$filesToHash = @(
    $Artifact,
    $Compiler,
    $Source,
    (Join-Path $ProjectInclude "RDR\natives32.h"),
    (Join-Path $ProjectInclude "RDR\consts32.h"),
    (Join-Path $ProjectInclude "types.h"),
    (Join-Path $ProjectInclude "constants.h"),
    (Join-Path $ProjectInclude "intrinsics.h"),
    (Join-Path $ProjectInclude "natives.h")
) | Where-Object { Test-Path $_ }

$hashRows = @($filesToHash | ForEach-Object { Hash-File $_ })

$manifest = [ordered]@{
    package = "camp_car_probe_compile_proof"
    created = (Get-Date).ToString('s')
    repo_root = $RepoRoot
    artifact = Hash-File $Artifact
    compiler = Hash-File $Compiler
    source = Hash-File $Source
    headers = @($hashRows | Where-Object { $_.relative_path -match 'include' })
    runtime_controls = @(
        "Stand near/inside camp.",
        "F5 = spawn ACTOR_VEHICLE_Car01 near the player",
        "F6 = put player in car",
        "F7 = re-apply vehicle tune",
        "F8 = delete the probe car"
    )
    boundary = "Proof package only. Runtime proof artifact only. Do not install/import into the game yet. Camp/RPF archive install lane is not proven."
    next_safe_steps = @(
        "Verify compiled artifact naming and hash.",
        "Use this only as a runtime/camp-car proof artifact.",
        "Research archive/import candidates separately before any install attempt."
    )
}

$manifestPath = Join-Path $ProofDir "COMPILE_PROOF_MANIFEST.json"
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Path $manifestPath -Encoding UTF8

$readme = @"
# Code RED Camp Car Runtime Proof

This package is proof-only.

## Compiled artifact

~~~text
artifact/camp_car_probe.xsc
sha1: $($manifest.artifact.sha1)
length: $($manifest.artifact.length)
~~~

## Runtime controls

~~~text
Stand near/inside camp.
F5 = spawn ACTOR_VEHICLE_Car01 near the player
F6 = put player in car
F7 = re-apply vehicle tune
F8 = delete the probe car
~~~

## Boundary

Do not install/import this compiled script into the game yet.

This proves the SC-CL camp-car runtime proof compile only. Camp/RPF archive install behavior is still a separate lane.

## Included

~~~text
artifact/camp_car_probe.xsc
source/main.c
headers/include/
reports/
COMPILE_PROOF_MANIFEST.json
~~~
"@
$readme | Set-Content -Path (Join-Path $ProofDir "README.md") -Encoding UTF8

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $ProofDir "*") -DestinationPath $ZipPath -Force

$packageHash = Get-FileHash -Path $ZipPath -Algorithm SHA1
$summary = [ordered]@{
    proof_dir = $ProofDir
    zip_path = $ZipPath
    zip_sha1 = $packageHash.Hash
    artifact_sha1 = $manifest.artifact.sha1
    artifact_length = $manifest.artifact.length
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $OutputRoot "camp_car_compile_proof_package_latest.json") -Encoding UTF8

Write-Host "# Code RED Camp Car Compile Proof Package"
Write-Host "Proof dir:" $ProofDir
Write-Host "ZIP:" $ZipPath
Write-Host "ZIP SHA1:" $packageHash.Hash
Write-Host "Artifact SHA1:" $manifest.artifact.sha1
Write-Host "Artifact length:" $manifest.artifact.length
Write-Host "Boundary: proof package only; not installed/imported."
