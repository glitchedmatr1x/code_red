<#
Force-install Code RED AI Menu spawn-safe data beside the game executable.

Use when the ASI loads but direct Car01/Truck01 raw actor spawns crash.
This script backs up the existing game-root data/codered files, then writes a
small spawn-safe probe roster and safe action list.

Run from repo root:
  powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_vehicle_first_menu_data_windows.ps1 -GameRoot "%RDR_GAME_DIR%"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$GameRoot
)

$ErrorActionPreference = "Stop"
$GameRoot = (Resolve-Path $GameRoot).Path
$DataDest = Join-Path $GameRoot "data\codered"
$Scratch = Join-Path $GameRoot "scratch"
$BackupRoot = Join-Path $GameRoot "data\codered_backups"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $BackupRoot "spawn_safe_backup_$Stamp"
$IniPath = Join-Path $GameRoot "CodeRED_AI_Menu.ini"

New-Item -ItemType Directory -Force -Path $DataDest | Out-Null
New-Item -ItemType Directory -Force -Path $Scratch | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

foreach ($name in @("npc_roster.txt", "ai_behavior_actions.csv", "actor_enum_map.csv")) {
    $src = Join-Path $DataDest $name
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $BackupDir $name) -Force
    }
}

$roster = @"
# CodeRED spawn-safe probe roster
# Installed by install_vehicle_first_menu_data_windows.ps1 after direct Car01/Truck01 crash.
# Raw CREATE_ACTOR_IN_LAYOUT vehicle spawns are not safe for mission cars/trucks.
# Car01 and Truck01 are intentionally parked for the WGD/gringo vehicle-generator lane.

ACTOR_RIDEABLE_ANIMAL_Horse01
ACTOR_RIDEABLE_ANIMAL_MEX_Mule01
ACTOR_RIDEABLE_ANIMAL_Buffalo
ACTOR_VEHICLE_Stagecoach
ACTOR_VEHICLE_Wagon02
ACTOR_VEHICLE_Coach01
ACTOR_VEHICLE_Cart01
"@
$roster | Set-Content -Path (Join-Path $DataDest "npc_roster.txt") -Encoding UTF8

$actions = @"
action,label,category,enabled,notes
spawn_selected_npc_request,Spawn Selected Safe Actor / Wagon,spawn,1,Uses selected roster label resolved through actor_enum_map.csv and CREATE_ACTOR_IN_LAYOUT; Car01 and Truck01 are blocked from raw spawn because they crashed
dismiss_ai_guest_request,Dismiss Spawned Actors,cleanup,1,Releases tracked CodeRED spawned actors
idle_spawned_request,Idle Spawned Actors,behavior,1,Clears current task and stands still
regroup_near_player_request,Regroup Near Player,behavior,1,Sends spawned actors near player
status_request,Status,debug,1,Reports native bridge, enum, tracked actors, and optional world scan support
follow_player_request,Follow Player,behavior,0,Disabled while testing spawn safety
guard_position_request,Stand Guard,behavior,0,Disabled while testing spawn safety
wander_spawned_request,Wander Spawned Actors,behavior,0,Disabled while testing spawn safety
make_spawned_lawmen_request,Make Spawned Actors Lawmen,faction,0,Disabled while testing spawn safety
side_lawman_immunity_request,Join Lawman Side,faction,0,Disabled while testing spawn safety
side_gang_immunity_request,Join Gang Side,faction,0,Disabled while testing spawn safety
restore_player_faction_request,Restore Player Faction,faction,0,Disabled while testing spawn safety
attack_nearest_hostile_request,Attack Nearest Hostile,combat,0,Disabled because unsafe world-scan/combat use can crash while spawn testing
"@
$actions | Set-Content -Path (Join-Path $DataDest "ai_behavior_actions.csv") -Encoding UTF8

