# CodeRED Trainer AI Control v1 — NPC Roster Switcher

Date: 2026-05-01

## Purpose

This pass makes the trainer/AI control layer use a real roster instead of a tiny hardcoded NPC list.

The controller can now browse and switch through NPC/model names from:

- `data/codered/npc_model_roster_v1.json`
- `scratch/codered_npc_roster.json`
- `scratch/codered_npc_roster_scan.json`
- `Smart Menu/ImportedFileNames.txt`
- `Smart_Menu/ImportedFileNames.txt`
- root-level `ImportedFileNames.txt`

It specifically supports the naming families we need for Red Dead fragments:

- `gent_`
- `gped_`
- `amb_`
- named/special fragment names such as `anc_`, `com_`, `crm_`, `law_`, `misc_`, `player_`, `ranch_`, `zombie_`, and names ending in `_cs`

## Added files

```text
CodeRED_Trainer_AI_Menu_v1.bat
tools/codered_trainer_ai_controller_v1.py
tools/codered_npc_roster.py
data/codered/trainer_ai_profile_v1.json
data/codered/npc_model_roster_v1.json
logs/CodeRED_Trainer_AI_NPC_Switcher_Pass_2026-05-01.md
docs/codered/trainer_ai_control_handoff_v1.md
```

## New commands

Interactive controller:

```bat
python tools\codered_trainer_ai_controller_v1.py
```

One-shot examples:

```bat
python tools\codered_trainer_ai_controller_v1.py npc-list
python tools\codered_trainer_ai_controller_v1.py npc-list amb
python tools\codered_trainer_ai_controller_v1.py npc-next
python tools\codered_trainer_ai_controller_v1.py npc-next gent
python tools\codered_trainer_ai_controller_v1.py npc-prev
python tools\codered_trainer_ai_controller_v1.py npc-set law_caucasianmarshall_06_cs
python tools\codered_trainer_ai_controller_v1.py spawn
python tools\codered_trainer_ai_controller_v1.py defend
```

Scan a fragment archive or text list for more names:

```bat
python tools\codered_trainer_ai_controller_v1.py npc-scan "D:\path\to\fragments.rpf"
```

Roster tool directly:

```bat
python tools\codered_npc_roster.py list --filter amb
python tools\codered_npc_roster.py scan "D:\path\to\fragments.rpf" --out scratch/codered_npc_roster_scan.json --merge
python tools\codered_npc_roster.py validate
```

## What gets written

Every selection/behavior command updates:

```text
scratch/codered_trainer_ai_state.json
scratch/codered_trainer_ai_action_plan.json
scratch/codered_trainer_ai_commands.jsonl
logs/codered_trainer_ai_controller.log
```

The selected NPC/model is carried in the action plan:

```json
{
  "entity": {
    "model": "amb_fh_farmer06",
    "model_category": "ambient",
    "model_index": 3
  },
  "requests": [
    "ensure_spawned",
    "spawn_model",
    "equip_basic_weapon"
  ]
}
```

A future ScriptHook/trainer bridge should read `entity.model` and use the trainer/game-side spawn method for that model. If the model fails, the bridge should report an invalid-model status and keep the last valid actor instead of crashing or deleting the actor.

## Important behavior

- The controller does not assume every model name is spawnable.
- Cycling works across the whole roster or filtered groups.
- `npc-next amb` cycles only ambient entries.
- `npc-next gent` and `npc-next gped` will work when the full list is present in `ImportedFileNames.txt` or after scanning.
- `npc-filter amb` makes list/next/previous stay inside that group until changed.
- RPF scanning is read-only and only mines visible strings; it does not patch or mutate archives.

## Safe scope

This is for offline/singleplayer/private modding and research. It does not implement public online cheating, anti-cheat bypass, or fake network players.
