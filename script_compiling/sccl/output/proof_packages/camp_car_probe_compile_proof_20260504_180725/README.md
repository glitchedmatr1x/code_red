# Code RED Camp Car Runtime Proof

This package is proof-only.

## Compiled artifacts

~~~text
script_compiling\sccl\output\camp_car_probe\camp_car_probe.xsc
sha1: 83823EAD70ECF075EF35AD38A85B910E04CCEAF8
length: 1026

script_compiling\sccl\output\camp_car_probe_sco\camp_car_probe.sco
sha1: 5B29D89E58E61171B6BAD30DC3B859B234F886DE
length: 943

~~~

## Runtime controls

~~~text
Stand near/inside camp.
F5 = spawn ACTOR_VEHICLE_Car01 near the player
F6 = put player in car
F7 = re-apply vehicle tune
F8 = delete the probe car
~~~

## Boundary

Do not install/import these compiled scripts into the game yet.

This proves the SC-CL camp-car runtime proof compile only. Camp/RPF archive install behavior is still a separate lane.

## Included

~~~text
artifact/camp_car_probe.xsc
artifact/camp_car_probe.sco if built
source/main.c
headers/include/
reports/
COMPILE_PROOF_MANIFEST.json
~~~
