$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Output = Join-Path $PSScriptRoot 'output'
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$Log = Join-Path $Output 'compile_vehicle_menu_probe.log'
$Lab = Resolve-Path (Join-Path $PSScriptRoot '..\code_red_script_compile_lab_v1')
$Src = Join-Path $Lab 'src\main.c'
$OutDir = Join-Path $Output 'vehicle_menu_probe_build'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
"Code RED vehicle menu probe compile helper" | Set-Content $Log
"Started: $(Get-Date -Format o)" | Add-Content $Log

if (!(Test-Path $Src)) {
  "[ERROR] Missing source: $Src" | Add-Content $Log
  throw "Missing source: $Src"
}

$candidates = @()
if ($env:SCCL_EXE) { $candidates += $env:SCCL_EXE }
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
$candidates += @(
  (Join-Path $Root 'SC-CL.exe'),
  (Join-Path $PSScriptRoot 'SC-CL.exe'),
  (Join-Path $Lab 'SC-CL.exe'),
  (Join-Path $Root 'resources\SC-CL-master\bin\SC-CL.exe'),
  (Join-Path $Root 'resources\SC-CL-master\llvm-14.0.0.src\MinSizeRel\bin\SC-CL.exe')
)

$Sccl = $null
foreach ($candidate in $candidates) {
  if ($candidate -and (Test-Path $candidate)) { $Sccl = $candidate; break }
}
if (!$Sccl) {
  "[ERROR] SC-CL.exe not found. Set SCCL_EXE or place SC-CL.exe in the build kit folder." | Add-Content $Log
  throw 'SC-CL.exe not found.'
}

"Using SC-CL: $Sccl" | Add-Content $Log
"Source: $Src" | Add-Content $Log
"Output dir: $OutDir" | Add-Content $Log
& $Sccl $Src '-o' (Join-Path $OutDir 'vehicle_menu_probe') 2>&1 | Tee-Object -FilePath $Log -Append
if ($LASTEXITCODE -ne 0) { throw "SC-CL compile failed. Review $Log" }
Write-Host "Compile helper completed. Review $OutDir and $Log."
