# Code RED Camp Car Runtime Proof

This package is proof-only.

## Compiled / candidate artifacts

~~~text
script_compiling\sccl\output\camp_car_probe\camp_car_probe.xsc
sha1: C8DC6821D04A76302C123814A8DCBD507DD6200E
length: 1158

script_compiling\sccl\output\camp_car_probe_sco\camp_car_probe.sco
sha1: 0351E47E3B0F5C6BA7C8D75A6C8FDA92A78D8C8B
length: 1075

script_compiling\sccl\output\camp_car_probe_wsc\camp_car_probe.wsc
sha1: 2729784CA37478DD22E0CFE8BD52B11793A36E14
length: 1158

~~~

## Runtime controls

~~~text
Stand near/inside camp.
F5 = spawn ACTOR_VEHICLE_Car01 near the player
F6 = put player in car
F7 = re-apply vehicle tune
F8 = delete the probe car
F9 = delete/re-spawn farther away
F10 = show help
~~~

## Boundary

Do not install/import these compiled scripts into the game yet.

This proves the SC-CL camp-car runtime proof compile only. Camp/RPF archive install behavior is still a separate lane.

The .wsc artifact is an experimental candidate generated from the compiled .xsc; it is not proven game-loadable yet.

## Included

~~~text
artifact/camp_car_probe.xsc
artifact/camp_car_probe.sco if built
artifact/camp_car_probe.wsc if exported
source/main.c
headers/include/
reports/
COMPILE_PROOF_MANIFEST.json
~~~
