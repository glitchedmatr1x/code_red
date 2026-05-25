param(
    [string]$CodeRedRoot = "D:\Games\Red Dead Redemption\Code_RED"
)

$ErrorActionPreference = "Stop"
$installer = Join-Path $CodeRedRoot "tools\codered_mp_freeroam_pass3_installer.py"

if (!(Test-Path $installer)) {
    throw "Installer not found: $installer"
}

$backup = "$installer.bak_resource_replace_fix"
if (!(Test-Path $backup)) {
    Copy-Item $installer $backup
}

$text = Get-Content $installer -Raw

$old = 'action, node = overlay.add_or_replace_file(wb, root, row["archive_path"], row["payload"], "replace")'
$new = 'action, node = overlay.add_or_replace_file(wb, root, row["archive_path"], row["payload"], "replace", allow_resource_replace=True)'

if ($text.Contains($new)) {
    Write-Host "Installer already has allow_resource_replace=True."
} elseif ($text.Contains($old)) {
    $text = $text.Replace($old, $new)
    Set-Content -Path $installer -Value $text -Encoding UTF8
    Write-Host "Patched installer:"
    Write-Host $installer
} else {
    throw "Could not find the expected add_or_replace_file call. Edit manually and add allow_resource_replace=True."
}

Write-Host ""
Write-Host "Now run:"
Write-Host "cd `"$CodeRedRoot`""
Write-Host "`$env:PYTHONPATH='.'"
Write-Host "py -3 tools\codered_mp_freeroam_pass3_installer.py"
