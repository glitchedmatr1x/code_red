# Code RED Terrainboundres Tooling Changelog

Date: 2026-04-30

## Summary

Code RED now has a focused terrain-bound workflow for `D:\Games\Red Dead Redemption\game\terrainboundres.rpf`.

The new lane can inventory `terrainboundres.rpf`, decode `.wtb` RSC05/zstd payloads for inspection, export patchable raw archive entries, apply edited `.wtb` files to a copied RPF, patch decoded WTB bytes for controlled experiments, and route `.wtb` files in the Code RED workbench as World assets.

## Files Added Or Updated

- `tools/codered_terrainboundres_tool.py` - new CLI for `inventory`, `inspect`, `export`, `patch-folder`, and `patch-wtb-bytes`.
- `python_workbench.py` - added `.wtb` World routing, Python `zstandard` streaming decode, tile metadata, payload SHA1, candidate strings, float3 samples, and WTB validation for RSC resource type `36`.
- `logs/terrainboundres_inventory/` - generated live inventory reports for the current `terrainboundres.rpf`.

## Live Archive Findings

- Target: `D:\Games\Red Dead Redemption\game\terrainboundres.rpf`
- Entries: 5,381
- Files: 5,378
- WTB terrain-bound tiles: 5,376
- TXT sidecars: 2
- Territory folder: `territory_swall_noid`
- Grid extent guess: `x=1024..7616`, `y=6656..11712`, cell size `64`

Generated reports:

- `logs/terrainboundres_inventory/terrainboundres_inventory.md`
- `logs/terrainboundres_inventory/terrainboundres_inventory.json`
- `logs/terrainboundres_inventory/terrainboundres_entries.csv`
- `logs/terrainboundres_inventory/terrainboundres_wtb_tiles.csv`
- `logs/terrainboundres_inventory/terrainboundres_txt_sidecars.csv`

## Usage

Inventory:

```powershell
& 'C:\Users\glitc\AppData\Local\Programs\Python\Python312\python.exe' 'D:\Games\Red Dead Redemption\Code_RED\tools\codered_terrainboundres_tool.py' inventory 'D:\Games\Red Dead Redemption\game\terrainboundres.rpf' --outdir 'D:\Games\Red Dead Redemption\Code_RED\logs\terrainboundres_inventory'
```

Inspect one tile:

```powershell
& 'C:\Users\glitc\AppData\Local\Programs\Python\Python312\python.exe' 'D:\Games\Red Dead Redemption\Code_RED\tools\codered_terrainboundres_tool.py' inspect 'D:\Games\Red Dead Redemption\game\terrainboundres.rpf' '08c022c0_bnd.wtb'
```

Export patchable raw WTB files plus decoded payload copies:

```powershell
& 'C:\Users\glitc\AppData\Local\Programs\Python\Python312\python.exe' 'D:\Games\Red Dead Redemption\Code_RED\tools\codered_terrainboundres_tool.py' export 'D:\Games\Red Dead Redemption\game\terrainboundres.rpf' --outdir 'D:\Games\Red Dead Redemption\Code_RED\reports\terrainboundres_export' --wtb-only --decoded-payloads
```

Apply edited `.wtb` files to a copied archive:

```powershell
& 'C:\Users\glitc\AppData\Local\Programs\Python\Python312\python.exe' 'D:\Games\Red Dead Redemption\Code_RED\tools\codered_terrainboundres_tool.py' patch-folder 'D:\Games\Red Dead Redemption\game\terrainboundres.rpf' 'D:\Games\Red Dead Redemption\Code_RED\reports\terrainboundres_export\terrainboundres_contents'
```

Patch decoded WTB bytes into a copied archive:

```powershell
& 'C:\Users\glitc\AppData\Local\Programs\Python\Python312\python.exe' 'D:\Games\Red Dead Redemption\Code_RED\tools\codered_terrainboundres_tool.py' patch-wtb-bytes 'D:\Games\Red Dead Redemption\game\terrainboundres.rpf' '08c022c0_bnd.wtb' --offset 0 --hex b8 --out 'D:\Games\Red Dead Redemption\Code_RED\reports\terrainboundres_patch_test\terrainboundres_test_copy.rpf'
```

## Validation

- `python -m py_compile` passed for `tools/codered_terrainboundres_tool.py` and `python_workbench.py`.
- Live inventory generation completed against `terrainboundres.rpf`.
- One copied-archive byte-patch smoke test completed and verified by re-reading the patched `.wtb` entry.
- The smoke test used a no-op decoded byte replacement at offset `0`; the re-compressed resource relocated to an appended span and verified successfully.

## Current Editing Guardrails

- The original `terrainboundres.rpf` is never modified.
- `patch-folder` and `patch-wtb-bytes` always write copied archives.
- `.wtb` replacements must stay RSC05 resource type `36`.
- Decoded WTB payload size must stay equal to the original decoded payload size.
- If a replacement compresses larger than the original slot, the copied archive relocates the resource to an appended 2048-byte-aligned span and updates the TOC.
- Full semantic terrain-bound structure editing is still research-only; current edits are byte/resource replacement with validation.
