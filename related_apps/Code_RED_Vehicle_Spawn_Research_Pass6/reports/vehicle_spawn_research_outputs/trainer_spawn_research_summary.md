# Code RED — Trainer-Style Vehicle Spawn Research Summary

## Bottom line

The wagon/cart placement mutation path is too unstable for vehicle experiments. The confirmed safe idea is to use WSI only for removing/clearing static blocker props, then move real vehicles through runtime/gringo/script paths.

## Strongest leads

The decoded WGD export identifies the real vehicle behavior layer:

- `Vehicle_Generator`
- `car_gringo`
- `PlayerCar`
- `CarCrank_gringo`
- `Gen_Vehicle_Brain`
- `GatlingAttachGringo`
- `TurretAttachMover`
- `TrainGringo`
- `trainCar_*_gringo`

The tune/content string scan adds runtime/mission vocabulary:

- `AE_Companion_FBI`
- `AE_Caucasian_Male_SteamEngineDriver01`
- `Coach_Passenger`
- `CRM_ROB_COACH`
- `CRM_ROB_TRAIN`
- `Drive_Stagecoach`
- `Enter_Minecart`
- `horse_matchspeed_train`
- `horse_matchspeed_wagon`
- `out_warn_vehicle`
- `PASS_COACH_*`
- `passenger0..3`
- `Steal_Wagon`
- `taxi_coach_help`
- `trainmarshal_help`
- `tutorial_law_posse_spawn`

## Next move

Build a runtime callsite resolver that focuses on FBI, coach, train, wagon, and Vehicle_Generator WSC/RSC resources. Compare those against trainer spawn labels if available.
