# CodeRED Terrainboundres Validation Lane Pass

Date: 2026-05-03

## Scope

This pass closes the last one-app proof-gated lane without pretending terrain editing is fully solved.

The lane now proves terrainboundres readiness from inside Code RED by validating a staged `terrainboundres.rpf` with inventory and WTB decode checks. The validator is read-only and does not patch source archives.

## Added

```text
tools/codered_terrainboundres_validation.py
```

The validator:

- finds `terrainboundres.rpf` in `imports/`, `game/`, or repo root unless `--archive` is supplied
- imports and uses `tools/codered_terrainboundres_tool.py`
- builds a terrainboundres inventory
- decodes a small WTB sample set
- verifies nonzero entries/files/WTB tiles/territory count
- verifies decoded WTB samples pass
- writes compact proof reports:
  - `logs/CodeRED_Terrainboundres_Validation_Report.json`
  - `logs/CodeRED_Terrainboundres_Validation_Report.md`

## Updated

```text
python_workbench.py
codered_app/launcher_registry.py
```

Dashboard and toolbar now include:

```text
Validate Terrain
```

The one-app registry now points the Terrainboundres lane at the validator instead of the lower-level terrain tool directly.

## Proof Result

Using a staged uploaded `imports/terrainboundres.rpf`:

```text
Result: PASS
Entries: 5381
Files: 5378
WTB tiles: 5376
TXT sidecars: 2
Territories: 1
Decoded samples: 5
Decoded OK: 5
Decoded failed: 0
Grid: x=1024..7616 y=6656..11712 cell=64
```

## One-App Status

```text
Ready: 16
Ready but needs proof: 0
Missing required files: 0
Weighted readiness: 100%
```

## Important Limitation

This pass proves the terrainboundres tool lane can parse, inventory, and decode WTB samples. It does not claim arbitrary semantic WTB editing is complete.

Safe editing remains:

```text
copied archive only
patch-folder
patch-wtb-bytes
re-read verification
```

## Fully Consumed / Obsolete

No new source file was fully consumed and made obsolete in this pass.

Carry-forward obsolete items remain removed:

```text
run_workbench.py
__pycache__/
```

## Validation Commands

```text
python3 -m py_compile main.py python_workbench.py codered_app/__init__.py codered_app/paths.py codered_app/launcher_registry.py tools/codered_one_app_status.py tools/codered_ai_trainer_validation.py tools/codered_terrainboundres_validation.py tools/codered_terrainboundres_tool.py
python3 tools/codered_terrainboundres_validation.py --decode-samples 5
python3 tools/codered_one_app_status.py --write
python3 main.py --dry-run
python3 main.py --one-app-status
```
