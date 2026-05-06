# Code RED — Start Here

## What to launch

Use this order:

1. `Code_RED.bat` — best Windows entry point if you copy this launcher kit into the Code_RED folder.
2. `run_workbench.py` — preferred Python source entry point.
3. `python_workbench.py` — app implementation/fallback if the runner is missing.
4. `Code_RED.exe` / `Code RED.exe` — preferred packaged entry point if an EXE build exists.

Avoid launching these directly unless you are developing/building the app:

- `Program.cs`
- `RDR1MergeWorkbench.csproj`
- `UI/MainForm.cs`
- `_capture_*.py`
- files under `docs/`, `sample_workspace/`, or `test_inputs/`

## Current feature truth

Code RED currently appears to be a conservative research/workbench tool, not a complete RPF injector/editor. It can inspect and route archive children into format-aware lanes, generate reports, preview/edit some extracted content, and produce reintegration/replacement plans. Some operations intentionally stop at plan files instead of mutating unknown binary containers.

## Missing / not yet safe to claim

These features should be considered missing or staged until a later pass proves them:

- automatic write-back into `.rpf` archives
- true direct binary injection into `.wtd/.wtx/.wsf/.xtd/.xtx/.xsf`
- full embedded texture dictionary parsing
- full `.wft/.wfd/.wvd` mesh/fragment structural editing
- source-level script compile-back
- full vehicle/tune GUI integration, unless a separate Code RED Tuner folder exists

## Recommended folder cleanup

A clean user-facing package should have this shape:

```text
Code_RED/
  Code_RED.bat
  run_workbench.py
  python_workbench.py
  README_START_HERE.md
  data/
    natives.json
  docs/
  sample_workspace/
  test_inputs/
  UI/                 # source only
  Services/           # source only
  Models/             # source only
  RDR1MergeWorkbench.csproj  # source/build only
```

For a packaged Windows build, the root should instead contain one obvious `Code_RED.exe` plus a README, with source files moved into a `source/` folder or omitted.
