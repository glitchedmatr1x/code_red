# Code RED Script Patch Workbench

`codered_script_patch_workbench.py` is the index-first patch lane for hash-only
`content.rpf` work. It is designed for safe inspection, same-size patching,
RSC85/WSC rebuild validation, and copied-RPF variant creation.

It does not overwrite the original archive.

## Inspect an Entry

```powershell
python tools\codered_sco_probe\codered_script_patch_workbench.py inspect-entry `
  --rpf "D:\Games\Red Dead Redemption\game\content.rpf" `
  --index 885 `
  --out build\script_workbench\inspect_885
```

Outputs include:

- `entry_885.bin`
- `decoded_payload.bin` when RSC85 decode succeeds
- `strings.csv`
- `numeric_constants.csv`
- `inspect_report.json`
- `inspect_report.md`

Decoded payloads and extracted entries must stay under `build/`.

## Make a Recipe

```powershell
python tools\codered_sco_probe\codered_script_patch_workbench.py make-patch-recipe `
  --index 885 `
  --out build\script_workbench\entry_885.recipe.json
```

Edit the generated JSON or start from one of:

- `tools/codered_sco_probe/patch_examples/playercar_index_885_safe.recipe.json`
- `tools/codered_sco_probe/patch_examples/rdr2init_index_272_probe.recipe.json`
- `tools/codered_sco_probe/patch_examples/pause_cheat_menu_scan.recipe.json`

## Apply a Recipe

```powershell
python tools\codered_sco_probe\codered_script_patch_workbench.py apply-patch-recipe `
  --rpf "D:\Games\Red Dead Redemption\game\content.rpf" `
  --index 885 `
  --recipe tools\codered_sco_probe\patch_examples\playercar_index_885_safe.recipe.json `
  --out build\script_workbench\patch_885_playercar
```

For RSC85/WSC entries, the workbench patches the decoded payload and then
rebuilds the RSC85 resource. Re-decode validation must pass before the patched
entry should be imported.

For SCO/raw entries, the first supported lane is same-size raw patching only.

## Build a Copied RPF Variant

```powershell
python tools\codered_sco_probe\codered_script_patch_workbench.py build-rpf-variant `
  --rpf "D:\Games\Red Dead Redemption\game\content.rpf" `
  --index 885 `
  --patched-entry build\script_workbench\patch_885_playercar\entry_885_patched.bin `
  --out build\script_workbench\variants\content_playercar_885_probe.rpf
```

The output path must be under a `build` directory. The original `content.rpf`
is refused as an output target.

## Why Index-Based Replacement

This PC `content.rpf` often exposes hash-only paths. Index replacement avoids
guessing unresolved names and keeps every experiment tied to the exact backend
entry that was inspected.

## Required Safety Order

1. Run `bulk-scan-rpf-scripts` to find candidates.
2. Run `inspect-entry` on the candidate index.
3. Run a no-change replacement with `codered_sco_probe.py`.
4. Apply a same-size recipe.
5. Re-decode/reopen the patched entry.
6. Build a copied RPF variant only after validation.

## Current Limits

- Length-changing strings are blocked.
- Adding or removing WSC code blocks is blocked until bytecode reassembly exists.
- Native call patching is report-only unless instruction boundaries and stack
  effects are proven.
- SCO starts with raw same-size patches only.
