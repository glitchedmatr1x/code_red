$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path "$PSScriptRoot\..\..\..\..")
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py scan --refresh
py -3 tools\codered_script_compile_validation.py
Write-Host 'Review related_apps\CodeRED_Script_Workshop\workspace\recompile_queue before output promotion.'
