# Code RED Working Event Seat/Control Test Kit v1

Purpose: keep the next in-game tests focused on the WSCs that already showed useful results, instead of patching broad population/global files.

## Stable test targets

1. `beat_crime_wagonthief.wsc`
   - Confirmed good gameplay target.
   - Goal: NPC-driven Truck01 / Car01 event, then runtime seat/control unlock.
   - Best for: NPC chauffeur + player riding/gunner tests.

2. `event_roadside_ambush.wsc`
   - Confirmed patch works, but only one actual vehicle handle.
   - Goal: verify whether the spawned car/truck can be seat-unlocked.
   - Best for: single ambush vehicle control tests.

3. `event_roadside_prisoners.wsc`
   - Confirmed car/truck direct replacement works.
   - Goal: transport-style vehicle replacement, then seat/control unlock.
   - Best for: transport/prison-wagon replacement tests.

4. `short_update_thread.wsc`
   - Do not patch broadly for now.
   - Use only as reference/global suspect until runtime seat unlock is proven.

## Why runtime unlock next

The WSC patches can make events spawn `1193 = Truck01` and `1194 = Car01`.
The remaining problem is runtime state:
- disabled seats
- driver seat locked
- NPC/event brain owns the vehicle
- gringo/use systems attaching the player to non-driver positions

The trainer-style control chain is the baseline:
- `SET_VEHICLE_ALLOWED_TO_DRIVE(vehicle, true)`
- `ENABLE_VEHICLE_SEAT(vehicle, 0, true)`
- `SET_ACTOR_AUTO_TRANSITION_TO_DRIVER_SEAT(player, true)`
- `SET_ACTOR_IN_VEHICLE(player, vehicle, 0)`
- `START_VEHICLE(vehicle)`
- `SET_VEHICLE_ENGINE_RUNNING(vehicle, true)`

For Code RED we want a runtime test that repeats seat enabling for nearby `1193/1194` vehicles, because WSC logic may disable seats again after spawn.

## Test order

Use one event patch at a time. Do not stack population, dynamite, roadside robbery, or short-update experiments.

### Test A: WagonThief
Install only the known-good WagonThief car/truck WSC.
Trigger WagonThief.
Use runtime seat/control unlock hotkey.
Expected:
- NPC truck/car still spawns
- NPC can keep driving
- player can try entering driver/passenger/gunner seats
- no crash

### Test B: Ambush
Install only the Ambush car/truck WSC.
Trigger roadside ambush.
Use runtime seat/control unlock hotkey.
Expected:
- one vehicle appears
- seats/control unlock attempt does not crash
- record whether player can enter/use it

### Test C: Prisoners
Install only the Prisoners `1197 -> 1193 Truck01` WSC.
Trigger prisoner transport.
Use runtime seat/control unlock hotkey.
Expected:
- prison wagon replacement appears as Truck01
- seats/control unlock attempt does not crash
- record whether transport behavior survives

## Rollback rule

If a test crashes:
1. remove the event WSC patch
2. remove runtime unlocker
3. return to the last known good file
4. test the next event separately

Do not test the 880-replacement dynamite/convoy broad patch or the 165-replacement Roadside Robbery broad patch in this lane.