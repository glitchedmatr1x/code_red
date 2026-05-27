# Code RED One-App Dashboard Pass

Date: 2026-05-03

## Goal

Move the one-app lane registry from command-line proof into the main Code RED UI so the app opens with a visible command-center dashboard instead of forcing users to run `--one-app-status` manually.

## Added to `python_workbench.py`

- New `Dashboard` tab at the front of the notebook.
- One-app summary line with root, readiness score, ready count, needs-proof count, and missing count.
- Lane table with state, category, lane title, required-file count, and proof count.
- Lane detail panel showing:
  - command
  - description
  - present required files
  - missing required files
  - optional files
  - proof files
  - external/manual workflows the lane is replacing
  - notes
- Dashboard toolbar buttons:
  - Refresh Dashboard
  - Write Status Report
  - Open Logs
  - Open Imports
- Root toolbar buttons:
  - Refresh Dashboard
  - Write Status Report

## Fully consumed / obsolete files

No new file became obsolete in this pass.

Carry-forward obsolete deletion from the previous pass:

```text
run_workbench.py
```

Reason: the useful MP Companion workspace behavior was moved into `main.py` behind `--legacy-companion-workspace`, and keeping the old launcher risks pulling the old MP Companion-first startup back into the workflow.

## Validation

Commands run from the extracted package:

```text
python3 -m py_compile main.py python_workbench.py codered_app/__init__.py codered_app/paths.py codered_app/launcher_registry.py tools/codered_one_app_status.py
python3 main.py --dry-run
python3 main.py --one-app-status
python3 tools/codered_one_app_status.py --write
xvfb-run -a python3 dashboard smoke test
xvfb-run -a python3 write-status smoke test with dialog mocked
```

Results:

```text
compile checks: passed
main dry run: passed
one-app status CLI: passed
status report write: passed
Dashboard tab exists: passed
Dashboard lane count: 16
Write Status Report action: passed
```

## Current readiness

```text
Ready: 14
Ready but needs proof: 2
Missing required files: 0
Weighted readiness: 94%
```

The remaining non-100% lanes are proof-gated, not missing required files.

## Next pass recommendation

Bring the first real work lane into the UI: AI Trainer / enum validation.

Target actions:

1. Add a guided AI Trainer tab or dashboard quick-action section.
2. Rebuild/validate `data/codered/actor_enum_map.csv`.
3. Validate `npc_roster.txt` and `ai_behavior_actions.csv`.
4. Write actor resolution proof JSON before spawn/build.
5. Only enable build/install when validation passes.
