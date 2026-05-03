# Code RED One-App Cleanup Rule

Date: 2026-05-03

## Rule

When a salvaged helper or duplicate launcher has been fully absorbed into the canonical Code RED app path, remove the old file instead of keeping it as a wrapper.

## Reason

The goal is one app, not a pile of side launchers. A salvaged duplicate can pull old behavior back into the workflow and make testing ambiguous.

## First application

`run_workbench.py` was removed because `main.py` now contains the useful companion-workspace option and remains the canonical launcher.

## Current canonical path

```text
Run_Code_RED.bat -> main.py -> python_workbench.py / future codered_app shell
```

## Future rule

Before deleting a duplicate, verify:

```text
1. The stronger canonical file contains the useful behavior.
2. There are no active launchers pointing at the old file.
3. Compile/dry-run tests pass.
4. The deletion is noted in logs.
```
