# Code RED Camp Additive Car Mod Target — 2026-05-04

## Question

Can Code RED mod the camp to have a car in it instead of replacing the whole camp once the compile/import lanes are ready?

## Answer

Yes. The preferred target is an additive camp car, not a whole camp replacement.

## Safer approaches

### 1. Runtime proof first

Use the proven SC-CL compile lane or ScriptHook/AI Trainer lane to spawn a car near the active/player camp coordinates.

Purpose:

```text
prove vehicle model
prove camp-safe coordinates
prove player can see/use it
prove it does not delete/replace camp props
```

This avoids touching camp content until the actor/model/path is proven.

### 2. Additive content placement second

After runtime proof, add or clone one placement entry in the correct camp/world placement layer.

Do not replace the whole camp file or camp template.

Target behavior:

```text
original camp stays intact
one car actor/prop/gringo host is added beside camp
camp persistence remains unchanged
```

### 3. Gringo/vehicle-generator host if needed

If `car01` is not valid as a standalone placement, use the existing vehicle-gringo research lane:

```text
WSI placement -> WGD gringo host -> Vehicle_Generator / car_gringo / PlayerCar path
```

This matters because previous research showed replacing a static WSI car prop with `car01` can remove the old prop without spawning a real car.

## Not recommended

```text
replace whole camp template
replace camp file globally
bulk patch all camp placements
replace wagons/camps blindly
install compiled scripts into game before import lane proof
```

## Best next pass

Build a small `camp_car_probe` lane:

```text
1. Find active player camp placement/name/path candidates.
2. Find safe camp coordinates and nearby existing objects.
3. Runtime spawn `ACTOR_VEHICLE_Car01` near camp using compiled proof or trainer bridge.
4. Log whether the car appears, is usable, and persists through camp reload.
5. Only then build copied-archive additive placement proof.
```

## Boundary

The SC-CL compile lane is proven, but archive install/import is not proven yet. Keep this as a proof plan until import/override is separately validated.
