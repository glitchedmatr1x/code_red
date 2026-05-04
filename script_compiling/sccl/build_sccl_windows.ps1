$ErrorActionPreference = 'Stop'
$Root = Resolve-Path "$PSScriptRoot\..\..\.."
$Output = Join-Path $PSScriptRoot 'output'
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$Log = Join-Path $Output 'build_sccl_windows.log'
"Code RED SC-CL Windows build helper" | Set-Content $Log
"Started: $(Get-Date -Format o)" | Add-Content $Log

$candidates = @()
if ($env:SCCL_EXE) { $candidates += $env:SCCL_EXE }
$candidates += @(
  (Join-Path $Root 'SC-CL.exe'),
  (Join-Path $PSScriptRoot 'SC-CL.exe'),
  (Join-Path $PSScriptRoot '..\code_red_script_compile_lab_v1\SC-CL.exe'),
  (Join-Path $Root 'resources\SC-CL-master\bin\SC-CL.exe'),
  (Join-Path $Root 'resources\SC-CL-master\llvm-14.0.0.src\MinSizeRel\bin\SC-CL.exe')
)

foreach ($candidate in $candidates) {
  if ($candidate -and (Test-Path $candidate)) {
    "Found SC-CL.exe at $candidate" | Add-Content $Log
    Write-Host "Found SC-CL.exe at $candidate"
    exit 0
  }
}

"SC-CL.exe was not found. Place SC-CL.exe here or set SCCL_EXE." | Add-Content $Log
Write-Warning 'SC-CL.exe not found. This is a detection helper, not a source builder.'
exit 2
