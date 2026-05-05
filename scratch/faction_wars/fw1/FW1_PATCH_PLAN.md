# Code RED Faction Wars FW-1 Patch Plan

Generated: `2026-05-05T07:16:07Z`

## Safety rule

This pass only stages local candidate resources. It does not patch source RPF archives, does not install scripts, and does not use the AI menu/native spawn lane.

## Recommended first patch

Start with: `research/blackwater_wsi_gringo_correlation_outputs/wgd_keyword_components.csv`

Reason: FW-1 phase

Patch only this one candidate first, then run copied-archive proof and reopen verification before touching any second file.

## Staged candidates

| Rank | Priority | Phase | Category | Source | Staged copy | Reason |
|---:|---:|---|---|---|---|---|
| 1 | 9270 | FW-1 tune/content pressure | world host / gringo | `research/blackwater_wsi_gringo_correlation_outputs/wgd_keyword_components.csv` | `scratch/faction_wars/fw1/staged_resources/research/blackwater_wsi_gringo_correlation_outputs/wgd_keyword_components.csv` | FW-1 phase |
| 2 | 3704 | FW-1 tune/content pressure | tune/template pressure | `research/CodeRED_Cutscene_Placement_Pass15_Build/reports/tune_refgroup_vehicle_cutscene_candidates.csv` | `scratch/faction_wars/fw1/staged_resources/research/CodeRED_Cutscene_Placement_Pass15_Build/reports/tune_refgroup_vehicle_cutscene_candidates.csv` | FW-1 phase; tune/template pressure |
| 3 | 3484 | FW-1 tune/content pressure | tune/template pressure | `research/modified_xml/placementglobals_15_50_rival_gang_towns.xml` | `scratch/faction_wars/fw1/staged_resources/research/modified_xml/placementglobals_15_50_rival_gang_towns.xml` | preferred patchable suffix; FW-1 phase; tune/template pressure; rival gang placement candidate |
| 4 | 2470 | FW-1 tune/content pressure | tune/template pressure | `research/15_50_rival_gang_towns_report.json` | `scratch/faction_wars/fw1/staged_resources/research/15_50_rival_gang_towns_report.json` | preferred patchable suffix; FW-1 phase; tune/template pressure; rival gang placement candidate |
| 5 | 2355 | FW-1 tune/content pressure | tune/template pressure | `research/Tune - Mirage Spawner/Prop List.xml` | `scratch/faction_wars/fw1/staged_resources/research/Tune - Mirage Spawner/Prop List.xml` | preferred patchable suffix; FW-1 phase; tune/template pressure |
| 6 | 2098 | FW-1 tune/content pressure | tune/template pressure | `research/Tune - Stronger NPC/Template/components.xml` | `scratch/faction_wars/fw1/staged_resources/research/Tune - Stronger NPC/Template/components.xml` | preferred patchable suffix; FW-1 phase; tune/template pressure; NPC template pressure candidate |
| 7 | 2039 | FW-1 tune/content pressure | tune/template pressure | `research/Tune - Stronger NPC/Template/template_base_human.xml` | `scratch/faction_wars/fw1/staged_resources/research/Tune - Stronger NPC/Template/template_base_human.xml` | preferred patchable suffix; FW-1 phase; tune/template pressure; NPC template pressure candidate |
| 8 | 2017 | FW-1 tune/content pressure | tune/template pressure | `research/CodeRED_Cutscene_Placement_Pass15_Build/reports/content_cutscene_vehicle_entries.csv` | `scratch/faction_wars/fw1/staged_resources/research/CodeRED_Cutscene_Placement_Pass15_Build/reports/content_cutscene_vehicle_entries.csv` | FW-1 phase; tune/template pressure |
| 9 | 1981 | FW-1 tune/content pressure | tune/template pressure | `research/Tune - Stronger NPC/Template/template_player.xml` | `scratch/faction_wars/fw1/staged_resources/research/Tune - Stronger NPC/Template/template_player.xml` | preferred patchable suffix; FW-1 phase; tune/template pressure; NPC template pressure candidate |
| 10 | 1505 | FW-1 tune/content pressure | tune/template pressure | `research/car_truck_inventory/car_truck_inventory.json` | `scratch/faction_wars/fw1/staged_resources/research/car_truck_inventory/car_truck_inventory.json` | preferred patchable suffix; FW-1 phase; tune/template pressure |
| 11 | 1505 | FW-1 tune/content pressure | tune/template pressure | `research/Tune - Max Render and Spawns/Tune/trees/treetypesettings.xml` | `scratch/faction_wars/fw1/staged_resources/research/Tune - Max Render and Spawns/Tune/trees/treetypesettings.xml` | preferred patchable suffix; FW-1 phase; tune/template pressure |
| 12 | 1487 | FW-1 tune/content pressure | tune/template pressure | `research/Tune - Max Render and Spawns/Tune/template/actions_templates.xml` | `scratch/faction_wars/fw1/staged_resources/research/Tune - Max Render and Spawns/Tune/template/actions_templates.xml` | preferred patchable suffix; FW-1 phase; tune/template pressure |

## Manual patch checklist

1. Open the staged copy, not the source file.
2. Make one conservative faction-war pressure change.
3. Record exact fields/values changed in this plan or a new report.
4. Use copied-archive RPF patch proof only after the staged file is reviewed.
5. Reopen/verify the copied archive before install.
6. Do not combine FW-1 with menu/native spawn changes.
