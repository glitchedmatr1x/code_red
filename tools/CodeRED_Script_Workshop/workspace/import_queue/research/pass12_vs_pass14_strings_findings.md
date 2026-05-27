# Code RED: Pass 12 vs Pass 14 + strings_d11generic Findings

Date: 2026-04-29

## Result

Pass 14 should not be treated as a complete successor to Pass 12 yet. Pass 14 correctly extends the later placement/Blackwater lane, but it was built on the Pass 13 combined base and does not carry every Pass 12 payload forward.

Next build rule: **start from Pass 12 as the base, then layer Pass 13 empty-world activity and Pass 14 Blackwater/lasso updates on top.**

## Pass 12 payloads that must be preserved

Pass 12 modified seven payloads:

1. `root/content/ambient/placementglobals.xml`
   - Wilderness event reinforcement.
   - Empty country event set.
   - Player-companion/posse scaffolding.

2. `root/content/ambient/factionrelations.xml`
   - Player/law/ally faction relationship work.
   - This is important for follower/lawmen/faction-war behavior.

3. `root/content/ai/game_main.tr`
   - Companion/helper pulse scaffold on the content side.

4. `root/tune/level/territory/level.pop`
   - Wilderness population pressure.

5. `root/tune/settings/default.traffic`
   - Traffic/population pressure changes.

6. `root/tune/settings/ambientmgrtuning.xml`
   - Ambient actor cap / manager tuning.

7. `root/tune/ai/game_main.tr`
   - Companion/helper pulse scaffold on the tune side.

Pass 12 validation reported these all present: wilderness event set, empty country event set, wilderness population, player companion posse, companion AI pulse in tune/content, ambient actor cap 130, and playerally gang relations.

## Pass 14 payload coverage

Pass 14 correctly added/retained these later lanes:

- `CodeRED Empty World Activity`
- `tevent_rowdy_gangs`
- `tevent_lone_lawman`
- transport defense/simple events
- wagon thief
- broken wagon
- criminal chase
- Blackwater law/high-alert events
- Blackwater duel/standoff pressure
- lasso tuning changes in `lasso.tune`, `base_lasso.weap`, and `sheriff.xml`

However, the Pass 14 manifest only reports placement/lasso/sheriff updates and does not list Pass 12's broader payload set. That means these Pass 12 files are merge gaps/regression risks unless the next build explicitly rebases on Pass 12:

- `root/content/ambient/factionrelations.xml`
- `root/content/ai/game_main.tr`
- `root/tune/level/territory/level.pop`
- `root/tune/settings/default.traffic`
- `root/tune/settings/ambientmgrtuning.xml`
- `root/tune/ai/game_main.tr`

`root/content/ambient/placementglobals.xml` is also different between passes. It needs a manual merge, not a simple choose-one replacement: keep Pass 12 wilderness/companion sections and add Pass 13/14 empty-world + Blackwater sections.

## strings_d11generic.rpf findings

The uploaded `strings_d11generic.zip` contains `strings_d11generic.rpf` with a declared uncompressed size of 99,669,984 bytes. A raw string scan was completed on the extractable local segment available during this run and produced 211,296 readable strings. These findings are useful for research and naming, but stringtables are not spawn controllers by themselves.

Keyword counts from the raw string scan:

- `blackwater`: 33
- `duel`: 213
- `lasso`: 11
- `law`: 730
- `sheriff`: 114
- `marshal`: 311
- `bounty`: 20
- `wanted`: 22
- `holdup`: 112
- `gang`: 611
- `nightwatch`: 11
- `posse`: 153
- `weapon`: 45
- `alert`: 48
- `crime`: 357
- `standoff`: 0
- `unarmed`: 0

Useful string/actor-name leads:

- Blackwater: `BLACKWATER`, `BLACKWATER_COMPLETE`, `Blackwater_END`, `GY_Blackwater_boss`, `FBI05_DriveBak2Blackwater_*`
- Lawmen: `Law_Caucasian_Sheriff_Medium01` through `Law_Caucasian_Sheriff_Medium12`
- Town posse: `Law_Caucasian_TownPosse_Easy01` through `Law_Caucasian_TownPosse_Easy12`
- Marshals: `Law_Caucasian_USMarshal_Hard01` through `Law_Caucasian_USMarshal_Hard06`, `MISC_Deputy_Marshal01` through `MISC_Deputy_Marshal03`, `Companion_Marshal`
- Gang/outlaw: `Companion_OutLaw`, `Gang_BANDITO_*`, `Gang_CATTLERUSTLER_*`, `Gang_CRAZYMINER_*`, `Gang_DRUNKNDIRTY_*`, `Gang_IndianRAIDER_*`, `MISC_BillsGang01` through `MISC_BillsGang05`, `MISC_Outlaw_01`
- Duel: `CAUCASIAN_MALE_GUNSLINGER*_duelNotoriety_*`, `caucasian_male_gunslinger*_duelRude_*`, `Black_Male_Laborer09_duelRevenge_*`
- Lasso: `tes_lassoedSheriff`, `LASSO`, `LASSO_DES`, `LASSO_RAD`, `Release_lasso`
- Nightwatch: `BLIP_NIGHTWATCH`, `job_type_nightwatch`, `nightwatch_help`, `*_NIGHTWATCH_JOB_INTRO_*`
- Crimes: `crimeHoldUp`, `crimeHorseThief`, `crimeWagonTheif`, `beatLawmanArrest`, `law_wanted`, `get_wanted_poster`

## Next pass recommendation

Build Pass 15 from Pass 12, not Pass 14. Merge order:

1. Use Pass 12 archives as base.
2. Merge Pass 13 confirmed empty-world placement additions into `placementglobals.xml`.
3. Merge Pass 14 Blackwater law/duel/standoff additions into `placementglobals.xml`.
4. Keep Pass 12 `factionrelations.xml`, `content/ai/game_main.tr`, `level.pop`, `default.traffic`, `ambientmgrtuning.xml`, and `tune/ai/game_main.tr` unless a specific replacement is proven stronger.
5. Add Pass 14 lasso/sheriff/base_lasso tuning on top.
6. Validate all Pass 12 markers and all Pass 14 markers before packaging.

No feature should be dropped unless it demonstrably fails validation or crashes in testing.