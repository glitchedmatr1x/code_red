# Pass 16 Tune Template Faction Scan

Purpose: preserve tune and template research that can support the next Code RED Faction War living-world pass.

## Source inspected

- `game 1.zip -> tune_d11generic.rpf`
- standalone uploaded `tune_d11generic.rpf`

The standalone tune archive matched the tune archive found inside the game zip during local extraction.

## Extraction summary

- RPF entries: 2,017
- RPF files: 1,915
- text-like tune files extracted: 1,431
- extraction failures: 0

## Why this matters

The user Max Render and Spawns tune behaves like a support layer. It can keep more actors alive, visible, and respawning. Faction War should use that headroom, but density alone is not enough. The pass needs faction identity so repeated generic NPCs become recognizable gang, law, and regional groups.

## Major tune-side files to preserve and compare

- `root/tune/settings/ambientmgrtuning.xml`
- `root/tune/settings/componentallocations.xml`
- `root/tune/level/territory/level.pop`
- `root/tune/settings/default.traffic`
- `root/tune/level/playgrounds/level.streaming`
- `root/tune/level/playgrounds/low_level.streaming`
- `root/tune/level/playgrounds/designer_level.streaming`
- `root/tune/settings/bucket.cfg`
- `root/tune/settings/buckets.csv`
- `root/tune/settings/targettuning.xml`
- `root/tune/template/components.xml`
- `root/tune/ai/game_main.tr`

## Spawn and render support findings

### Ambient manager

`root/tune/settings/ambientmgrtuning.xml` exposes key living-world values:

- `MaxVisibleRange value="40.000000"`
- `DespawnMaxCheckDistance value="15.000000"`
- `DespawnNotVisibleTime value="3.000001"`
- `MaxNumActorsTotal value="50"`
- `NumActorsPreemptiveDestroy value="1"`
- `SpawnExcludeTime value="3.000000"`

Anti-regression note: the validated Pass 15 report preserved an ambient actor cap of 130. When merging this tune lane with Faction War, do not accidentally reduce that cap back to 50.

### Component allocations

`root/tune/settings/componentallocations.xml` contains resource headroom values. Important examples:

- `Mind = 80`
- `Animator = 80`
- `Behavior = 80`
- `BehaviorAnimal = 80`
- `Entity = 80`
- `Target = 80`
- `Vehicle = 20`
- `VehicleAudio = 20`
- `VehicleAnimator = 16`
- `DraftVehicle = 9`
- `Horse = 32`
- `BipedIK = 80`

This is likely a key support file for higher NPC, horse, wagon, vehicle, and AI density.

## Population findings

`root/tune/level/territory/level.pop` already contains useful faction-war seeds:

- `ped_law_WesternDeputy` -> `template_law_WesternDeputy` / `Deputy001`
- `ped_outlaw_bully` -> `template_enemy_OutlawBully` / `Cowboy002`
- `ped_outlaw_boss` -> `template_enemy_OutlawBoss` / `Cowboy003`
- `ped_bandito_desperado` -> `template_enemy_BanditoDesperado` / `Thug000`, `Thug002`
- `ped_bandito_pistolero` -> `template_enemy_BanditoPistolero` / `Thug001`

Likely easy Faction War tests:

- Armadillo already references `ped_outlaw_bully`, but at probability 0. Raise it only slightly for a controlled test.
- Fort Mercer already uses bandito references. Preserve and consider mild increases.
- Twin Rocks already uses outlaw references. Preserve and consider mild increases.
- Wilderness is mostly generic animal/wilderness pressure, so increasing wilderness density alone will not create faction variety.

## Template folder findings

`root/tune/template/` mostly contains base/schema templates and components rather than all named gang templates.

Important component names found in `root/tune/template/components.xml`:

- `Faction`
- `LawfulToAttack`
- `Race`
- `Rideable`
- `Player`

`LawfulToAttack` is a high-priority lead for fair law behavior. The goal is to make law systems treat hostile faction actors as valid targets instead of unfairly redirecting blame onto the player when the player helps against those groups.

The named faction templates referenced by `level.pop`, such as `template_enemy_OutlawBully` and `template_enemy_BanditoDesperado`, were not fully defined in the tune template folder. Next search target is `content.rpf` for the actual named template definitions.

## AI and law targeting clue

`root/tune/ai/game_main.tr` includes law and target-selection logic that points toward this path:

- law actor plus criminal target -> treat as enemy
- recently attacked actor -> treat as enemy
- neutral actor plus treat-as-enemy state -> enemy state

Faction War should use this instead of fighting it. Make faction groups clearly marked through the right criminal, hostile, or lawful-to-attack data, then law groups should prioritize them more naturally.

## Gang taxonomy clues

`root/tune/settings/xmleditorlists.xml` exposes gang/capability labels worth searching in content-side data:

- `DnD_Gang`
- `CR_Gang`
- `CM_Gang`
- `MexBan_Gang`
- `MexReb_Gang`
- `BH_Gang`
- `IndRaid_Gang`
- `Smug_Gang`
- `IndMil_Gang`
- `UsMil_Gang`
- `MexMil_Gang`

These are useful names to hunt in content templates, actor data, events, and relationship files.

## Hard faction identity requirements

The next Faction War pass should not only increase generic respawns. Required behavior:

- gangs spawn in recognizable faction groups
- each faction should have variety, not clones of one NPC type
- rival factions should engage each other through game event/relationship logic
- gangs should be a valid challenge to the player when appropriate
- law groups should prioritize hostile gang groups as the main public threat
- helping law groups against hostile gangs should not immediately become unfair player blame
- player-friendly law behavior must be protected

## Recommended pass split

### Pass 16A - Tune Support Layer

- preserve validated Pass 15 / Pass 15.30 faction-war lineage
- add conservative component allocation headroom
- add conservative ambient manager range/despawn/cap tuning
- preserve or exceed Pass 15 actor cap checks
- do not increase generic NPC density blindly

### Pass 16B - Faction Identity and Law Targeting

- find real gang template definitions in `content.rpf`
- build a faction template matrix
- map outlaw, bandito, law, bounty hunter, rebel, army, and regional gangs
- verify relationship/law targeting data
- use level/population/event/refgroup edits to spawn group identities, not just more bodies

## Next content-side research target

Extract and scan `content.rpf` for:

- `template_enemy_OutlawBully`
- `template_enemy_OutlawBoss`
- `template_enemy_BanditoDesperado`
- `template_enemy_BanditoPistolero`
- `template_law_WesternDeputy`
- `LawfulToAttack`
- `Faction`
- `Criminal`
- `MexBan_Gang`, `MexReb_Gang`, `DnD_Gang`, `CR_Gang`, `CM_Gang`, `BH_Gang`, `Smug_Gang`, `UsMil_Gang`, `MexMil_Gang`

## No-regression checks for future builders

Any generated Pass 16 patch should verify:

- Pass 15 placement features preserved
- Pass 15 law/high-alert events preserved
- Pass 15 rowdy gangs and lone lawman preserved
- Pass 15 wilderness population preserved
- Pass 15 traffic routes preserved
- Pass 15 ambient actor cap is not lowered
- Max Render and Spawns changes are merged as a separate support layer
- faction identity changes do not collapse into one repeated NPC model
