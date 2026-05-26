# XSC LZX to PC WSC Candidate Conversion

No live game files or RPFs were modified.

- Output folder: `D:\Games\Red Dead Redemption\Code_RED\build\mp_xenon_full_conversion_pass2\converted_extensionless_editable_wsc`

## Status Counts

- `pc_wsc_magicrdr_table_candidate_runtime_unproven`: `8`

## Interpretation

This pass performs a real unwrap/decrypt/LZX-decompress/Zstandard-rewrap cycle for XENON `.xsc` resources. A successful row means Code RED can reopen the produced PC `.wsc` wrapper and recover the same decoded payload.

Runtime compatibility is still not guaranteed. The decoded script payload came from Xbox/XENON, so bytecode endianness, native table layout, and platform assumptions must be tested before using these in a gameplay RPF.

## Core Multiplayer Scripts

