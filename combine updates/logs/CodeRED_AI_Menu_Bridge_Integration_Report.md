# CodeRED AI Menu Bridge Integration Report

Generated: `2026-05-03T09:14:27Z`
Result: **PASS**

## Outputs

- Source: `/mnt/data/codered_work/related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp`
- Candidate: `/mnt/data/codered_work/related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp`
- Build helper: `/mnt/data/codered_work/related_apps/Code_RED_ScriptHookRDR_AI_Menu/build_bridge_candidate.bat`
- Diff: `/mnt/data/codered_work/logs/CodeRED_AI_Menu_Bridge_Integration_Candidate.diff`
- Manifest: `/mnt/data/codered_work/data/codered/ai_menu_bridge_integration_manifest.json`

## Native bridge wrapper proof

- Selected natives: `26`
- Ready wrappers: `26`
- Candidate block inserted: `True`

## Existing AI Menu native usage

- `AI_IS_HOSTILE_OR_ENEMY`: `2` hash references
- `CREATE_ACTOR_IN_LAYOUT`: `1` hash references
- `GET_ACTOR_FACTION`: `1` hash references
- `SET_ACTOR_FACTION`: `3` hash references
- `TASK_FOLLOW_ACTOR`: `3` hash references
- `TASK_KILL_CHAR`: `1` hash references

## Safety note

This pass does not overwrite the active AI Menu source and does not install an ASI.
Use the generated candidate and build helper only after reviewing the diff.
