# Code RED Dynamite / Transport Car-Truck WSC Finder

Find likely dynamite, transport, escort, convoy, coach/wagon scripts and patch one selected WSC into cars/trucks.

## Status

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"
.\Run_CodeRED_DynamiteTransport_CarTruck_WSC.bat status
```

## Find candidates

Scans `imports` plus the exported deep-scan payloads if they exist:

```powershell
.\Run_CodeRED_DynamiteTransport_CarTruck_WSC.bat scan `
  --input-dirs imports `
  --include-deepscan `
  --out-dir logs\dynamite_transport_cartruck_scan `
  --terms dynamite transport escort convoy coach wagon stagecoach explosive crate crates ammo powder
```

Open:

```powershell
Import-Csv logs\dynamite_transport_cartruck_scan\dynamite_transport_scan.csv |
  Sort-Object {[int]$_.term_hits}, {[int]$_.vehicle_hits} -Descending |
  Select-Object -First 25 input,term_hits,vehicle_hits,id_counts_json,term_counts_json,sample_strings |
  Format-List
```

## Preview patch a chosen candidate

```powershell
.\Run_CodeRED_DynamiteTransport_CarTruck_WSC.bat patch `
  --input "PATH_FROM_SCAN" `
  --out patches\dynamite_transport_cartruck_preview.wsc `
  --mode car-truck `
  --old-low 1177 `
  --old-high 1202 `
  --int-format u16be `
  --max-replacements 32 `
  --preview-only
```

## Patch car/truck

```powershell
.\Run_CodeRED_DynamiteTransport_CarTruck_WSC.bat patch `
  --input "PATH_FROM_SCAN" `
  --out patches\dynamite_transport_cartruck.wsc `
  --mode car-truck `
  --old-low 1177 `
  --old-high 1202 `
  --int-format u16be `
  --max-replacements 32 `
  --allow-grow
```

Modes:

- `car-truck`: alternates `1193 Truck01`, `1194 Car01`
- `car-only`: replaces with `1194 Car01`
- `truck-only`: replaces with `1193 Truck01`

Safer direct-ID example:

```powershell
.\Run_CodeRED_DynamiteTransport_CarTruck_WSC.bat patch `
  --input "PATH_FROM_SCAN" `
  --out patches\dynamite_transport_selected_to_cartruck.wsc `
  --mode car-truck `
  --old-ids 1195 1196 1199 1200 1201 1202 `
  --int-format u16be `
  --max-replacements 32 `
  --preview-only
```

Do not test stacked patches. Use one candidate WSC at a time.
