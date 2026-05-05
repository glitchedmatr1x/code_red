# Code RED source/decompiled export
# Source: docs/code-red-script-workflow/README.md
# SHA1: 2a5522d6fbde7ed8b7cbdf87b1a2036e970c802a

# Code RED Script Workflow

This folder organizes script work so menu features can be built without mixing together trainer code, SC-CL experiments, archive tools, and research notes.

## Mission

Build Code RED scripts with proof instead of guesses.

Every script feature should have:

- a lane
- a verified source of truth
- a tiny proof or runtime check
- a log entry
- a safe rollback path

## Folder layout

```text
SCRIPTING.md                                  root quick-start

docs/code-red-script-workflow/
  README.md                                  this guide
  LANES.md                                   where each kind of work belongs
  SCRIPT_FEATURE_STATUS.md                   current feature matrix
  NATIVE_VERIFICATION_TEMPLATE.csv           evidence table template
  PROOF_SCRIPT_TEMPLATE.md                   tiny-proof checklist
  ACTOR_TRAVEL_MENU_PLAN.md                  no-guess actor travel plan
  CLEANROOM_RESEARCH_RULES.md                safe research rules

logs/
  CodeRED_*                                  pass logs and proof logs
```

## No-guess acceptance rule

A script feature is not production-ready until it has one of the following:

1. real header evidence
2. verified wrapper/API evidence
3. tiny compile proof
4. tiny runtime proof
5. a working reference that can be described without copying code

The feature must also fail safely. If the handle, coordinates, or native call is invalid, the menu should do nothing and log the failure.

## Script work order

Use this sequence:

1. Identify the lane.
2. Find the native/wrapper/function evidence.
3. Add evidence to the verification table.
4. Build one tiny proof.
5. Log the proof result.
6. Only then wire it into the menu.

## What not to do

Do not continue from the old full SC-CL menu source.

Do not use proof shim headers as real compile evidence.

Do not bulk patch game archives to test script commands.

Do not copy proprietary trainer code, tables, or assets.

## Current recommendation

Use the Trainer / ScriptHook / RedHook lane for the real Code RED menu.

Keep SC-CL for tiny internal experiments only.
