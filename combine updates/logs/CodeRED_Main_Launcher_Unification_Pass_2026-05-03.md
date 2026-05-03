# Code RED Main Launcher Unification Pass

Date: 2026-05-03

## Goal

Resolve the two-main collision and remove the fully-salvaged duplicate launcher so it cannot be pulled back into the workflow by accident.

## Finding

`main.py` was the stronger canonical launcher because it already created runtime folders, wrapped the workbench launch in a callable `main()` function, returned process status, and wrote crash logs.

`run_workbench.py` was the weaker launcher because it executed everything at import time, had no crash logging, had no return-code wrapper, and started the whole workbench inside MP Companion when that folder existed.

The useful behavior from `run_workbench.py` was its MP Companion workspace discovery. That behavior is now available as an explicit compatibility flag in `main.py`, so the duplicate launcher can be deleted.

## Updated

- `main.py`
  - Added CLI parsing.
  - Added `--workspace`.
  - Added `--legacy-companion-workspace`.
  - Added `--title`.
  - Added `--dry-run` for headless launch tests.
  - Kept crash logging and runtime folder creation.
  - Kept repo root as default startup workspace.

- `run_workbench.py`
  - Removed after its useful behavior was fully moved into `main.py`.
  - This prevents the old MP Companion-first startup path from being accidentally reused.

## Test Commands

```bat
py -3 -m py_compile main.py python_workbench.py
py -3 main.py --dry-run
py -3 main.py --legacy-companion-workspace --title "Code RED Resource Workbench" --dry-run
```

## Result

`Run_Code_RED.bat` still launches `main.py` and now has the cleaner canonical behavior.

Old `run_workbench.py` shortcuts should be updated to call `main.py`. The removed behavior is still reachable through `main.py --legacy-companion-workspace`, but it no longer exists as a competing root launcher.
