# Code RED Vehicle Bridge ASI Scaffold

This is a conservative scaffold for the ScriptHook/ASI lane. It is not a finished
vehicle spawner. The goal is to keep custom behavior out of fragile compiled WSC
patches while Code RED uses WSC files as research maps.

## Intended workflow

1. Use `codered_vehicle_script_lab.py` to scan `playercar.wsc`,
   `beat_crime_wagonthief.wsc`, `vehicle_generator.wsc`, and tune resources.
2. Identify the native calls / templates / strings involved in making a vehicle
   active and driveable.
3. Implement the smallest ASI experiment possible: logging first, then controlled
   spawn/activation tests.
4. Keep original RPFs untouched. Put replacement resource files in copied RPFs only.

## Build notes

- Use Visual Studio x64 Release.
- Add your local ScriptHookRDR headers/libs when available.
- Keep logging on by default.
- Avoid hardcoded memory patching until native-call routes are proven.

