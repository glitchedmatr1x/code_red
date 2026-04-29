# Code RED Faction War — No-SC Menu-Free Pass 02

This is a continuation branch of `CodeRedFactionWarV26_ReadyProject` with the trainer/debug menu layer disabled.

## Purpose

The goal is to keep the faction-war world simulation alive as an ambient background layer instead of a menu-driven trainer. It is prepared for the newer Code RED direction: use editable tune/camera/content resources where possible, and avoid SC-CL for this branch.

## What changed from v26

- The F7 overlay/menu path is disabled.
- Numpad/F-key debug controls are disabled.
- HUD toast spam is disabled by default.
- Simulation remains enabled automatically.
- Save/log/diagnostic/bulletin filenames were moved to `CodeRedFactionWar_NoSC_MenuFree.*`.
- The v26 faction, node, pressure, heat, supply, fear, logistics, convoy, town-assault, regional-shootout, occupation, directive, bulletin, and auto-event systems are preserved.

## Important distinction

This branch is **non-SC-CL**. It does not use the SC-CL compile lane.

The included Visual Studio project is still a RedHook `.red` plugin project because that is what the original v26 runtime was. The new `WorldResourceBridge/` is now the active no-EXE/no-SC-CL research lane. It generates editable `.tr`, `.pop`, `.traffic`, `.ini`, merge packs, and patch previews from the same faction-war seed data. The TR bridge now uses condition/action names recovered from the real AI files instead of placeholder functions.

## Files to inspect first

- `Source/CodeRedFactionWar/code_red_factionwar_plugin_v26.cpp`
- `Source/CodeRedFactionWar/code_red_faction_seed_v26.inl`
- `Source/CodeRedFactionWar/code_red_tune_profiles_v26.inl`
- `WorldResourceBridge/factionwar_nodes.json`
- `WorldResourceBridge/tune_ai/code_red_factionwar_world.tr`
- `WorldResourceBridge/tune_level/code_red_factionwar_level.pop`
- `WorldResourceBridge/tune_settings/code_red_factionwar.traffic`

## Runtime behavior

The world layer should now quietly:

- Track nearest faction-war territory.
- Update region pressure and daily directives.
- Generate rumors/bulletins/logs.
- Trigger nearby auto-events through the existing v26 world logic.
- Save state without requiring the player to open a menu.

## Next Code RED pass

The next major step is to let Code RED inject or merge the `WorldResourceBridge` text resources into tune/content archives using the Zstandard decode/rebuild path already discovered in tune and camera RPF research.


## Pass 02 functional bridge update

This pass turns the first bridge sketch into a usable resource workflow:

- `WorldResourceBridge/tools/codered_bridge_build.py` regenerates the resource bridge from JSON.
- `WorldResourceBridge/tune_ai/code_red_factionwar_world.tr` now uses recovered TR condition/action names such as `WantToHurt`, `CanCombatShootNoCover`, `UnknownWeaponFired`, `ObserveLastKnownPosition`, `CanHelp`, and `Help`.
- `WorldResourceBridge/merge_packs/` contains loose resource candidates for content/tune merge work.
- `WorldResourceBridge/merge_preview/` contains patched `game_main.tr` previews and diffs for both content AI and tune AI targets.
- `WorldResourceBridge/world_state_bridge.ini` gives the faction-war nodes a simple editable no-compiler data file for future runtime/resource alignment.
- `WorldResourceBridge/patch_recipes/code_red_factionwar_world_bridge_recipe.json` now lists a safer install order.

### Practical target

The first functional AI test is to add:

```text
#include "code_red_factionwar_world.tr"
```

to a validated `game_main.tr` target and extend the `program Main` TRUE route with:

```text
CodeRedFactionWarWorld WITH 1.0
```

Use the generated diffs in `WorldResourceBridge/merge_preview/` as the guide. The actual RPF write still needs Code RED's Zstandard decode/rebuild verification before installing to a game archive.
