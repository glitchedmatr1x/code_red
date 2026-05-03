# Code RED Script Workflow Organization Pass — 2026-05-03

## Purpose

Make script work persistent in GitHub so the project does not forget which path is safe.

## Result

Added permanent workflow documentation under:

```text
docs/script_workflow/
```

Added native registry files:

```text
docs/script_workflow/native_registry/verified_natives.csv
docs/script_workflow/native_registry/candidate_natives.csv
```

## Key decision

The real Code RED menu belongs in the ScriptHook / AI Trainer lane.

SC-CL remains a proof-only lane until exact native signatures are verified against real headers.

Archive tools remain separate from script/menu work.

Research tools remain read-only until promoted with proof.

## No-guess rule

Do not add actor travel, actor spawn, companion control, teleport, or task commands to the real menu unless the native/wrapper signature is verified or a tiny runtime/compile proof exists.

## Current verified proof notes

Verified proof-only calls:

- `_CLEAR_PRINTS`
- `_PRINT_SUBTITLE` with the real 8-argument usage used in the proof
- `WAIT(0)`

Blocked/candidate:

- `CREATE_ACTOR_IN_LAYOUT` requires exact vector3 Position and vector3 Rotation usage.
- actor travel/follow/task calls need ScriptHook/RedHook wrapper verification before menu use.

## Next pass

Add a non-destructive script lane doctor that scans the repo and reports files that appear to be in the wrong lane.

Suggested path:

```text
tools/codered_script_lane_doctor.py
```

The doctor should only report; it should not move, delete, or rewrite files.
