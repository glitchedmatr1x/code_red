# Code RED AI Menu Doctor

Root: `D:\Games\Red Dead Redemption\Code_RED`
related_apps exists: `True`

Boundary: read-only local scan. No files modified.

## Verdict

- current camp-car artifacts are present and match expected hashes
- AI menu/trainer files do not appear wired to camp_car_probe yet

## Artifact status

- `xsc` `script_compiling/sccl/output/camp_car_probe/camp_car_probe.xsc` exists=`True` length=`1158` sha1=`C8DC6821D04A76302C123814A8DCBD507DD6200E` current=`True`
- `sco` `script_compiling/sccl/output/camp_car_probe_sco/camp_car_probe.sco` exists=`True` length=`1075` sha1=`0351E47E3B0F5C6BA7C8D75A6C8FDA92A78D8C8B` current=`True`
- `wsc` `script_compiling/sccl/output/camp_car_probe_wsc/camp_car_probe.wsc` exists=`True` length=`1158` sha1=`2729784CA37478DD22E0CFE8BD52B11793A36E14` current=`True`

## Candidate AI menu / trainer files

### score 140 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/tools__codered_ai_trainer_validation.py.decompiled_source.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 140 — `related_apps/CodeRED_Script_Workshop/workspace/edit/tools/codered_ai_trainer_validation.py`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 140 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/tools/codered_ai_trainer_validation.py`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 140 — `related_apps/CodeRED_Script_Workshop/workspace/read/tools__codered_ai_trainer_validation.py.fullread.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/related_apps__Code_RED_ScriptHookRDR_AI_Menu__CodeRED_AI_Menu.bridge_candidate.cpp.decompiled_source.txt`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, menu, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/tools__codered_script_compile_validation.py.decompiled_source.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/edit/related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, menu, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/edit/tools/codered_script_compile_validation.py`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, menu, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/tools/codered_script_compile_validation.py`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/read/related_apps__Code_RED_ScriptHookRDR_AI_Menu__CodeRED_AI_Menu.bridge_candidate.cpp.fullread.txt`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, menu, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/read/tools__codered_script_compile_validation.py.fullread.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/CodeRED_Script_Workshop/workspace/recompile_queue/related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, menu, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 130 — `related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, menu, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/report1.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, sco, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/related_apps__code_red_sccl_attempt_bundle_v1__code_red_script_compile_lab_v1__scripts__validate_vehicle_menu_probe.py.decompiled_source.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/related_apps__code_red_sccl_attempt_bundle_v1__code_red_script_compile_lab_v1__src__main.c.decompiled_source.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/research__CodeRED_Project_Research_Master_Chat_Source_2026-04-29.md.decompiled_source.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/research__IMPORTANT_readable_root_index_2026-05-02__ai_readable_root_index.json.decompiled_source.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/research__IMPORTANT_readable_root_index_2026-05-02__ai_readable_root_index.md.decompiled_source.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/research__IMPORTANT_readable_root_index_2026-05-02__categories__npc_ai_factions.csv.decompiled_source.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/edit/related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/scripts/validate_vehicle_menu_probe.py`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/edit/related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/src/main.c`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/edit/research/CodeRED_Project_Research_Master_Chat_Source_2026-04-29.md`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/edit/research/IMPORTANT_readable_root_index_2026-05-02/ai_readable_root_index.json`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/edit/research/IMPORTANT_readable_root_index_2026-05-02/ai_readable_root_index.md`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/edit/research/IMPORTANT_readable_root_index_2026-05-02/categories/npc_ai_factions.csv`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/scripts/validate_vehicle_menu_probe.py`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/src/main.c`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/research/CodeRED_Project_Research_Master_Chat_Source_2026-04-29.md`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/research/IMPORTANT_readable_root_index_2026-05-02/ai_readable_root_index.json`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/research/IMPORTANT_readable_root_index_2026-05-02/ai_readable_root_index.md`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/import_queue/research/IMPORTANT_readable_root_index_2026-05-02/categories/npc_ai_factions.csv`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/read/related_apps__code_red_sccl_attempt_bundle_v1__code_red_script_compile_lab_v1__scripts__validate_vehicle_menu_probe.py.fullread.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/read/related_apps__code_red_sccl_attempt_bundle_v1__code_red_script_compile_lab_v1__src__main.c.fullread.txt`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/read/research__CodeRED_Project_Research_Master_Chat_Source_2026-04-29.md.fullread.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle, wsc, xsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/read/research__IMPORTANT_readable_root_index_2026-05-02__ai_readable_root_index.json.fullread.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/read/research__IMPORTANT_readable_root_index_2026-05-02__ai_readable_root_index.md.fullread.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/read/research__IMPORTANT_readable_root_index_2026-05-02__categories__npc_ai_factions.csv.fullread.txt`
- hits: ai, car01, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/CodeRED_Script_Workshop/workspace/recompile_queue/related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/src/main.c`
- hits: ACTOR_VEHICLE_Car01, CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.log`
- hits: ACTOR_VEHICLE_Car01, ai, car01, menu, scripthook, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/Code_RED_ScriptHookRDR_AI_Menu/car_truck_spawn_recipe_pseudocode.txt`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, scripthook, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/Code_RED_ScriptHookRDR_AI_Menu/data/codered/npc_roster_safe_verified.txt`
- hits: ACTOR_VEHICLE_Car01, ai, car01, menu, scripthook, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 120 — `related_apps/Code_RED_ScriptHookRDR_AI_Menu/docs/codered/trainer_ai_control_handoff_v1.md`
- hits: ai, menu, rpf, sco, scripthook, spawn, trainer
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 110 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/data__codered__script_pipeline_manifest.csv.decompiled_source.txt`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, sco, spawn, vehicle, wsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 110 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/data__codered__script_pipeline_manifest.json.decompiled_source.txt`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, car01, menu, sco, spawn, vehicle, wsc
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 110 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/data__codered__script_workshop_compile_candidates.json.decompiled_source.txt`
- hits: CREATE_ACTOR_IN_LAYOUT, ai, menu, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 110 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/docs__CodeRED_One_App_Upgrade_Plan_2026-05-03.md.decompiled_source.txt`
- hits: ai, menu, rpf, sco, scripthook, spawn, trainer, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 110 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/research__CodeRed_Navres_Terrain_Navigation_Findings_Pass12.txt.decompiled_source.txt`
- hits: ai, menu, rpf, sco, spawn, vehicle
- references camp_car_probe: `False`
- references current artifacts: `False`

### score 110 — `related_apps/CodeRED_Script_Workshop/workspace/decompiled_export/research__CodeRed_USArmy_Companion_AI_Research_Pass12.txt.decompiled_source.txt`
- hits: ai, rpf, sco, spawn, vehicle, wsc
- references camp_car_probe: `False`
- references current artifacts: `False`
