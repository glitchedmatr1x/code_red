# AI / Tune Resource Findings Used In Pass02

This pass was built from the recovered tune/content/camera resource patterns.

## Useful file types

- `.tr` uses a readable C-like rule language with `#include`, `program`, `rules`, custom predicates, and action lists.
- `.pop` uses `version 2` plus `Conditions` blocks and neighborhood/time expressions.
- `.traffic` uses `version 1` plus profile records.
- Many tune/camera entries are Zstandard-compressed text. The raw compressed frame starts with `28 B5 2F FD`.

## AI files that shaped the bridge

Observed from recovered AI text:

- `root/tune/ai/game_main.tr`
- `root/content/ai/game_main.tr`
- `root/content/ai/human_hostile.tr`
- `root/content/ai/human_combat.tr`
- `root/content/ai/human_guard.tr`

Important recovered TR actions/conditions used by the bridge:

```text
Player(x)
WantToHurt(x)
Hostile(x)
PossibleEnemy(x)
Ally(x)
ScreamedRecently(x)
UnknownWeaponFired(x)
HiddenEnemyWeaponFired(x)
RecentExplosion(x)
CanObserveLastKnownPosition(x)
ObserveLastKnownPosition(x)
CanCombatShootNoCover(x)
CombatShootNoCover(x)
CanCombatFightOrTakeDown(x)
CombatFightOrTakeDown(x)
CanCombatReadyRangeWeapon
CombatReadyRangeWeapon
CanHelp(x)
Help(x)
LookAt(x)
LookAtIfPossible(x)
SpeedJog
SpeedSprint
PerformExternalGoals
```

## Why Pass02 is safer than Pass01

Pass01 mostly documented intent in comments. Pass02 generates a TR bridge that should participate in stock AI arbitration after it is included from `game_main.tr`.

The generated file still avoids unknown functions such as:

```text
FactionPressure(...)
Neighborhood(...)
StartFactionWar(...)
```

inside `.tr`, because those were not observed in the recovered AI rule language.

## First install experiment

Use `merge_preview/tune_root_tune_ai_game_main_with_codered.tr.diff` as the cleanest first target:

```diff
+#include "code_red_factionwar_world.tr"
- TRUE -> Main0, PerformExternalGoals, UpdateHostility;
+ TRUE -> Main0, PerformExternalGoals, UpdateHostility, CodeRedFactionWarWorld WITH 1.0;
```

Then add `code_red_factionwar_world.tr` beside `game_main.tr` in the same AI folder.

## Important warning

The previews are not full archive installers. The RPF writer must preserve the target entry's resource flags, size fields, and compression type.
