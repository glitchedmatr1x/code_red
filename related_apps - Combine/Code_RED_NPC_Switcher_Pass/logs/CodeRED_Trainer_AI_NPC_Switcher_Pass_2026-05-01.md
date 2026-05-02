# CodeRED Trainer AI NPC Switcher Pass — 2026-05-01

## Goal

Allow CodeRED's trainer AI controller to use the full NPC/model list instead of a small hardcoded selection, with support for switching through `gent_`, `gped_`, `amb_`, and special named fragment actors.

## Completed

- Added a dependency-free NPC roster loader/scanner.
- Added a trainer AI controller with roster-driven selection.
- Added next/previous/set/filter/list commands.
- Added optional RPF/string-list scanning for model names.
- Added a conservative 42-entry seed roster from visible `fragments.rpf` strings so the controller works immediately.
- Added batch menu entries for NPC list/switch/set/filter/scan.
- Added state/action-plan output for a future ScriptHook/trainer bridge.

## Key files

```text
tools/codered_npc_roster.py
tools/codered_trainer_ai_controller_v1.py
CodeRED_Trainer_AI_Menu_v1.bat
data/codered/npc_model_roster_v1.json
data/codered/trainer_ai_profile_v1.json
docs/codered/trainer_ai_control_handoff_v1.md
```

## Tested commands

```text
python tools/codered_npc_roster.py validate
# result: loaded=42
# ambient: 6
# animal_or_mount: 6
# named_fragment: 15
# player_like: 10
# zombie: 5

python tools/codered_npc_roster.py list --filter amb --limit 10
python tools/codered_trainer_ai_controller_v1.py status
python tools/codered_trainer_ai_controller_v1.py npc-list player
python tools/codered_trainer_ai_controller_v1.py npc-next amb
python tools/codered_trainer_ai_controller_v1.py npc-set player_bandito
python tools/codered_trainer_ai_controller_v1.py spawn
python tools/codered_trainer_ai_controller_v1.py defend
python tools/codered_npc_roster.py scan /mnt/data/codered_work/fragments/fragments.rpf --out scratch/codered_npc_roster_scan.json --merge
# result: saved 42 model candidates
```

## Regression checks

- Python syntax compile passed for both added tools.
- One-shot commands no longer reset selected model back to profile default.
- JSON category labels such as `player_like` are no longer mistaken for model names.
- Binary scan now rejects obvious material/texture/body/animation junk more conservatively.
- No Xenia/network files were touched.
- No RPF/archive mutation is performed.

## Usage notes

- The seed roster is not the true final full list; it is a conservative starting list from visible strings.
- To use the actual full local list, place it in `Smart Menu/ImportedFileNames.txt`, `Smart_Menu/ImportedFileNames.txt`, root `ImportedFileNames.txt`, or run `npc-scan` on the local archive/list.
- `npc-next amb`, `npc-next gent`, `npc-next gped`, and `npc-next player` cycle inside filtered groups when those names exist in the roster.
- Not all names are guaranteed spawnable. The bridge should handle invalid models safely and keep the previous actor alive.
