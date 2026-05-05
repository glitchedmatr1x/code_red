# Code RED Camp Car Probe Compile Proof — 2026-05-04

## Result

The camp-car runtime proof source compiled successfully after the compile batch copied the active real SC-CL include folder into the project-local include folder.

## Command sequence used

```powershell
py -3 script_compiling\sccl\projects\camp_car_probe\scripts\validate_camp_car_probe.py
script_compiling\sccl\compile_camp_car_probe_windows.bat
```

## Important note

The first validator run failed because the camp-car project-local include folder did not exist yet:

```text
project_include_exists: False
project_consts_exists: False
RESULT: FAIL
```

The compile batch then repaired the missing include by copying the active lane include into:

```text
script_compiling\sccl\projects\camp_car_probe\include
```

The compile succeeded.

## Compile proof

```text
[CodeRED] SC-CL exit: 0
```

## Output artifact

```text
script_compiling\sccl\output\camp_car_probe\camp_car_probe.xsc
length: 1026
sha1: 83823EAD70ECF075EF35AD38A85B910E04CCEAF8
```

## Runtime controls in probe

```text
Stand near/inside camp.
F5 = spawn ACTOR_VEHICLE_Car01 near the player
F6 = put player in car
F7 = re-apply vehicle tune
F8 = delete the probe car
```

## Boundary

Runtime proof only.

Not installed/imported into the game yet.

No camp files changed. No RPF/archive import. No whole-camp replacement.

## Follow-up fix

The camp-car compile batch was updated to self-validate after it repairs/copies project-local includes, so future runs should be less confusing.
