# XSC LZX to PC WSC Candidate Conversion

No live game files or RPFs were modified.

- Output folder: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe\xsc_lzx_pc_wsc_converted`

## Status Counts

- `pc_wsc_candidate_decode_ok_runtime_unproven`: `56`

## Interpretation

This pass performs a real unwrap/decrypt/LZX-decompress/Zstandard-rewrap cycle for XENON `.xsc` resources. A successful row means Code RED can reopen the produced PC `.wsc` wrapper and recover the same decoded payload.

Runtime compatibility is still not guaranteed. The decoded script payload came from Xbox/XENON, so bytecode endianness, native table layout, and platform assumptions must be tested before using these in a gameplay RPF.

## Core Multiplayer Scripts

- `ctf/ctf_base_game.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`45649` error=``
- `deathmatch/deathmatch.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`34747` error=``
- `freemode/freemode.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`47921` error=``
- `mp_idle.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`41676` error=``
- `multiplayer_system_thread.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`29531` error=``
- `multiplayer_update_thread.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`22949` error=``
- `pr_multiplayer.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`14522` error=``
- `support/mp_actorpicker.xsc` -> `pc_wsc_candidate_decode_ok_runtime_unproven` size=`20335` error=``
