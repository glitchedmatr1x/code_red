# Faction Wars 1.zip audit

## Verdict

This is a real loose-resource mod package, not just a tool/report bundle. It contains `tune/`, `content/`, and `naturalmotion/` folders. The most important discovery is that it already includes the real loose `content/ambient/factionrelations.xml`, so we do not need to keep hunting through research indexes for faction relations.

## Package counts

- Files: `1618`
- Top folders: `tune:1579, content:36, naturalmotion:3`
- Common extensions: `.refgroup:860, .xml:247, .rmptx:113, .vehgyro:42, .vehinput:42, .vehmodel:42, .vehsim:42, .vehstuck:42, .dds:41, .tr:29, .vehdraft:21, .ppp:20`

## Key files found

- `content/ambient/factionrelations.xml` — 72656 bytes
- `content/ambient/placementglobals.xml` — 7356 bytes
- `content/ai/human_combat.tr` — 69142 bytes
- `content/ai/human_hostile.tr` — 7012 bytes
- `content/ai/human_guard.tr` — 15639 bytes
- `tune/asd/npc.xml` — 12369 bytes
- `tune/asd/sheriff.xml` — 12366 bytes
- `tune/template/template_base_human.xml` — 3299 bytes
- `tune/template/components.xml` — 31112 bytes
- `tune/template/actions_templates.xml` — 64795 bytes
- `naturalmotion/behaviours.xml` — 212830 bytes

## XML validation

- XML files checked: `247`
- XML parser issues: `1`
  - `tune/player/input_car.xml` — XML or text declaration not at start of entity: line 2, column 0

Note: `tune/player/input_car.xml` appears to have a blank line before the XML declaration. That is easy to fix for tools; the game may tolerate it, but XML parsers do not.

## factionrelations.xml summary

- Factions: `33`
- Law-enforcement factions: `LawEnforcement, USLawEnforcement, IndianLawEnforcement, MexicanLawEnforcement`
- Lawful-to-attack factions: `MexicanBandito, GenericCriminal, CattleRustler, IndianRaider, AnimalPredator, PlayerEnemy, PlayerHostile, TreasureHunter, DrunkNDirty, MexicanRebel, PlayerMpTeam1, PlayerMpTeam2, PlayerMpTeamFfa, PlayerMpTeamCoop, Zombie`
- Relationship values: `Enemy:158, Ally:26, Friendly:36, Neutral:59, Hostile:93`

### Selected law/gang relationships

