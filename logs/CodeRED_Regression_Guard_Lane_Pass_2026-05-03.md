# CodeRED Regression Guard Lane Pass

Date: 2026-05-03

## Goal

Add a first-class regression guard to Code RED so checkpoint zips can be used as baselines while the app continues absorbing Script Lab, Magic-RDR, CodeX, and related workflows.

## Added

```text
tools/codered_regression_guard.py
```

## Updated

```text
python_workbench.py
codered_app/launcher_registry.py
```

## New UI action

```text
Regression Guard
```

Added to the dashboard and top toolbar.

## What it checks

- Compares the current tree against an older `Code_RED.zip` or folder baseline.
- Flags unexpected removed files.
- Allows only declared fully consumed obsolete removals.
- Fails if obsolete files are still present and likely to get pulled back into workflow.
- Checks critical one-app files and validators.
- Scans discovered source folders and verifies text/source decode.
- Writes JSON, Markdown, and CSV manifest outputs.

## Current proof

Baseline:

```text
/mnt/data/Code_RED.zip
```

Result:

```text
PASS
Current files: 734
Baseline files: 656
Added: 79
Changed: 3
Removed: 1
Intentional obsolete removals: 1
Unexpected removals: 0
Critical missing: 0
Obsolete present: 0
Source dirs: 5
Source files decoded: 11/11
```

## Fully consumed / obsolete confirmed

```text
run_workbench.py
```

Reason: its useful MP Companion workspace behavior was salvaged into `main.py` through `--legacy-companion-workspace`; keeping the old launcher risks reintroducing MP Companion-first startup behavior.

## Generated proof files

```text
logs/CodeRED_Regression_Guard_Report.md
logs/CodeRED_Regression_Guard_Report.json
data/codered/regression_guard_manifest.csv
```

## Important note

The local package does not currently show a new root-level `src/` folder, but the guard detected and decoded existing source folders under related apps. If new GitHub source folders are pulled into the package later, the guard will include them in source decode checks.
