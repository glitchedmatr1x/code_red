# MP Script CSC/XSC -> WSC Conversion Probe

No RPFs or live game files were modified.

- Build output: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe`
- Focused core-script mode: `False`

## Status Counts

- `rsc86_conversion_blocked`: `45`
- `wrapper_converted_decode_blocked`: `56`

## Result

- Decode-ready WSC conversions: `0`
- XSC byte-swapped WSC wrapper candidates that still failed payload decode: `56`

The current practical path is still source/authoring via SC-CL for new WSCs. Donor XENON .xsc files can be converted to a PC-looking RSC85/WSC wrapper by 32-bit word-swap, but the payload did not become Code RED-decodable with the available PC AES/Zstd/zlib lanes. PSN .csc files are RSC86 and are not converted to WSC by this pass.

## Next Technical Blockers

- Identify the correct XENON script payload key/transform if it differs from the PC RDR AES key.
- Build or obtain a callable XCompress/LZX bridge for the local toolchain, then validate payload decode/repack.
- If source/pseudocode is available, compile with SC-CL `-target=RDR_SCO` and wrap into PC RSC85 WSC using the existing Code RED authoring lane.

## Core Outputs

- `xenon_xsc` `ctf/ctf_base_game.xsc` -> `wrapper_converted_decode_blocked` output=`ctf/ctf_base_game.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `deathmatch/deathmatch.xsc` -> `wrapper_converted_decode_blocked` output=`deathmatch/deathmatch.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `freemode/freemode.xsc` -> `wrapper_converted_decode_blocked` output=`freemode/freemode.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `mp_idle.xsc` -> `wrapper_converted_decode_blocked` output=`mp_idle.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `multiplayer_system_thread.xsc` -> `wrapper_converted_decode_blocked` output=`multiplayer_system_thread.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `multiplayer_update_thread.xsc` -> `wrapper_converted_decode_blocked` output=`multiplayer_update_thread.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `pr_multiplayer.xsc` -> `wrapper_converted_decode_blocked` output=`pr_multiplayer.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `rotations/gametype_lobby.xsc` -> `wrapper_converted_decode_blocked` output=`rotations/gametype_lobby.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `xenon_xsc` `support/mp_actorpicker.xsc` -> `wrapper_converted_decode_blocked` output=`support/mp_actorpicker.wsc` error=`AES decrypt was attempted, but the payload did not match the implemented Zstandard/zlib lanes or the simple Xbox LZX wrapper probe.`
- `psn_csc` `ctf/ctf_base_game.csc` -> `rsc86_conversion_blocked` output=`ctf/ctf_base_game.rsc86.review` error=`PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.`
- `psn_csc` `deathmatch/deathmatch.csc` -> `rsc86_conversion_blocked` output=`deathmatch/deathmatch.rsc86.review` error=`PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.`
- `psn_csc` `freemode/freemode.csc` -> `rsc86_conversion_blocked` output=`freemode/freemode.rsc86.review` error=`PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.`
- `psn_csc` `mp_idle.csc` -> `rsc86_conversion_blocked` output=`mp_idle.rsc86.review` error=`PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.`
- `psn_csc` `multiplayer_system_thread.csc` -> `rsc86_conversion_blocked` output=`multiplayer_system_thread.rsc86.review` error=`PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.`
- `psn_csc` `multiplayer_update_thread.csc` -> `rsc86_conversion_blocked` output=`multiplayer_update_thread.rsc86.review` error=`PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.`
- `psn_csc` `pr_multiplayer.csc` -> `rsc86_conversion_blocked` output=`pr_multiplayer.rsc86.review` error=`PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.`
