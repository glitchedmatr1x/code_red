# Code RED One-App Registry Pass

Date: 2026-05-03

## Goal

Begin moving Code RED toward one app by adding a modular lane registry instead of adding more root launchers or more logic directly into `python_workbench.py`.

## Added

```text
codered_app/__init__.py
codered_app/paths.py
codered_app/launcher_registry.py
tools/codered_one_app_status.py
```

## Updated

```text
main.py
```

Added:

```text
--one-app-status
```

This prints the current one-app lane registry/status report without opening the Tk UI.

## Lanes Registered

- Code RED Workbench
- Repo Doctor
- Build Assistant
- AI Trainer / ScriptHookRDR Menu
- Trainer AI Controller
- Native Probe / Bridge Prep
- Script Compile Lab
- RPF Edit Lab
- CodeX / Model XML Bundle Helpers
- WFT / RSC5 Edit Bridge
- WSI / Map / Gringo Tools
- Terrainboundres Tools
- Vehicle / Gringo Research
- CodeRED Tuner / Arcade
- MP Companion
- Logs / Research Browser

## Current Status

Generated:

```text
logs/one_app_status/one_app_lane_status.md
logs/one_app_status/one_app_lane_status.json
```

Current status from this extracted package:

```text
Ready: 14
Ready but needs proof: 2
Missing required files: 0
Weighted readiness: 94%
```

The score does not claim 100% until proof-gated lanes have proof logs. Ready-but-unproven lanes count only halfway.

## Fully Salvaged / Obsolete Removed

```text
run_workbench.py
```

Already removed in the launcher unification pass. Its useful MP Companion detection behavior is now in `main.py --legacy-companion-workspace`.

## Not Removed Yet

No related app was deleted in this pass. These lanes are not yet 100% consumed by the one-app registry because their UI/actions are not fully embedded; the registry only discovers and launches them cleanly.

## Test Commands

```bat
py -3 -m py_compile main.py python_workbench.py codered_app\__init__.py codered_app\paths.py codered_app\launcher_registry.py tools\codered_one_app_status.py
py -3 main.py --dry-run
py -3 main.py --one-app-status
py -3 tools\codered_one_app_status.py --write
```

## Result

Code RED now has the first real one-app foundation:

```text
main.py -> old workbench host + modular codered_app lane registry
```

The next pass should add a real app dashboard tab/panel that reads this registry instead of only printing it from the command line.
