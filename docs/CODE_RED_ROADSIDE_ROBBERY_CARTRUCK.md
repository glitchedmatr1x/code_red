# Code RED Roadside Robbery Car/Truck WSC Patcher v3

Targets `beat_roadside_robbery.wsc`.

v3 fix:
- fixes `direct-ids` crash: `NameError: VEHICLE_NAMES is not defined`
- keeps direct ID vehicle labels embedded locally
- does not overwrite the population Direct ID patcher

Preferred selective car-only Roadside Robbery test:

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"

.\Run_CodeRED_Roadside_Robbery_CarTruck_WSC.bat patch `
  --input imports\beat_roadside_robbery.wsc `
  --out patches\beat_roadside_robbery_wagons_coach_to_car_preview.wsc `
  --mode direct-ids `
  --old-ids 1195 1196 1199 1202 `
  --target-id 1194 `
  --int-format u16be `
  --max-replacements 96 `
  --preview-only

.\Run_CodeRED_Roadside_Robbery_CarTruck_WSC.bat patch `
  --input imports\beat_roadside_robbery.wsc `
  --out patches\beat_roadside_robbery_wagons_coach_to_car.wsc `
  --mode direct-ids `
  --old-ids 1195 1196 1199 1202 `
  --target-id 1194 `
  --int-format u16be `
  --max-replacements 96 `
  --allow-grow
```

Leaves untouched by default in that command:
- `1197 WagonPrison01`
- `1198 WagonGatling01`
