# Code RED WSC Direct ID Patcher v3

Purpose: patch exact decoded binary vehicle actor IDs in RSC85 type-2 WSC scripts.

This is not the broad GUI workflow. It is a controlled script lane:

- decode RSC85 type-2 script
- AES key from `rdr.exe`
- Zstandard decompress
- scan exact binary IDs in one integer format, usually `u16be`
- preview hits with offset/context CSVs
- patch only explicit old IDs to one target ID
- repack/re-encrypt
- validate decode after writing

## Known vehicle IDs

- 1193 = Truck01
- 1194 = Car01
- 1197 = WagonPrison01

Full trainer range: 1177-1202.

## Single file scan

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat scan --input imports\event_roadside_prisoners.wsc --old-ids 1197 --int-format u16be --out logs\wsc_direct_id\prisoners_1197_scan
```

## Single file patch

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat patch-id --input imports\event_roadside_prisoners.wsc --out patches\event_roadside_prisoners_1197_to_car.wsc --old-ids 1197 --target-id 1194 --int-format u16be --max-replacements 8
```

## Batch scan every WSC in imports

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat batch-scan --input-dir imports --out-dir logs\wsc_direct_id\batch_scan_all_vehicles --range-low 1177 --range-high 1202 --int-format u16be
```

## Batch preview direct ID replacements

Preview all files before writing patched WSCs:

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat batch-patch-id --input-dir imports --out-dir logs\wsc_direct_id\batch_preview_1197_to_car --old-ids 1197 --target-id 1194 --int-format u16be --max-replacements 8 --preview-only
```

## Batch patch direct ID replacements

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat batch-patch-id --input-dir imports --out-dir patches\wsc_direct_id_batch_1197_to_car --old-ids 1197 --target-id 1194 --int-format u16be --max-replacements 8
```

## Guardrails

- Batch patch requires explicit `--old-ids`.
- It skips files with no hits.
- It blocks files with more than `--max-replacements` hits.
- It validates the rewritten WSC before reporting success.
- It never modifies originals in `imports`.
