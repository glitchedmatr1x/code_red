# XSC LZX to PC WSC Candidate Conversion

No live game files or RPFs were modified.

- Output folder: `build\mp_script_conversion_probe\xsc_lzx_pc_wsc_magicrdr_fixed_subset`

## Status Counts

- `pc_wsc_magicrdr_table_candidate_runtime_unproven`: `4`

## Interpretation

This pass performs a real unwrap/decrypt/LZX-decompress/Zstandard-rewrap cycle for XENON `.xsc` resources. A successful row means Code RED can reopen the produced PC `.wsc` wrapper and recover the same decoded payload.

Runtime compatibility is still not guaranteed. The decoded script payload came from Xbox/XENON, so bytecode endianness, native table layout, and platform assumptions must be tested before using these in a gameplay RPF.

## Core Multiplayer Scripts

- `freemode/freemode.xsc` -> `pc_wsc_magicrdr_table_candidate_runtime_unproven` size=`47932` error=``
- `multiplayer_system_thread.xsc` -> `pc_wsc_magicrdr_table_candidate_runtime_unproven` size=`29529` error=``
- `multiplayer_update_thread.xsc` -> `pc_wsc_magicrdr_table_candidate_runtime_unproven` size=`22948` error=``
- `pr_multiplayer.xsc` -> `pc_wsc_magicrdr_table_candidate_runtime_unproven` size=`14522` error=``
