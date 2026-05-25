# XSC -> WSC Magic RDR Compatibility Report

## Result

The converter now has a Magic RDR compatibility lane. The old output was only Code RED-decodable; Magic RDR decompressed it but failed in `ScriptFile` because XENON script tables were still big-endian while PC/Switch WSC mode reads script structure tables as little-endian.

Fixed conversion now performs:

1. XENON header normalize: `.xsc` `85CSR` -> `RSC85` header order.
2. AES decrypt of payload.
3. Xbox XCompress/LZX decode.
4. Script table endian normalization:
   - script main header words
   - code page pointer table
   - native hash table
   - static table
5. Preserve bytecode instruction bytes.
6. Rewrap as PC/Switch-style RSC85 WSC with Zstandard + AES.
7. Validate with Code RED and Magic RDR parser.

## Validation Levels Reached

- LEVEL 1 Code RED decrypt/decompress/reopen: PASS, 56/56.
- LEVEL 2 Magic RDR opens standalone WSC: PASS, 56/56.
- LEVEL 3 Magic RDR imports WSC into cloned RPF: PASS for core subset via MagicRDR batch import.
- LEVEL 4 Exported-back file reopens in both Magic RDR and Code RED: PASS for core subset exported through Code RED after MagicRDR import/save.
- LEVEL 5 game boots with cloned RPF: NOT TESTED in this pass.
- LEVEL 6 game reaches script launch path: NOT TESTED in this pass.

## Core Subset

Standalone Magic RDR parser passed for:

- `freemode/freemode.wsc`
- `multiplayer_update_thread.wsc`
- `multiplayer_system_thread.wsc`
- `pr_multiplayer.wsc`

MagicRDR batch import was tested on a cloned Pass 5 RPF for the same core files. MagicRDR has no headless export command in its decompiled `Program.Main`; exported-back payloads were extracted from the MagicRDR-saved clone with Code RED and then reopened in both parsers.

## Outputs

- Fixed full converted set: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe\xsc_lzx_pc_wsc_magicrdr_fixed_all`
- Fixed mirrored import tree: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe\import_ready_xsc_magicrdr_fixed_wsc`
- Standalone Magic RDR report: `magicrdr_standalone\magicrdr_wsc_compat_report.csv`
- Import/export readback report: `magicrdr_import_export_readback.csv`
- Header comparison: `known_good_vs_converted_header_compare.csv`

## Remaining Caveat

Magic RDR parser compatibility is now proven. Runtime/game compatibility is still not proven. The fixed files should not be called gameplay-ready until a cloned RPF boots and reaches the script launch path.