| Source | Target | Relationship |
|---|---|---|
| Player | Player | Enemy |
| Player | MexicanBandito | Hostile |
| Player | GenericCriminal | Hostile |
| Player | CattleRustler | Hostile |
| Player | IndianRaider | Hostile |
| Player | MexicanSoldier | Hostile |
| Bystander | Player | Neutral |
| Bystander | Bystander | Friendly |
| Bystander | LawEnforcement | Friendly |
| Bystander | MexicanBandito | Hostile |
| Bystander | GenericCriminal | Enemy |
| Bystander | CattleRustler | Hostile |
| Bystander | IndianRaider | Hostile |
| Bystander | MexicanSoldier | Hostile |
| USBystander | USBystander | Friendly |
| USBystander | MexicanBystander | Neutral |
| USBystander | USLawEnforcement | Friendly |
| USBystander | MexicanBandito | Enemy |
| USBystander | GenericCriminal | Hostile |
| USBystander | CattleRustler | Hostile |
| USBystander | IndianRaider | Enemy |
| USBystander | MexicanSoldier | Enemy |
| MexicanBystander | USBystander | Neutral |
| MexicanBystander | MexicanBystander | Friendly |
| MexicanBystander | MexicanLawEnforcement | Friendly |
| MexicanBystander | MexicanBandito | Neutral |
| MexicanBystander | GenericCriminal | Enemy |
| MexicanBystander | CattleRustler | Enemy |
| MexicanBystander | IndianRaider | Enemy |
| MexicanBystander | MexicanSoldier | Hostile |
| LawEnforcement | Bystander | Friendly |
| LawEnforcement | LawEnforcement | Ally |
| USLawEnforcement | USBystander | Friendly |
| USLawEnforcement | USLawEnforcement | Ally |
| USLawEnforcement | MexicanLawEnforcement | Hostile |
| USLawEnforcement | BountyHunter | Neutral |
| USLawEnforcement | MexicanBandito | Enemy |
| USLawEnforcement | GenericCriminal | Enemy |
| USLawEnforcement | CattleRustler | Enemy |
| USLawEnforcement | IndianRaider | Enemy |
| USLawEnforcement | MexicanSoldier | Enemy |
| MexicanLawEnforcement | MexicanBystander | Friendly |
| MexicanLawEnforcement | USLawEnforcement | Hostile |
| MexicanLawEnforcement | MexicanLawEnforcement | Ally |
| MexicanLawEnforcement | BountyHunter | Friendly |
| MexicanLawEnforcement | MexicanBandito | Enemy |
| MexicanLawEnforcement | MexicanRebel | Enemy |
| MexicanLawEnforcement | GenericCriminal | Enemy |
| MexicanLawEnforcement | CattleRustler | Enemy |
| MexicanLawEnforcement | IndianRaider | Enemy |
| MexicanLawEnforcement | MexicanSoldier | Friendly |
| BountyHunter | USLawEnforcement | Friendly |
| BountyHunter | MexicanLawEnforcement | Friendly |
| BountyHunter | BountyHunter | Ally |
| BountyHunter | MexicanBandito | Hostile |
| BountyHunter | GenericCriminal | Enemy |
| BountyHunter | CattleRustler | Hostile |
| BountyHunter | IndianRaider | Hostile |
| BountyHunter | MexicanSoldier | Hostile |
| MexicanBandito | Player | Hostile |
| MexicanBandito | Bystander | Friendly |
| MexicanBandito | USBystander | Friendly |
| MexicanBandito | MexicanBystander | Neutral |
| MexicanBandito | USLawEnforcement | Enemy |
| MexicanBandito | MexicanLawEnforcement | Enemy |
| MexicanBandito | BountyHunter | Enemy |
| MexicanBandito | MexicanBandito | Ally |
| MexicanBandito | GenericCriminal | Enemy |
| MexicanBandito | CattleRustler | Enemy |
| MexicanBandito | IndianRaider | Enemy |
| MexicanBandito | MexicanSoldier | Enemy |
| GenericCriminal | Player | Hostile |
| GenericCriminal | Bystander | Hostile |
| GenericCriminal | USBystander | Hostile |
| GenericCriminal | MexicanBystander | Hostile |
| GenericCriminal | USLawEnforcement | Hostile |
| GenericCriminal | MexicanLawEnforcement | Hostile |
| GenericCriminal | BountyHunter | Enemy |
| GenericCriminal | MexicanBandito | Enemy |
| GenericCriminal | GenericCriminal | Ally |
| GenericCriminal | CattleRustler | Enemy |
| GenericCriminal | IndianRaider | Enemy |
| GenericCriminal | MexicanSoldier | Enemy |
| CattleRustler | Player | Hostile |
| CattleRustler | Bystander | Hostile |
| CattleRustler | USBystander | Hostile |
| CattleRustler | MexicanBystander | Hostile |
| CattleRustler | USLawEnforcement | Enemy |
| CattleRustler | MexicanLawEnforcement | Enemy |
| CattleRustler | BountyHunter | Hostile |
| CattleRustler | MexicanBandito | Enemy |
| CattleRustler | GenericCriminal | Enemy |
| CattleRustler | CattleRustler | Ally |
| CattleRustler | IndianRaider | Enemy |
| CattleRustler | MexicanSoldier | Enemy |
| IndianRaider | Player | Enemy |
| IndianRaider | Bystander | Enemy |
| IndianRaider | USBystander | Enemy |
| IndianRaider | MexicanBystander | Enemy |
| IndianRaider | USLawEnforcement | Enemy |
| IndianRaider | MexicanLawEnforcement | Enemy |
| IndianRaider | BountyHunter | Enemy |
| IndianRaider | MexicanBandito | Enemy |
| IndianRaider | GenericCriminal | Enemy |
| IndianRaider | CattleRustler | Enemy |
| IndianRaider | IndianRaider | Ally |
| IndianRaider | MexicanSoldier | Enemy |
| MexicanSoldier | Player | Hostile |
| MexicanSoldier | Bystander | Hostile |
| MexicanSoldier | USBystander | Enemy |
| MexicanSoldier | MexicanBystander | Friendly |
| MexicanSoldier | USLawEnforcement | Enemy |
| MexicanSoldier | MexicanLawEnforcement | Enemy |
| MexicanSoldier | BountyHunter | Hostile |
| MexicanSoldier | MexicanBandito | Enemy |
| MexicanSoldier | MexicanRebel | Enemy |
| MexicanSoldier | GenericCriminal | Enemy |
| MexicanSoldier | CattleRustler | Enemy |
| MexicanSoldier | IndianRaider | Enemy |
| MexicanSoldier | MexicanSoldier | Ally |
| MexicanRebel | MexicanLawEnforcement | Enemy |
| MexicanRebel | MexicanSoldier | Enemy |
| MexicanRebel | MexicanRebel | Ally |
| MexicanRebel | Player | Neutral |

