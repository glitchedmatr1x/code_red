# CodeRED AI Menu Bridge Integration Lane Pass - 2026-05-03

# CodeRED AI Menu Bridge Integration Report

Generated: `2026-05-10T21:12:28Z`
Result: **PASS**

## Outputs

- Source: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_ScriptHookRDR_AI_Menu\CodeRED_AI_Menu.cpp`
- Candidate: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_ScriptHookRDR_AI_Menu\CodeRED_AI_Menu.bridge_candidate.cpp`
- Build helper: `D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_bridge_candidate.bat`
- Diff: `D:\Games\Red Dead Redemption\Code_RED\logs\CodeRED_AI_Menu_Bridge_Integration_Candidate.diff`
- Manifest: `D:\Games\Red Dead Redemption\Code_RED\data\codered\ai_menu_bridge_integration_manifest.json`

## Native bridge wrapper proof

- Selected natives: `26`
- Ready wrappers: `26`
- Candidate block inserted: `True`

## Existing AI Menu native usage

- `AI_IS_HOSTILE_OR_ENEMY`: `4` hash references
- `CREATE_ACTOR_IN_LAYOUT`: `3` hash references
- `GET_ACTOR_FACTION`: `3` hash references
- `SET_ACTOR_FACTION`: `5` hash references
- `TASK_FOLLOW_ACTOR`: `5` hash references
- `TASK_KILL_CHAR`: `3` hash references

## Safety note

This pass does not overwrite the active AI Menu source and does not install an ASI.
Use the generated candidate and build helper only after reviewing the diff.

## Next step

Run `related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_bridge_candidate.bat` from a Visual Studio x64 Native Tools Command Prompt on Windows.
