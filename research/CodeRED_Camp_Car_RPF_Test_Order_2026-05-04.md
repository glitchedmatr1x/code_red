# Code RED Camp Car RPF Test Order — 2026-05-04

## Question

Can the staged camp-car proof files be put into an RPF instead of using the trainer/loose-loader route?

## Answer

Yes, but match the file type to the target slot.

## Proven artifacts

```text
camp_car_probe.xsc
length: 1158
sha1: C8DC6821D04A76302C123814A8DCBD507DD6200E

camp_car_probe.sco
length: 1075
sha1: 0351E47E3B0F5C6BA7C8D75A6C8FDA92A78D8C8B

camp_car_probe.wsc candidate
length: 1158
sha1: 2729784CA37478DD22E0CFE8BD52B11793A36E14
header: 52 53 43 85 / RSC.
```

## Recommended RPF experiment order

### 1. WSC camp gringo slot

Use the staged WSC candidate and test it against a WSC slot first.

Most direct first target:

```text
content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc
```

Test in-game near/inside camp.

Expected script controls if it loads:

```text
F10 = show help
F5 = spawn ACTOR_VEHICLE_Car01 near player/camp
F6 = enter spawned car
F7 = re-apply tune
F8 = delete probe car
F9 = re-spawn farther away
```

### 2. WSC vehicle gringo slots

If the player camp slot does not run the script, test WSC vehicle behavior slots next:

```text
content/release64/scripting/gringo/commonscripts/vehicle_generator.wsc
content/release64/scripting/gringo/commonscripts/car_gringo.wsc
content/release64/scripting/gringo/commonscripts/playercar.wsc
```

### 3. SCO slot only if target is SCO

Use the SCO artifact only for an SCO slot or loader path.

Do not put `.sco` into a `.wsc` slot.

### 4. XSC slot only if target is XSC

Use the XSC artifact only for a known XSC slot.

Do not put `.xsc` into a `.wsc` slot.

## Boundary

This is an experiment plan for a backed-up mod workspace.

Do not mix file types blindly:

```text
WSC candidate -> WSC slot
SCO -> SCO slot
XSC -> XSC slot
```

The RPF import tool/override path is separate from SC-CL compile proof.
