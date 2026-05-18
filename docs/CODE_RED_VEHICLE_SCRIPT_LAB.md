# Code RED Vehicle Script Lab v3

Read-first vehicle/script research lane for Code RED.

## Purpose

The refgroup tests can place `car01x` and `truck01x` visually, but they behave like loose props. That means the missing layer is probably script/template/tune activation rather than only WFT geometry.

Priority targets:

- `playercar.wsc`
- `beat_crime_wagonthief.wsc`
- `gen_vehicle_brain.wsc`
- `vehicle_generator.wsc`
- `template_vehicle*.xml`
- `*.vehsim`, `*.vehmodel`, `*.vehinput`, `*.vehgyro`, `*.vehstuck`

## What v3 adds

- Keeps v2 SHA256, duplicate detection, and `find-rpf`.
- Adds humanish string filtering so accidental bytecode printable runs are separated from useful labels.
- Adds WSC byte profiles: entropy chunks, common aligned u32 constants, prefix bytes, and profile reports.
- Adds `profile-wsc` for direct compiled-script structure triage.

## What this does not claim

It does not claim full `.wsc` decompile/recompile. It does not rewrite scripts. It does not edit source RPFs.

## Commands

Status:

```bat
.\Run_CodeRED_Vehicle_Script_Lab.bat
```

Find the real priority scripts inside `content.rpf`:

```bat
.\Run_CodeRED_Vehicle_Script_Lab.bat find-rpf --archive game\content.rpf --query playercar beat_crime_wagonthief wagonthief vehicle_generator gen_vehicle_brain --extract --out logs\vehicle_script_lab\script_finder
```

Scan scripts directly from an RPF:

```bat
.\Run_CodeRED_Vehicle_Script_Lab.bat scan-rpf --archive game\content.rpf --out logs\vehicle_script_lab\content_scripts
```

Compare two extracted scripts:

```bat
.\Run_CodeRED_Vehicle_Script_Lab.bat compare --left imports\playercar.wsc --right imports\beat_crime_wagonthief.wsc --out logs\vehicle_script_lab\playercar_vs_wagonthief
```

Create an ASI scaffold:

```bat
.\Run_CodeRED_Vehicle_Script_Lab.bat make-asi-scaffold --out asi\CodeREDVehicleBridge
```

## Output files

For each scanned file:

- `*.strings.csv` — ASCII and UTF-16LE printable strings
- `*.target_hits.csv` — direct string/hash hits for vehicle targets
- `*.hash_probe.csv` — Jenkins hash probes
- `*.summary.json` — scan summary with SHA256
- `*.report.md` — readable report

For `find-rpf`:

- `script_candidates.csv`
- `script_candidates_summary.json`
- optional `candidates/` extraction folder

## Guardrails

- Source RPFs are not modified.
- WSC full decompile/recompile is not claimed.
- Hash hits are research clues, not proof of control flow.
- Behavior changes should move to an ASI/ScriptHook lane unless full script rebuild is proven.

Profile a WSC without comparing it:

```bat
.\Run_CodeRED_Vehicle_Script_Lab.bat profile-wsc --input imports\playercar.wsc --out logs\vehicle_script_lab\playercar_profile
```
