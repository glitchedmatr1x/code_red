Code RED Car/Truck Mission Recipe Pass 29
=========================================

This package is research/tooling only. It does not include content.rpf, tune_d11generic.rpf, or any ASI.

What this pass extracts from the MagicRDR decompiled mission script:
- 1194 = ACTOR_VEHICLE_Car01
- 1193 = ACTOR_VEHICLE_Truck01
- Local_6 + 1184[02] is the mission vehicle actor handle in the FBI vehicle mission lane.
- Function_453 starts and enables the engine.
- Function_408/428/452 put mission actors into the vehicle or task them into it.
- Function_956 creates the carSettings bitmask: 1017.
- Function_646/794 prove population can return actor enums directly through GET_RAND_ACTORENUM_FROM_POPULATION_NATIVE.

Main takeaway:
The next real patch should not be more wagon template morphing. The stronger direction is either:
1. runtime/native spawn proof using actor enum 1194/1193, or
2. SCR02 population decode to force a population return value to 1194/1193.

Do not raw patch FBI02/FBI04 WSC yet. RSC85 raw offsets are not mapped to MagicRDR script positions.
