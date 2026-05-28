# Pass 3 Installer Resource Replace Fix

The original installer failed on:

`Refusing to replace resource entry without explicit allow_resource_replace`

That is expected for `.wsc` resources. The Code RED overlay builder requires an explicit safety flag for replacing existing RSC85 resource entries.

Run one of these from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\Fix-Pass3InstallerResourceReplace.ps1
```

or:

```powershell
py -3 .\fix_pass3_installer_resource_replace.py
```

Then rerun:

```powershell
cd "%RDR_GAME_DIR%\Code_RED"
$env:PYTHONPATH='.'
py -3 tools\codered_mp_freeroam_pass3_installer.py
```
