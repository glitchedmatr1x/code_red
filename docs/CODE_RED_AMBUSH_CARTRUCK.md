# Code RED Roadside Ambush Car/Truck WSC Patcher

Purpose: patch `imports\event_roadside_ambush.wsc` with the same careful method that worked on WagonThief: decode RSC85 type-2 WSC, patch exact decoded binary vehicle actor IDs, repack, re-encrypt, and validate.

Default patch:

- old range: `1177..1188` stagecoach/cart/gatling/cart lane
- new range: `1193..1194`
- mapping: alternating `1193 Truck01`, `1194 Car01`
- integer format: `u16be`
- original file is never modified

## Commands

Install dependencies once:

```powershell
.\install_ambush_cartruck_wsc_deps.bat
```

Set the RDR exe path:

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"
```

Check status:

```powershell
.\Run_CodeRED_Ambush_CarTruck_WSC.bat status
```

Decode-scan first:

```powershell
.\Run_CodeRED_Ambush_CarTruck_WSC.bat decode-scan `
  --input imports\event_roadside_ambush.wsc `
  --out logs\ambush_cartruck_wsc\decode_scan
```

Preview the exact binary replacements:

```powershell
.\Run_CodeRED_Ambush_CarTruck_WSC.bat patch `
  --input imports\event_roadside_ambush.wsc `
  --out patches\event_roadside_ambush_1177_1188_to_1193_1194_preview.wsc `
  --mode binary-range `
  --int-format u16be `
  --preview-only
```

Write the patched WSC:

```powershell
.\Run_CodeRED_Ambush_CarTruck_WSC.bat patch `
  --input imports\event_roadside_ambush.wsc `
  --out patches\event_roadside_ambush_1177_1188_to_1193_1194.wsc `
  --mode binary-range `
  --int-format u16be
```

## Testing rule

Test this ambush patch by itself first. Do not stack it with population patches or short-update seat-unlock guesses. If needed, combine only with the known-good WagonThief truck patch after each works alone.
