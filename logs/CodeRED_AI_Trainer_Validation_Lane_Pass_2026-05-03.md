# Code RED AI Trainer Validation Lane Pass

Date: 2026-05-03

## Goal

Move the AI Trainer enum/roster/action sanity checks into the one-app workflow so the trainer lane does not require separate manual checking before build/install work.

## Added

```text
tools/codered_ai_trainer_validation.py
```

This tool validates:

- `data/codered/actor_enum_map.csv`
- `data/codered/npc_roster.txt`
- `data/codered/ai_behavior_actions.csv`
- `related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp`
- `related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.ini`

## Checks

- Known actor sanity values resolve correctly.
- Safe roster entries resolve to actor enums.
- Behavior action CSV contains the required enabled actions.
- AI Menu source still contains the required native hash hooks and source anchors.
- AI Menu INI points at the Code RED roster, enum map, and behavior-action CSV.

## Updated

```text
codered_app/launcher_registry.py
python_workbench.py
```

The one-app Dashboard now has a `Validate AI Trainer` action.
The top toolbar also has `Validate AI Trainer`.
The AI Trainer lane now uses the validator as its registry command and proof gate.

## Proof output

```text
logs/CodeRED_AI_Trainer_Validation_Report.json
logs/CodeRED_AI_Trainer_Validation_Report.md
```

Latest validation result:

```text
PASS
Enum rows: 3624
Roster resolved: 13/13
Actions enabled: 14/14
Sanity errors: 0
Native errors: 0
INI errors: 0
```

## One-app readiness impact

Before:

```text
Ready: 14
Ready but needs proof: 2
Weighted readiness: 94%
```

After:

```text
Ready: 15
Ready but needs proof: 1
Weighted readiness: 97%
```

## Fully consumed / obsolete

No new file was fully consumed in this pass.

Carry-forward obsolete deletion still applies:

```text
run_workbench.py
__pycache__/
```

## Next pass

The remaining proof-gated lane is `Terrainboundres Tools`. The next pass should run or generate terrainboundres proof from the included archive/tooling, then wire that proof into the one-app dashboard so readiness can hit 100% without faking completion.
