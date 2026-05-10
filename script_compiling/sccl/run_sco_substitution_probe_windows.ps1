<#
Code RED SCO substitution proof probe.

Purpose:
- Compile the existing vehicle_menu_probe as RDR_SCO.
- Inspect the resulting .sco artifact header.
- Compare it against generated .xsc/.csc and extracted active .wsc headers.
- Do not install/import anything into the game.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\run_sco_substitution_probe_windows.ps1
#>

param(
    [string]$RepoRoot = ".",
    [string]$ProjectName = "vehicle_menu_probe",
    [string]$OutputName = "test_sco"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Lane = Join-Path $RepoRoot "script_compiling\sccl"
$Compile = Join-Path $Lane "compile_sccl_project_windows.ps1"
$Inspect = Join-Path $Lane "inspect_script_artifact_headers_windows.ps1"
$Out = Join-Path $Lane "output"
$Report = Join-Path $Out "SCO_SUBSTITUTION_PROBE_REPORT.md"
$Json = Join-Path $Out "SCO_SUBSTITUTION_PROBE_REPORT.json"

if (-not (Test-Path $Compile)) { throw "Missing compile wrapper: $Compile" }
if (-not (Test-Path $Inspect)) { throw "Missing header inspector: $Inspect" }

Write-Host "# Code RED SCO Substitution Probe"
Write-Host "Compiling RDR_SCO proof artifact..."

powershell -ExecutionPolicy Bypass -File $Compile `
  -RepoRoot $RepoRoot `
  -ProjectName $ProjectName `
  -OutputName $OutputName `
  -Target RDR_SCO `
  -Platform X360

$exitCode = $LASTEXITCODE

Write-Host "Inspecting generated and extracted script headers..."

powershell -ExecutionPolicy Bypass -File $Inspect `
  -RepoRoot $RepoRoot `
  -Root @("script_compiling\sccl\output", "game\content_extracted", "logs\content_rpf_full_extract_after_magic_names\content") `
  -Max 120 `
  -Bytes 32

$scriptArtifacts = @()
$extensions = @(".sco", ".xsc", ".csc", ".wsc")
foreach ($ext in $extensions) {
    $scriptArtifacts += Get-ChildItem -Path $Out -Recurse -File -Filter "*$ext" -ErrorAction SilentlyContinue |
        Where-Object { $_.BaseName -match $OutputName -or $_.BaseName -match 'test_x360|test_ps3' }
}

function HeadHex($Path, $Count = 32) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        $take = [Math]::Min($Count, $bytes.Length)
        if ($take -le 0) { return "" }
        return (($bytes[0..($take - 1)] | ForEach-Object { $_.ToString("X2") }) -join " ")
    } catch { return "" }
}

$rows = @($scriptArtifacts | Sort-Object FullName -Unique | ForEach-Object {
    $hash = Get-FileHash -Path $_.FullName -Algorithm SHA1
    [pscustomobject]@{
        extension = $_.Extension
        length = $_.Length
        head_hex = HeadHex $_.FullName 32
        sha1 = $hash.Hash
        relative_path = $_.FullName.Substring($RepoRoot.Length).TrimStart('\')
    }
})

$summary = [ordered]@{
    project_name = $ProjectName
    output_name = $OutputName
    compile_exit_code = $exitCode
    generated_artifacts = $rows
    verdict = "If .sco compiles, it still must be runtime-tested by a non-critical script request. Header mismatch with active WSC means substitution is not proven by naming alone."
    safe_next_test = "Try a nonessential, tiny script alias/probe first; do not replace multiplayer_update_thread until the engine proves it will resolve/load .sco for a no-extension request."
}
$summary | ConvertTo-Json -Depth 10 | Set-Content -Path $Json -Encoding UTF8

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Code RED SCO Substitution Probe Report")
$lines.Add("")
$lines.Add("Project: $ProjectName")
$lines.Add("Output: $OutputName")
$lines.Add("RDR_SCO compile exit code: $exitCode")
$lines.Add("")
$lines.Add("## Generated artifacts")
if ($rows.Count -eq 0) {
    $lines.Add("- none")
} else {
    foreach ($r in $rows) {
        $lines.Add("### $($r.relative_path)")
        $lines.Add("- extension: $($r.extension)")
        $lines.Add("- length: $($r.length)")
        $lines.Add("- sha1: $($r.sha1)")
        $lines.Add("- first 32 bytes: $($r.head_hex)")
        $lines.Add("")
    }
}
$lines.Add("## Verdict")
$lines.Add("A successful .sco compile only proves SC-CL can emit RDR_SCO. It does not prove that active PC/Switch/PS4-style WSC requests will accept .sco in place of .wsc.")
$lines.Add("")
$lines.Add("Safe next test: use a tiny noncritical script probe/alias before attempting anything near multiplayer_update_thread.")
$lines -join "`n" | Set-Content -Path $Report -Encoding UTF8

Write-Host "Report:" $Report
Write-Host "JSON:" $Json
exit $exitCode
