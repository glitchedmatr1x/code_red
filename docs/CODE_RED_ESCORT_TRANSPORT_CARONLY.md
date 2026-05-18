# Code RED Escort/Transport Car-Only WSC Patcher

Target: escort/transport WSC files in `imports`.

Default patch: decoded binary `u16be` actor IDs in `1177..1202` become `1194 Car01` only.

This is intentionally not a broad GUI patch. Preview first, then test one event at a time.

## Install

Unzip into:

```text
D:\Games\Red Dead Redemption\Code_RED
```

Install deps once:

```powershell
.\install_escort_transport_caronly_wsc_deps.bat
```

Set the RDR executable path:

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"
```

## Status

```powershell
.\Run_CodeRED_EscortTransport_CarOnly_WSC.bat status
```

## Find escort / transport files in imports

```powershell
.\Run_CodeRED_EscortTransport_CarOnly_WSC.bat batch-scan `
  --input-dir imports `
  --out-dir logs\escort_transport_caronly_wsc\batch_scan `
  --terms escort transport
```

Review:

```powershell
Import-Csv logs\escort_transport_caronly_wsc\batch_scan\batch_scan_summary.csv | Format-Table -AutoSize
```

## Preview patch for every detected escort / transport file

```powershell
.\Run_CodeRED_EscortTransport_CarOnly_WSC.bat batch-patch `
  --input-dir imports `
  --out-dir patches\escort_transport_caronly_preview `
  --terms escort transport `
  --target-id 1194 `
  --int-format u16be `
  --max-replacements 48 `
  --preview-only
```

## Write patches after preview

```powershell
.\Run_CodeRED_EscortTransport_CarOnly_WSC.bat batch-patch `
  --input-dir imports `
  --out-dir patches\escort_transport_caronly `
  --terms escort transport `
  --target-id 1194 `
  --int-format u16be `
  --max-replacements 48 `
  --allow-grow
```

## Patch one known file

```powershell
.\Run_CodeRED_EscortTransport_CarOnly_WSC.bat patch `
  --input imports\event_roadside_escort.wsc `
  --out patches\event_roadside_escort_caronly.wsc `
  --target-id 1194 `
  --int-format u16be `
  --preview-only
```

Then rerun without `--preview-only`.

## Safety notes

- Originals are never modified.
- It patches exact decoded binary integers only.
- It does not replace ASCII digit chains.
- It blocks too many replacements unless `--allow-many` is set.
- `--allow-grow` writes a variable-size WSC only when exact-size fit is impossible; use an RPF importer that updates size metadata.
