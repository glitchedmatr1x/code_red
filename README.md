# Code RED Layout Consolidation Pass

This pass provides a stable main-app shell for Code RED with a fixed top toolbar, fixed resource lane rail, workspace table, inspector notebook, and status bar.

## Run

```bash
python run_workbench.py
```

Optional path scan:

```bash
python run_workbench.py /path/to/resource/or/folder
```

Headless metadata self-test:

```bash
python code_red_main.py --self-test
```

## Why this pass exists

The prior Code RED reports showed a useful RDR research/workbench pipeline, but also several staged pieces that should not be exposed as final mutation buttons yet: direct binary injection, full texture dictionary parsing, automatic RPF write-back, and full mesh structural editing. This pass keeps the UI conservative and read-first.

## Layout rules locked by this pass

- Buttons are centralized through one `_button(...)` factory.
- The shell uses grid-only layout; no absolute placement.
- Top toolbar actions are limited to five stable actions.
- Resource lanes are fixed on the left.
- Resource details, reports, and logs live in the right inspector.
- Archive/resource mutation remains staged unless a validated backend is attached.
