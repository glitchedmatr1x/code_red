<#
Code RED local-only multiplayer thread probe preparer.

Purpose:
- Create a local SC-CL probe project for decoded/decompiled multiplayer scripts.
- Copy a user-supplied decoded source file into src/main.c.
- Copy active SC-CL headers into the probe project.
- Write a local prep report with artifact/source warnings.
- Do not commit decoded Rockstar/game script source into the repository.
- Do not install/import anything into the game.

Run from repo root, example:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\prepare_multiplayer_thread_probe_windows.ps1 `
    -ProjectName multiplayer_update_thread_probe `
    -OutputName multiplayer_update_thread `
    -DecodedSource scratch\decoded_xsc\multiplayer_update_thread.c
#>

param(
    [string]$RepoRoot = ".",
    [string]$ProjectName = "multiplayer_update_thread_probe",
    [string]$OutputName = "multiplayer_update_thread",
    [Parameter(Mandatory=$true)][string]$DecodedSource,
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$Project = Join-Path $Lane "projects\$ProjectName"
$SrcDir = Join-Path $Project "src"
$ScriptsDir = Join-Path $Project "scripts"
$ReportDir = Join-Path $Project "reports"
$ProjectInclude = Join-Path $Project "include"
$LaneInclude = Join-Path $Lane "include"
$Main = Join-Path $SrcDir "main.c"
$SourcePath = (Resolve-Path $DecodedSource).Path

function RequireFile($Path, $Label) {
    if (-not (Test-Path $Path)) {
        throw "Missing ${Label}: $Path"
    }
}
function ReadText($Path) {
    if (Test-Path $Path) { return Get-Content $Path -Raw -Encoding UTF8 -ErrorAction SilentlyContinue }
    return ""
}
function CountRegex($Text, $Pattern) {
    return ([regex]::Matches($Text, $Pattern)).Count
}
function CountChar($Text, [char]$Char) {
    return ($Text.ToCharArray() | Where-Object { $_ -eq $Char }).Count
}

RequireFile $SourcePath "decoded source"
RequireFile (Join-Path $LaneInclude "RDR\natives32.h") "lane RDR native header"
RequireFile (Join-Path $LaneInclude "RDR\consts32.h") "lane RDR constants header"

New-Item -ItemType Directory -Force -Path $SrcDir, $ScriptsDir, $ReportDir, $ProjectInclude | Out-Null

if ((Test-Path $Main) -and -not $Overwrite) {
    throw "Project source already exists: $Main. Re-run with -Overwrite to replace it."
}

Copy-Item -Path $SourcePath -Destination $Main -Force
Copy-Item -Path (Join-Path $LaneInclude "*") -Destination $ProjectInclude -Recurse -Force

$text = ReadText $Main
$unknownFunctionCount = CountRegex $text '\bUnknown_Function\s*\('
$unknownNativeCount = CountRegex $text '\bUNK_0x[0-9A-Fa-f]+\b'
$functionCount = CountRegex $text '\bFunction_\d+\s*\('
$launchCalls = CountRegex $text '\bLAUNCH_NEW_SCRIPT\s*\('
$requestCalls = CountRegex $text '\bREQUEST_ASSET\s*\('
$netCalls = CountRegex $text '\bNET_[A-Z0-9_]+\s*\('
$uiEvents = CountRegex $text '\bUI_SEND_EVENT\s*\('
$waitCalls = CountRegex $text '\bWAIT\s*\('
$hasMain = $text -match '\bvoid\s+main\s*\('
$braceBalance = (CountChar $text '{') -eq (CountChar $text '}')
$parenBalance = (CountChar $text '(') -eq (CountChar $text ')')

$warnings = New-Object System.Collections.Generic.List[string]
if (-not $hasMain) { $warnings.Add("No 'void main()' entrypoint was detected.") }
if (-not $braceBalance) { $warnings.Add("Brace counts are not balanced.") }
if (-not $parenBalance) { $warnings.Add("Parenthesis counts are not balanced.") }
if ($unknownFunctionCount -gt 0) { $warnings.Add("Unknown_Function calls remain. SC-CL may not compile until these are resolved or mapped.") }
if ($text -match '(?m)^\s*#region') { $warnings.Add("Decompiler #region blocks remain. If SC-CL rejects them, remove or convert them to comments.") }
if ($text -match 'char\*\s+\w+\[\d+\]') { $warnings.Add("Decompiler char* array syntax was detected; SC-CL may require cleanup depending on parser behavior.") }
if ($text -match '\bvar\s+') { $warnings.Add("Decompiler 'var' declarations were detected; verify SC-CL accepts this dialect.") }
if ($text -match '\bbool\s+bVar\d+;') { $warnings.Add("Decompiler bool temporaries are present; this is expected but should be checked if compile fails.") }

$manifest = [ordered]@{
    project_name = $ProjectName
    output_name = $OutputName
    source_input = $SourcePath
    staged_source = $Main
    include = $ProjectInclude
    prepared_at = (Get-Date).ToString('s')
    counts = [ordered]@{
        unknown_function_calls = $unknownFunctionCount
        unknown_native_symbols = $unknownNativeCount
        function_references = $functionCount
        launch_new_script_calls = $launchCalls
        request_asset_calls = $requestCalls
        net_native_calls = $netCalls
        ui_send_event_calls = $uiEvents
        wait_calls = $waitCalls
    }
    shape = [ordered]@{
        has_void_main = $hasMain
        brace_balance = $braceBalance
        paren_balance = $parenBalance
    }
    warnings = @($warnings)
    boundary = "Local probe only. The decoded source is copied into the working tree for local compiling, but should not be committed to GitHub."
    next_command = "powershell -ExecutionPolicy Bypass -File script_compiling\\sccl\\compile_sccl_project_windows.ps1 -ProjectName $ProjectName -OutputName $OutputName"
}

$jsonPath = Join-Path $ReportDir "PREP_REPORT.json"
$mdPath = Join-Path $ReportDir "PREP_REPORT.md"
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Code RED Multiplayer Thread Probe Prep Report")
$lines.Add("")
$lines.Add("Project: $ProjectName")
$lines.Add("Output name: $OutputName")
$lines.Add("Input: $SourcePath")
$lines.Add("Staged source: $Main")
$lines.Add("")
$lines.Add("## Counts")
$lines.Add("- Unknown_Function calls: $unknownFunctionCount")
$lines.Add("- UNK_0x native symbols: $unknownNativeCount")
$lines.Add("- Function references: $functionCount")
$lines.Add("- LAUNCH_NEW_SCRIPT calls: $launchCalls")
$lines.Add("- REQUEST_ASSET calls: $requestCalls")
$lines.Add("- NET_* calls: $netCalls")
$lines.Add("- UI_SEND_EVENT calls: $uiEvents")
$lines.Add("- WAIT calls: $waitCalls")
$lines.Add("")
$lines.Add("## Shape")
$lines.Add("- has void main: $hasMain")
$lines.Add("- brace balance: $braceBalance")
$lines.Add("- paren balance: $parenBalance")
$lines.Add("")
$lines.Add("## Warnings")
if ($warnings.Count -eq 0) {
    $lines.Add("- none")
} else {
    foreach ($w in $warnings) { $lines.Add("- $w") }
}
$lines.Add("")
$lines.Add("## Next command")
$lines.Add("")
$lines.Add('```powershell')
$lines.Add($manifest.next_command)
$lines.Add('```')
$lines.Add("")
$lines.Add("Boundary: local probe only; do not commit decoded game script source.")
$lines -join "`n" | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "# Code RED Multiplayer Thread Probe Prep"
Write-Host "Project:" $ProjectName
Write-Host "Source staged:" $Main
Write-Host "Unknown_Function calls:" $unknownFunctionCount
Write-Host "UNK_0x symbols:" $unknownNativeCount
Write-Host "Warnings:" $warnings.Count
foreach ($w in $warnings) { Write-Host "  - $w" }
Write-Host "Report:" $mdPath
Write-Host "Next:"
Write-Host "  " $manifest.next_command
