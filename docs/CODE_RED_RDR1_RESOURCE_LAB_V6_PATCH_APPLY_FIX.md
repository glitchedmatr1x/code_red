# Code RED RDR1 Resource Lab v6 Patch-Archive Fix

This pass fixes the `patch-archive` failure where the copied-archive backend could crash with a raw `shutil.copy2` / `CopyFile2` traceback when the requested output folder did not already exist.

## Fixed

- `patch-archive` now creates the output archive parent folder before delegating to Code RED's copied-archive patch backend.
- `patch-archive` now fails early with a readable message when the source RPF is missing.
- `patch-archive` now fails early with a readable message when the patch root is missing or empty.
- If the existing Code RED backend still fails, the wrapper explains that the internal staged path should be checked against `rpf-inventory`.

## Typical command

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat patch-archive --archive game\gringores.rpf --patch-root patches\wgd_lasso_override --out game\patched\gringores.rpf
```

If `game\gringores.rpf` is not actually in the Code RED `game` folder, either copy it there or pass the full path to your RPF.
