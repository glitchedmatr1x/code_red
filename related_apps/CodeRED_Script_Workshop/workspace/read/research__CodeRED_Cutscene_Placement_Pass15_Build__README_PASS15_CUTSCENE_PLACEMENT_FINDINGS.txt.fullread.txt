Code RED Pass 15 - Cutscene / Placement Correlator Research
==============================================================

Research-only. No game patch is included.

Why this pass exists
--------------------
The user suspected cutscenes and mission resources would reveal how Rockstar places actors, props, vehicles, cameras, and scripted objects. That direction is correct, but the safe route is not to patch the compiled cutscene scripts directly yet.

What was scanned
----------------
- content.rpf cutscene/camera/gringo/wagon/car/train entries
- tune_d11generic.rpf refgroups, vehicle templates, locsets, and vehicle text resources
- blackwater.rpf / blackwater.wsi placement resource

Key result
----------
Blackwater WSI is the strongest placement clue so far. It decodes as an RSC/zstd resource and contains hashed object placement records. The scan matched candidate names from tune/content resources back into WSI hash slots.

Strong Blackwater WSI wagon placement hits:

- i_gen_wagonParts03x at decoded offset 1163200 hash 0x4BC41017
  vec -48: [741.263062, 80.248344, 1417.242065]
  vec -32: [741.191956, 80.224312, 1416.548462]
  vec -16: [744.690735, 81.567451, 1419.016235]

- i_gen_wagonBroken02x at decoded offset 1165440 hash 0xAC84C193
  vec -48: [723.793213, 79.2099, 1419.701904]
  vec -32: [719.840637, 79.106247, 1418.24707]
  vec -16: [724.79303, 81.841583, 1422.198975]


Interpretation
--------------
The vectors are not yet labeled with certainty, but they look like placement bounds/transform-adjacent values. The hash offset repeatedly appears at a 224-byte stride-style record layout. That is a major clue for exact placement editing.

What not to patch yet
---------------------
- Do not bulk edit cutscene WSC files.
- Do not patch long_update_thread.
- Do not use old CodeRED_AI_Menu.asi.
- Do not try to make drivable Car01 appear through WSI until a valid static car/prop hash is confirmed.

Best next patch
---------------
A copied-archive WSI proof:
1. Pick one harmless Blackwater WSI wagon prop placement.
2. Replace only that placement hash with another confirmed static prop hash of the same placement type.
3. Repack blackwater.rpf copy.
4. Verify that the WSI reopens and the hash changed.
5. Test in-game near Blackwater.

If that works, then we use WSI placement records for exact object placement and use scripts/tune only for behavior.
