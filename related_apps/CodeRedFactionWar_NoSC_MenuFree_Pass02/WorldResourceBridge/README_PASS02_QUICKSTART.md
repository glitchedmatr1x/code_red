# Code RED Faction War WorldResourceBridge Pass02 Quickstart

This folder is the no-EXE/no-SC-CL path for pushing Faction War logic toward editable game resources.

## Rebuild the bridge files

```bat
python WorldResourceBridge\tools\codered_bridge_build.py --root . --build
```

## Patch an exported AI file

```bat
python WorldResourceBridge\tools\codered_bridge_build.py --patch-game-main exported_game_main.tr patched_game_main.tr
```

The patcher adds:

```text
#include "code_red_factionwar_world.tr"
```

and extends `program Main` with:

```text
CodeRedFactionWarWorld WITH 1.0
```

## Files that matter

- `tune_ai/code_red_factionwar_world.tr`
- `merge_packs/content_ai/root_content_ai_code_red_factionwar_world.tr`
- `merge_packs/tune_ai/root_tune_ai_code_red_factionwar_world.tr`
- `merge_preview/*.diff`
- `patch_recipes/code_red_factionwar_world_bridge_recipe.json`
- `world_state_bridge.ini`

## Install caution

Do not blind replace archives. The target RPF entry must be decompressed, patched, recompressed with the same method, reopened, and verified in Code RED before game testing.
