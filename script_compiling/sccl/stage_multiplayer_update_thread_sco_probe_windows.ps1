<#
Code RED multiplayer_update_thread SCO probe stager.

Purpose:
- Stage the compiled multiplayer_update_thread.sco stub into a patch-layer mirror folder.
- Mirror the active extracted script tree under release64.
- Do not inject or install anything into game archives.
- Write a manifest and README describing the probe boundary.

Run from repo root after compiling the stub:
  powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_multiplayer_update_thread_sco_probe_windows.ps1
#>

param(
    [string]$RepoRoot = ".",
    [string]$CompiledSCO = "script_compiling\sccl\output\multiplayer_update_thread_stub\multiplayer_update_thread.sco",
    [string]$PatchRoot = "script_compiling\sccl\output\sco_loader_probe_patch",
    [string]$TargetRelativePath = "release64\multiplayer\multiplayer_update_thread.sco"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$CompiledPath = if ([System.IO.Path]::IsPathRooted($CompiledSCO)) { $CompiledSCO } else { Join-Path $RepoRoot $CompiledSCO }
$PatchRootPath = if ([System.IO.Path]::IsPathRooted($PatchRoot)) { $PatchRoot } else { Join-Path $RepoRoot $PatchRoot }
$TargetPath = Join-Path $PatchRootPath $TargetRelativePath
$ManifestPath = Join-Path $PatchRootPath "SCO_LOADER_PROBE_MANIFEST.json"
$ReadmePath = Join-Path $PatchRootPath "README_SCO_LOADER_PROBE.txt"

if (-not (Test-Path $CompiledPath)) {
    throw "Missing compiled SCO probe: $CompiledPath. Compile first with compile_sccl_project_windows.ps1 -ProjectName multiplayer_update_thread_stub -OutputName multiplayer_update_thread -Target RDR_SCO -Platform X360"
}

function Rel($Path) {
    return $Path.Substring($RepoRoot.Length).TrimStart('\')
}
function HeadHex($Path, $Count = 16) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $take = [Math]::Min($Count, $bytes.Length)
    if ($take -le 0) { return "" }
    return (($bytes[0..($take - 1)] | ForEach-Object { $_.ToString("X2") }) -join " ")
}

# Remove the earlier wrong content\multiplayer staging path if present so the patch root is unambiguous.
$legacyTarget = Join-Path $PatchRootPath "content\multiplayer\multiplayer_update_thread.sco"
Remove-Item -LiteralPath $legacyTarget -Force -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path (Split-Path $TargetPath -Parent) | Out-Null
Copy-Item -Path $CompiledPath -Destination $TargetPath -Force

$hash = Get-FileHash -Path $TargetPath -Algorithm SHA1
$item = Get-Item $TargetPath
$manifest = [ordered]@{
    generated_at = (Get-Date).ToString('s')
    compiled_source = Rel $CompiledPath
    patch_root = Rel $PatchRootPath
    staged_target = Rel $TargetPath
    target_relative_path = $TargetRelativePath
    legacy_path_removed_if_present = "content\\multiplayer\\multiplayer_update_thread.sco"
    bytes = $item.Length
    sha1 = $hash.Hash
    first_16_bytes_hex = HeadHex $TargetPath 16
    expected_header = "53 43 52 02"
    probe_boundary = "Loader/asset-resolution proof only. This stub does not implement multiplayer, freeroam, session, auth, lobby, player-list, or net update behavior."
    install_warning = "Do not overwrite game files directly. Use this only as a patch-layer/import candidate after backing up archives."
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $ManifestPath -Encoding UTF8

$readme = @"
Code RED SCO Loader Probe
=========================

This folder mirrors the active extracted script tree path:

  $TargetRelativePath

The staged file is a tiny compiled RDR_SCO stub named multiplayer_update_thread.sco.
It only proves whether the active script loader can resolve/load an SCO asset for the
missing multiplayer_update_thread request path.

It is NOT a real multiplayer_update_thread implementation.
It does NOT initialize freeroam, sessions, lobbies, auth, player lists, or net state.

Expected header:
  53 43 52 02

Staged file:
  $(Rel $TargetPath)

SHA1:
  $($hash.Hash)

Use this only with a safe patch-layer/import workflow and backups. Do not overwrite
original game files directly.
"@
$readme | Set-Content -Path $ReadmePath -Encoding UTF8

Write-Host "# Code RED multiplayer_update_thread SCO probe staged"
Write-Host "Compiled source:" (Rel $CompiledPath)
Write-Host "Patch root:" (Rel $PatchRootPath)
Write-Host "Staged target:" (Rel $TargetPath)
Write-Host "Bytes:" $item.Length
Write-Host "Header:" (HeadHex $TargetPath 16)
Write-Host "Manifest:" (Rel $ManifestPath)
Write-Host "README:" (Rel $ReadmePath)
