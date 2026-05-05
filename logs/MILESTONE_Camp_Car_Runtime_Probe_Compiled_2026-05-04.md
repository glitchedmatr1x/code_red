# Milestone — Camp Car Runtime Probe Compiled

Date: 2026-05-04

## Status

The Code RED camp-car runtime proof compiled cleanly.

## Command

```powershell
script_compiling\sccl\compile_camp_car_probe_windows.bat
```

## Result

```text
[CodeRED] SC-CL exit: 0
Artifact count: 1
```

## Output artifact

```text
script_compiling\sccl\output\camp_car_probe\camp_car_probe.xsc
length: 1026
sha1: 83823EAD70ECF075EF35AD38A85B910E04CCEAF8
```

## Runtime proof intent

```text
Stand near/inside camp.
F5 = spawn ACTOR_VEHICLE_Car01 near the player
F6 = put player in car
F7 = re-apply vehicle tune
F8 = delete the probe car
```

## Boundary

This is a runtime proof artifact only.

No camp files were changed.
No RPF/archive import was performed.
No whole-camp replacement was performed.

## Next safe pass

Package the camp-car proof artifact and then research the archive/import or override path separately before any game install attempt.