$actorMap = @"
# CodeRED actor enum map
# Car01/Truck01 are documented here only, not placed in the default roster.
label,actor_enum,category,source,aliases,notes
ACTOR_RIDEABLE_ANIMAL_Horse01,976,rideable,CodeRED spawn-safe sanity map,ACTOR_RIDEABLE_ANIMAL_HORSE01|actor_rideable_animal_horse01|RIDEABLE_ANIMAL_Horse01|RIDEABLE_ANIMAL_HORSE01|rideable_animal_horse01|AE_RIDEABLE_ANIMAL_Horse01|AE_RIDEABLE_ANIMAL_HORSE01|ae_rideable_animal_horse01,canonical=ACTOR_RIDEABLE_ANIMAL_Horse01; hex=0x000003D0; spawn_safe=true
ACTOR_RIDEABLE_ANIMAL_MEX_Mule01,1000,rideable,CodeRED spawn-safe sanity map,ACTOR_RIDEABLE_ANIMAL_MEX_MULE01|actor_rideable_animal_mex_mule01|RIDEABLE_ANIMAL_MEX_Mule01|RIDEABLE_ANIMAL_MEX_MULE01|rideable_animal_mex_mule01|AE_RIDEABLE_ANIMAL_MEX_Mule01|AE_RIDEABLE_ANIMAL_MEX_MULE01|ae_rideable_animal_mex_mule01,canonical=ACTOR_RIDEABLE_ANIMAL_MEX_Mule01; hex=0x000003E8; spawn_safe=true
ACTOR_RIDEABLE_ANIMAL_Buffalo,1004,rideable,CodeRED spawn-safe sanity map,ACTOR_RIDEABLE_ANIMAL_BUFFALO|actor_rideable_animal_buffalo|RIDEABLE_ANIMAL_Buffalo|RIDEABLE_ANIMAL_BUFFALO|rideable_animal_buffalo|AE_RIDEABLE_ANIMAL_Buffalo|AE_RIDEABLE_ANIMAL_BUFFALO|ae_rideable_animal_buffalo,canonical=ACTOR_RIDEABLE_ANIMAL_Buffalo; hex=0x000003EC; spawn_safe=true
ACTOR_VEHICLE_Stagecoach,1177,vehicle,CodeRED spawn-safe sanity map,ACTOR_VEHICLE_STAGECOACH|actor_vehicle_stagecoach|VEHICLE_Stagecoach|VEHICLE_STAGECOACH|vehicle_stagecoach|AE_VEHICLE_Stagecoach|AE_VEHICLE_STAGECOACH|ae_vehicle_stagecoach,canonical=ACTOR_VEHICLE_Stagecoach; hex=0x00000499; spawn_safe_probe=true
ACTOR_VEHICLE_Cart01,1183,vehicle,CodeRED spawn-safe sanity map,ACTOR_VEHICLE_CART01|actor_vehicle_cart01|VEHICLE_Cart01|VEHICLE_CART01|vehicle_cart01|AE_VEHICLE_Cart01|AE_VEHICLE_CART01|ae_vehicle_cart01,canonical=ACTOR_VEHICLE_Cart01; hex=0x0000049F; spawn_safe_probe=true
ACTOR_VEHICLE_Wagon02,1199,vehicle,CodeRED spawn-safe sanity map,ACTOR_VEHICLE_WAGON02|actor_vehicle_wagon02|VEHICLE_Wagon02|VEHICLE_WAGON02|vehicle_wagon02|AE_VEHICLE_Wagon02|AE_VEHICLE_WAGON02|ae_vehicle_wagon02,canonical=ACTOR_VEHICLE_Wagon02; hex=0x000004AF; spawn_safe_probe=true
ACTOR_VEHICLE_Coach01,1202,vehicle,CodeRED spawn-safe sanity map,ACTOR_VEHICLE_COACH01|actor_vehicle_coach01|VEHICLE_Coach01|VEHICLE_COACH01|vehicle_coach01|AE_VEHICLE_Coach01|AE_VEHICLE_COACH01|ae_vehicle_coach01,canonical=ACTOR_VEHICLE_Coach01; hex=0x000004B2; spawn_safe_probe=true
ACTOR_VEHICLE_Car01,1194,vehicle_blocked,CodeRED unsafe raw spawn note,ACTOR_VEHICLE_CAR01|actor_vehicle_car01|VEHICLE_Car01|VEHICLE_CAR01|vehicle_car01|AE_VEHICLE_Car01|AE_VEHICLE_CAR01|ae_vehicle_car01,canonical=ACTOR_VEHICLE_Car01; hex=0x000004AA; blocked_from_default_roster=true; crashed_with_raw_CREATE_ACTOR_IN_LAYOUT; use WGD/gringo lane
ACTOR_VEHICLE_Truck01,1193,vehicle_blocked,CodeRED unsafe raw spawn note,ACTOR_VEHICLE_TRUCK01|actor_vehicle_truck01|VEHICLE_Truck01|VEHICLE_TRUCK01|vehicle_truck01|AE_VEHICLE_Truck01|AE_VEHICLE_TRUCK01|ae_vehicle_truck01,canonical=ACTOR_VEHICLE_Truck01; hex=0x000004A9; blocked_from_default_roster=true; use WGD/gringo lane
"@
$actorMap | Set-Content -Path (Join-Path $DataDest "actor_enum_map.csv") -Encoding UTF8

$ini = @"
[paths]
roster=data/codered/npc_roster.txt
actor_enum_map=data/codered/actor_enum_map.csv
behavior_actions=data/codered/ai_behavior_actions.csv
action_plan=scratch/codered_ai_action_plan.json
"@
$ini | Set-Content -Path $IniPath -Encoding UTF8

$report = [ordered]@{
    installed = (Get-Date).ToString('s')
    game_root = $GameRoot
    data_dest = $DataDest
    backup_dir = $BackupDir
    roster_count_expected = 7
    first_roster_entry = "ACTOR_RIDEABLE_ANIMAL_Horse01"
    blocked_raw_spawn_entries = @("ACTOR_VEHICLE_Car01", "ACTOR_VEHICLE_Truck01")
    note = "Spawn-safe AI menu data installed. Car01/Truck01 removed from raw spawn roster after crash."
}
$reportPath = Join-Path $DataDest "spawn_safe_install_report.json"
$report | ConvertTo-Json -Depth 5 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "# Code RED Spawn-Safe Menu Data Installed"
Write-Host "GameRoot:" $GameRoot
Write-Host "Data:" $DataDest
Write-Host "Backup:" $BackupDir
Write-Host "Roster first entry: ACTOR_RIDEABLE_ANIMAL_Horse01"
Write-Host "Blocked from raw spawn: ACTOR_VEHICLE_Car01, ACTOR_VEHICLE_Truck01"
Write-Host "Expected in-game footer: Roster 1-7 / 7 or similar, not / 11 or / 413"
Write-Host "Report:" $reportPath
