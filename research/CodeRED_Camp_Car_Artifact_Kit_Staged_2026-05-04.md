# Code RED Camp Car Artifact Kit Staged — 2026-05-04

## Command

```powershell
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_camp_car_artifacts_windows.ps1
```

## Result

```text
Kit: script_compiling\sccl\output\playtest_kits\camp_car_artifacts_20260504_192307
ZIP: script_compiling\sccl\output\playtest_kits\camp_car_artifacts_20260504_192307.zip
ZIP SHA1: 7B182C7A2044F12549E80AC1171F2CBC6CD52DD2
```

## Artifacts

```text
script_compiling\sccl\output\camp_car_probe\camp_car_probe.xsc
length: 1158
sha1: C8DC6821D04A76302C123814A8DCBD507DD6200E

script_compiling\sccl\output\camp_car_probe_sco\camp_car_probe.sco
length: 1075
sha1: 0351E47E3B0F5C6BA7C8D75A6C8FDA92A78D8C8B

script_compiling\sccl\output\camp_car_probe_wsc\camp_car_probe.wsc
length: 1158
sha1: 2729784CA37478DD22E0CFE8BD52B11793A36E14
```

## Boundary

Local staging only. No game/archive files were modified by the staging script.

## Runtime controls if the script loads

```text
F5 = spawn ACTOR_VEHICLE_Car01 near player/camp
F6 = put player in spawned car
F7 = re-apply vehicle tuning
F8 = delete probe car
F9 = delete/re-spawn farther away
F10 = show help
```

## Next step

Use the staged kit for manual in-game loading/import experiments from a backed-up mod workspace.
