# Code RED Camp Car Import Candidate Analysis

Scan file: `logs\camp_car_import_candidate_scan.json`
Total candidates in scan: `200`

## Verdict

The scan should be treated as a lead finder, not permission to patch. Top player-camp gringo scripts are the first inspection target for a runtime/script hook path. WSI/WGD placement remains a separate path and should not be bulk patched.

## Priority order

1. Inspect `playercamp##_gringo.wsc` candidates for camp gringo behavior and whether they reference usable camp actions.
2. Inspect `campfire##_always_gringo.wsc` as nearby camp behavior, not as the car host yet.
3. Inspect vehicle gringo/common scripts such as `Vehicle_Generator`, `car_gringo`, and `PlayerCar` if present in the extracted set.
4. Only after script/gringo behavior is understood, return to WSI/WGD placement correlation.

## Do not do yet

- Do not replace `playercamp01_gringo.wsc` directly in the game.
- Do not replace all player camp scripts.
- Do not bulk patch WSI/WGD/refgroup files.
- Do not install `camp_car_probe.xsc` into an archive until import/override behavior is separately proven.

## playercamp_gringo_scripts — 5 candidates

- score `82` — `content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc`
  - content hits: wsi
- score `70` — `content/release64/scripting/gringo/commonscripts/playercamp02_gringo.wsc`
- score `70` — `content/release64/scripting/gringo/commonscripts/playercamp03_gringo.wsc`
- score `70` — `content/release64/scripting/gringo/commonscripts/playercamp04_gringo.wsc`
- score `70` — `content/release64/scripting/gringo/commonscripts/playercampfootlocker.wsc`

## campfire_gringo_scripts — 17 candidates

- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_always_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_bad_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_law_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire02_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire03_bad_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire03_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire03_law_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire04_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire05_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire06_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire07_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfireindian_bad_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfireindian_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfirerebel_gringo.wsc`

## vehicle_gringo_scripts — 2 candidates

- score `55` — `content/release64/scripting/gringo/commonscripts/vehicle_generator.wsc`
- score `50` — `content/release64/scripting/gringo/gringobrains/gringobrainscripts/gen_vehicle_brain.wsc`

## car_gringo_scripts — 16 candidates

- score `50` — `content/release64/scripting/gringo/commonscripts/car_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/carcrank_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/playercar.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincar_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincararmored_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarbaggage_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarbox01_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarbox02_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarbox03_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarbox04_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarbox05_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarcaboose_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarcattle_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarflat_gringo.wsc`
- score `50` — `content/release64/scripting/gringo/commonscripts/traincarsteamer_gringo.wsc`

## wsi_wgd_placement — 0 candidates


## zombie_camp_gringos — 7 candidates

- score `65` — `content/release64/dlc/zombiepack/gringos/scripts/zombie_camp02_gringo.sco`
- score `65` — `content/release64/dlc/zombiepack/gringos/scripts/zombie_camp02_gringo.wsc`
- score `65` — `content/release64/dlc/zombiepack/gringos/scripts/zombie_camp03_gringo.sco`
- score `65` — `content/release64/dlc/zombiepack/gringos/scripts/zombie_camp03_gringo.wsc`
- score `64` — `content/dlc/zombiepack/gringos/zombie_camp02.xml`
  - content hits: camp, gringo
- score `64` — `content/dlc/zombiepack/gringos/zombie_camp03.xml`
  - content hits: camp, gringo
- score `56` — `content/dlc/zombiepack/gringos/dlc_rand_idle_sit_ground_player.xml`
  - content hits: camp, gringo, scripting

## script_slots — 156 candidates

- score `82` — `content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc`
  - content hits: wsi
- score `70` — `content/release64/scripting/gringo/commonscripts/playercamp02_gringo.wsc`
- score `70` — `content/release64/scripting/gringo/commonscripts/playercamp03_gringo.wsc`
- score `70` — `content/release64/scripting/gringo/commonscripts/playercamp04_gringo.wsc`
- score `70` — `content/release64/scripting/gringo/commonscripts/playercampfootlocker.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_always_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_bad_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire01_law_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire02_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire03_bad_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire03_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire03_law_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire04_gringo.wsc`
- score `65` — `content/release64/scripting/gringo/commonscripts/campfire05_gringo.wsc`

## Next command suggestions

Use these locally after the scan:

~~~powershell
Get-Content logs\camp_car_import_candidate_scan.md -TotalCount 80
Select-String -Path logs\camp_car_import_candidate_scan.csv -Pattern 'playercamp01_gringo|Vehicle_Generator|car_gringo|PlayerCar|wgd|wsi'
~~~
