# CodeRED Archive / RPF Lane Pass

Date: 2026-05-03

## Scope

Upgrade the Archive/RPF lane so Code RED can prove its archive inventory and sample extraction path from inside the one-app dashboard, instead of relying on manual Magic RDR browsing or separate helper workflows.

## Added

```text
tools/codered_archive_lane_validation.py
```

The validator is read-only. It discovers staged RPF archives in:

```text
imports/
game/
package root
parent sources folder
```

It inventories RPF6 archives, counts storage/module/extension profiles, sample-reads entries, identifies text-like/resource samples, and writes proof reports.

## Updated

```text
python_workbench.py
codered_app/launcher_registry.py
```

New one-app button:

```text
Validate Archives
```

Added in:

```text
Dashboard tab
Top toolbar
```

The Archive/RPF lane now points at the validator and records proof logs in the lane registry.

## Proof Result

Validated staged source archives:

```text
content.rpf
tune_d11generic.rpf
```

Result:

```text
Archive lane validation: PASS
Archives parsed: 2/2
Sample reads: 12/12 ok
```

Generated:

```text
logs/CodeRED_Archive_Lane_Validation_Report.md
logs/CodeRED_Archive_Lane_Validation_Report.json
```

## Validation

Passed:

```text
python3 -m py_compile main.py python_workbench.py codered_app/__init__.py codered_app/paths.py codered_app/launcher_registry.py tools/codered_archive_lane_validation.py tools/codered_one_app_status.py
python3 tools/codered_archive_lane_validation.py --root . --sample-limit 6
python3 tools/codered_one_app_status.py --write
python3 main.py --dry-run
python3 main.py --one-app-status
xvfb-run UI smoke: Validate Archives invoked successfully
```

One-app status remains:

```text
Ready: 16
Ready but needs proof: 0
Missing required files: 0
Weighted readiness: 100%
```

## Fully Consumed / Obsolete

None new in this pass.

Carry-forward obsolete items remain removed:

```text
run_workbench.py
__pycache__/
```

## Safety

This pass does not modify source archives. It proves parse/inventory/sample-read readiness only. Patch/install operations must continue to use copied archives with proof reports.
