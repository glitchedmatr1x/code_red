# Code RED Car1194 WagonThief WSC Kit

Purpose: focus on `beat_crime_wagonthief.wsc` as the first active vehicle-script target and use the confirmed car model/value `1194` only.

This is **not** a blind WSC rewrite. It is a guarded local builder:

- reads `imports\beat_crime_wagonthief.wsc`
- parses the RSC header
- tries the script-resource unlock/decompress path when the local game executable/key is available
- scans for 32-bit constants
- only patches old IDs that you explicitly pass with `--old-id`
- writes a staged output under `patches\`, never overwrites the source

Why beat crime wagon thief?

Your refgroup placement already proves `Car01x` can appear as a placed asset, but that still behaves like a loose prop. The wagon thief beat is more promising because it already uses active wagon/vehicle theft gameplay. If we can safely change the active vehicle/template/model id in that script to `1194`, it is a cleaner test than static placement.

## Commands

Status:

```powershell
.\Run_CodeRED_Car1194_WagonThief_WSC.bat status
```

Analyze:

```powershell
.\Run_CodeRED_Car1194_WagonThief_WSC.bat analyze --input imports\beat_crime_wagonthief.wsc --out logs\car1194_wagonthief_wsc\analyze
```

Make a plan:

```powershell
.\Run_CodeRED_Car1194_WagonThief_WSC.bat plan --input imports\beat_crime_wagonthief.wsc --out logs\car1194_wagonthief_wsc\plan
```

Patch only when you know a wagon/coach/cart old ID:

```powershell
.\Run_CodeRED_Car1194_WagonThief_WSC.bat patch-u32 --input imports\beat_crime_wagonthief.wsc --old-id OLD_ID_HERE --new-id 1194 --out patches\beat_crime_wagonthief_car1194.wsc
```

You can pass multiple old IDs:

```powershell
.\Run_CodeRED_Car1194_WagonThief_WSC.bat patch-u32 --input imports\beat_crime_wagonthief.wsc --old-id 123 456 789 --new-id 1194 --out patches\beat_crime_wagonthief_car1194.wsc
```

## Guardrails

- Does not guess the truck id.
- Does not guess old wagon IDs.
- Does not mutate `imports\beat_crime_wagonthief.wsc`.
- Does not claim full WSC decompile/recompile.
- Direct WSC editing is blocked unless the script resource can be opened safely.
