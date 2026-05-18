# Code RED WSC Direct ID / Population Vehicle Patcher v4

This is a rollback-safe command-line tool for RDR1 RSC85 type-2 WSC scripts.

It is designed for the problem seen with population WSCs: those scripts may not store vehicle IDs the same way beat/event scripts do. This tool can scan both:

- actor IDs, such as `1197` for `WagonPrison01`
- trainer indexes, such as `20` when using the trainer formula `actor_id = index + 1177`

It scans multiple binary formats and writes CSV previews before patching.

## Setup

Place this drop-in at the root of Code RED.

Set the real game executable, not `PlayRDR.exe`:

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"
```

Install dependencies if needed:

```powershell
.\install_wsc_direct_id_deps.bat
```

## Scan arm_population.wsc

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat population-scan `
  --input imports\arm_population.wsc `
  --out logs\wsc_direct_id\arm_population_population_scan
```

Open:

```text
logs\wsc_direct_id\arm_population_population_scan\arm_population\arm_population.wsc.summary.csv
```

## Preview a population patch

Default old IDs are carts/wagons/coaches:

```text
1183-1188, 1195-1202
```

Preview replacing them with `1194 Car01`:

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat population-patch `
  --input imports\arm_population.wsc `
  --out patches\arm_population_population_to_car_preview.wsc `
  --target-id 1194 `
  --preview-only `
  --max-replacements 16
```

The tool auto-selects a low-count candidate from actor/index encodings and writes `.preview_hits.csv`.

## Patch if preview is reasonable

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat population-patch `
  --input imports\arm_population.wsc `
  --out patches\arm_population_population_to_car.wsc `
  --target-id 1194 `
  --max-replacements 16
```

## Mixed Truck/Car target

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat population-patch `
  --input imports\arm_population.wsc `
  --out patches\arm_population_population_to_truck_car.wsc `
  --target-ids 1193 1194 `
  --max-replacements 16
```

## Batch preview all WSCs

```powershell
.\Run_CodeRED_WSC_Direct_ID_Patcher.bat batch-population-patch `
  --input-dir imports `
  --out-dir logs\wsc_direct_id\batch_population_preview `
  --target-id 1194 `
  --preview-only `
  --max-replacements 16
```

## Safety notes

This tool does not patch ASCII digit chains. It patches decoded binary constants only after AES + Zstandard decode.

It blocks files with too many matches. Increase `--max-replacements` only after reviewing the `.preview_hits.csv` report.

If an output is variable-size, inject it with an RPF path that updates entry size/TOC. Do not raw-overwrite fixed-size slots.
