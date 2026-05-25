param(
    [string]$CodeRedRoot = "D:\Games\Red Dead Redemption\Code_RED"
)

$ErrorActionPreference = "Stop"

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $AppRoot "backend"
New-Item -ItemType Directory -Force -Path $Backend | Out-Null

$Required = @(
    @{ Source = Join-Path $CodeRedRoot "python_workbench.py"; Dest = Join-Path $Backend "python_workbench.py" },
    @{ Source = Join-Path $CodeRedRoot "tools\codered_content_convert_overlay_builder.py"; Dest = Join-Path $Backend "codered_content_convert_overlay_builder.py" },
    @{ Source = Join-Path $CodeRedRoot "tools\codered_rpf_utils.py"; Dest = Join-Path $Backend "codered_rpf_utils.py" }
)

foreach ($item in $Required) {
    if (!(Test-Path $item.Source)) {
        throw "Missing required Code RED backend file: $($item.Source)"
    }
    Copy-Item $item.Source $item.Dest -Force
    Write-Host "Copied $($item.Source) -> $($item.Dest)"
}

Write-Host ""
Write-Host "Portable backend copied."
Write-Host "Install dependencies if needed:"
Write-Host "py -3 -m pip install -r requirements.txt"
