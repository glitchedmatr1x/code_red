# CodeRED Research Browser Lane Pass

Date: 2026-05-03

## Scope

Added an in-app Logs / Research Browser so Code RED can browse curated pass logs, generated proof reports, research-manifest entries, docs, and regression checkpoint zips without manually hunting files.

## Updated

- `python_workbench.py`
- `codered_app/launcher_registry.py`

## Added runtime proof

- `logs/CodeRED_Research_Browser_Report.md`
- `logs/CodeRED_Research_Browser_Report.json`

## UI additions

New tab:

```text
Research
```

New toolbar buttons:

```text
Refresh Research
Write Research Index
```

Research tab buttons:

```text
Refresh Research
Write Research Index
Open Selected
Open Logs
Open Research Folder
```

## What the browser indexes

- `research/CodeRED_RESEARCH_MANIFEST.csv`
- `logs/CodeRED_LOG_INDEX.md` when present
- curated README/docs files
- `logs/CodeRED_*.md`
- `logs/CodeRed_*.txt`
- `logs/README*.txt`
- generated proof JSON reports
- selected `research/CodeRED_*.md` and `research/CodeRed_*.txt`
- `docs/*.md`
- root-level Code RED regression checkpoint zips if copied into the package

## Validation

Commands run:

```text
python3 -m py_compile main.py python_workbench.py codered_app/__init__.py codered_app/paths.py codered_app/launcher_registry.py tools/codered_one_app_status.py
python3 tools/codered_one_app_status.py --write
python3 main.py --dry-run
python3 main.py --one-app-status
xvfb-run -a python3 /tmp/test_research_ui.py
```

Result:

```text
research-ui-smoke-pass
```

## Current report notes

The browser indexed 88 entries in the current package and found 10 manifest references missing from the uploaded/extracted source set. Those missing entries are not treated as app failures because they are referenced research notes not required launch files. They are surfaced in the Research tab and in the generated report so future source refreshes can fill them back in.

## Fully consumed / obsolete this pass

None.

## Carry-forward obsolete items

- `run_workbench.py` remains obsolete and should stay deleted because its useful behavior was absorbed into `main.py`.
- `__pycache__/` remains generated clutter and should stay deleted.