## placementglobals.xml summary

- Events/sets listed: `39`
  - `Events`: `beacon_transport_defend`
  - `Events`: `beacon_transport_simple`
  - `Events`: `event_roadside_ambush`
  - `Events`: `beat_roadside_robbery`
  - `Events`: `event_raodside_prisoners`
  - `Events`: `beat_crime_wagonthief`
  - `Events`: `event_roadside_dig_grave`
  - `Events`: `event_roadside_execution`
  - `Events`: `event_roadside_eating`
  - `Events`: `event_roadside_aftermath`
  - `Events`: `beacon_wilderness_dynomite`
  - `Events`: `event_gnrc_rescue_beacon`
  - `Events`: `beacon_escort_criminals`
  - `Events`: `event_coyote_chase`
  - `Events`: `event_loot_dead_body`
  - `Events`: `event_wild_animals`
  - `Events`: `event_stickup`
  - `Events`: `event_crazy_hermit`
  - `Events`: `event_wilderness_drunks`
  - `Events`: `event_wilderness_dynomite`
  - `Events`: `event_lone_stranger`
  - `Events`: `event_night_procession`
  - `Events`: `event_criminal_chase`
  - `Events`: `event_hanging`
  - `Events`: `event_treasurehunter_intro`
  - `Events`: `event_herbalist_intro`
  - `Events`: `event_hunter_intro`
  - `Events`: `event_sharpshooter_challenge`
  - `Events`: `mexican_rev_rebelCamp`
  - `Events`: `event_broken_wagon01`
  - `Events`: `event_campfire01`
  - `Events`: `event_landmark_attack`
  - `AllowEventSets`: `All Events`
  - `AllowEventSets`: `Roadside Events`
  - `AllowEventSets`: `Trailside Events`
  - `AllowEventSets`: `Wilderness Normal (30-60m from any road/train/path)`
  - `AllowEventSets`: `Wilderness Isolated (60m from any road/train/path)`
  - `DenyEventSets`: `Tree Problems`
  - `DenyEventSets`: `Approach Events / Pathfinding issues`

## Practical next mod step

1. Patch `content/ambient/factionrelations.xml` first: harden law-vs-criminal/gang hostility and ensure criminal/bandit factions are lawful-to-attack. This file is real and present in this zip.
2. Patch `content/ambient/placementglobals.xml` second: it is compact and generic; use it for more crime/law/gang/roadside/wilderness event sets, not town-specific blocks unless we add those deliberately.
3. Patch `tune/template/template_base_human.xml` and `tune/template/components.xml` third: improve hearing/awareness/hostile targeting carefully.
4. Keep content `.tr` AI rule files as reviewable loose text, but do not change them until XML changes are proven in-game.