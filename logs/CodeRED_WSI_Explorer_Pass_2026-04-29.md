# Code RED — WSI Explorer Pass Notes

Date: 2026-04-29

This pass adds the first practical territory-resource tool from the WSI/CodeX research lane:

```text
tools/codered_wsi_explorer.py
```

## What this pass adds

- RPF6 inventory reading.
- Optional encrypted TOC handling using Python `cryptography` or the `openssl` CLI fallback.
- Debug-name recovery when the archive contains a debug name table.
- RSC6 resource extraction for `.wsi` entries.
- RSC zstd decode/recompress using Python `zstandard` or the `zstd` CLI fallback.
- RDR/JOOAT hash generation.
- Hash-name import from text/hash/csv files.
- WSI string scan, virtual pointer scan, hash-hit scan, sector-info VFT scan, and vector candidate scan.
- CSV/JSON export for scanned WSI resources.
- Safe copy-only decoded-byte patching for `.wsi` resources.
- Rebuild verification by reopening the patched RPF and decoding the target WSI again.

## Safety rules implemented

The patch command refuses in-place archive writes. It always writes a new output archive.

RSC replacement uses the rule found during the territory research pass:

```text
- preserve 12-byte RSC header
- decode zstd payload
- patch decoded payload bytes
- recompress zstd payload
- append replacement resource at 2048-byte alignment
- update TOC size and offset metadata
- reopen archive
- decode target resource again
- verify decoded bytes match the intended patch
```

## Requirements

Recommended Python packages:

```text
cryptography
zstandard
```

Fallback tools if those packages are missing:

```text
openssl
zstd
```

## Usage examples

Inventory an RPF:

```bat
py -3 tools\codered_wsi_explorer.py inventory path\to\blackwater.rpf --out exports\blackwater_inventory.json
```

Scan every WSI in an RPF:

```bat
py -3 tools\codered_wsi_explorer.py scan-wsi path\to\blackwater.rpf --outdir exports\blackwater_wsi_scan
```

Scan one WSI and import extra names from a string database folder:

```bat
py -3 tools\codered_wsi_explorer.py scan-wsi path\to\blackwater.rpf --path root/blackwater/blackwater.wsi --names path\to\RAGE-StringsDatabase --outdir exports\blackwater_wsi_scan
```

Patch a decoded WSI byte range into a copied archive:

```bat
py -3 tools\codered_wsi_explorer.py patch-wsi-bytes path\to\dlc03x.rpf root/dlc03x/0xA79C05A9/dlc03x.wsi --offset 0x40 --hex 00 --out exports\dlc03x_patch_test.rpf --proof exports\dlc03x_patch_proof.json
```

Only use decoded-byte patching for controlled tests until the semantic WSI structure is ported.

## Local proof before commit

The tool was tested locally against extracted sample archives from the uploaded territory resources:

```text
dlc03x.rpf
- inventory succeeded
- WSI decode succeeded
- scan JSON/CSV exports succeeded
- copy-only decoded-byte patch succeeded
- reopened patched RPF verified decoded payload

blackwater.rpf
- inventory succeeded
- blackwater.wsi decoded successfully
- hash-hit CSV exported
- vec3 candidate CSV exported
```

## What this does not solve yet

- It does not fully edit `.wvd` models.
- It does not fully edit `.wbd` collisions.
- It does not fully parse all WSI records semantically yet.
- It does not convert RDR1 W-resources to GTA V Y-resources.

## Next pass targets

Highest priority:

```text
1. Port the CodeX Rsc6SectorInfo / sagSectorInfo reader structure into Python.
2. Add real WSI sector hierarchy export instead of heuristic VFT/vector scans.
3. Export fields such as Name, Scope, NameHash, ScopedNameHash, BoundMin, BoundMax, Props, DrawableInstances, Locators, ChildGroup, and Flags.
4. Add coordinate-only semantic patching once the field offsets are confirmed from the structure reader.
5. Add optional batch import/cache for OpenIV RAGE-StringsDatabase names.
```

Risk rule:

```text
Do not pretend WVD/WBD are fully editable yet. WSI is the first safe semantic target.
```
