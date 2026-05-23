# Code RED WagonThief Car/Truck WSC Patcher

Purpose: patch `beat_crime_wagonthief.wsc` so the vehicle selection that used wagon/cart/coach actor IDs can be narrowed to the trainer-proven car/truck IDs.

Confirmed trainer vehicle IDs:

```text
1183 Cart01
1184 Cart02
1185 Cart003
1186 Cart004
1187 Cart005
1188 Cart006
1189 Canoe01
1190 Raft02
1191 Raft03
1192 Raft01
1193 Truck01
1194 Car01
1195 Wagon04
1196 Wagon05
1197 WagonPrison01
1198 WagonGatling01
1199 Wagon02
1200 Chuckwagon
1201 Chuckwagon02
1202 Coach01
```

This tool targets the `1183..1197 -> 1193..1194` test range for the wagon thief script.

## Important finding

The decoded WSC payload does **not** contain standalone ASCII four-digit tokens like `1188`. The numbers are stored as decoded binary constants. Use `ascii-isolated-range` only to prove that there are no literal text tokens. For real patching, use `binary-range` with `u16be` unless a later scan proves a different format.

## Commands

Check key access:

```powershell
.\Run_CodeRED_WagonThief_CarTruck_WSC.bat status
```

Decode and scan:

```powershell
$env:CODERED_RDR_EXE="D:\Games\Red Dead Redemption\rdr.exe"
.\Run_CodeRED_WagonThief_CarTruck_WSC.bat decode-scan --input imports\beat_crime_wagonthief.wsc --out logs\wagonthief_cartruck_wsc\decode_scan_v6
```

Recommended individual-ID patch:

```powershell
.\Run_CodeRED_WagonThief_CarTruck_WSC.bat patch --mode binary-range --int-format u16be --input imports\beat_crime_wagonthief.wsc --out patches\beat_crime_wagonthief_binary_1183_1197_to_1193_1194.wsc
```

Optional: map everything to car only:

```powershell
.\Run_CodeRED_WagonThief_CarTruck_WSC.bat patch --mode binary-range --int-format u16be --range-map high --input imports\beat_crime_wagonthief.wsc --out patches\beat_crime_wagonthief_binary_1183_1197_to_car1194.wsc
```

Previous bounds-only patch:

```powershell
.\Run_CodeRED_WagonThief_CarTruck_WSC.bat patch --mode bounds --input imports\beat_crime_wagonthief.wsc --out patches\beat_crime_wagonthief_1183_1197_to_1193_1194.wsc
```

## Safety behavior

- No source file is overwritten.
- Requires the RDR1 AES key from `rdr.exe` for RSC85 type-2 script resources.
- Decrypts, Zstandard-decompresses, patches, recompresses, encrypts, then validates the output by decoding it again.
- `binary-range` patches complete decoded binary integer operands only; it does not replace digit substrings or longer number chains.
- Reports before/after counts by integer format and value so you can verify undesired values were reduced.
