# SP FreeMode Sector Graft Pass 2 - TES Sector Graft

- base: `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass1\reconstructed_A_disable_update_thread_refs_from_F1D9391F4EE5CC32634B8625F32F63302F92ABB4.rpf`
- base SHA1: `C637CE34DA8CD34F96F83F879AD60B8B0535D6B2`
- multiplayer activation: `not used`
- patch method: existing SP sector-native PushString slot replacement only

## Built Variants

| Variant | Status | Output | SHA1 | Notes |
|---|---|---|---|---|
| `A0_pass2_repack_control` | `built` | `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass2\A0_pass2_repack_control.rpf` | `07DC7DC10EAAEF121EFA75C3A274CDA8E43B771E` | Base resource replacement/readback control; no decoded change. |
| `A1_pass2_callsite_noop_control` | `built` | `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass2\A1_pass2_callsite_noop_control.rpf` | `07DC7DC10EAAEF121EFA75C3A274CDA8E43B771E` | No-op repack through selected callsite lane: MAIN_ENABLE_CHILD_RWF_BARN_PROPS01. |
| `A2_tes_single_sector` | `built` | `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass2\A2_tes_single_sector.rpf` | `22D140491496060458CA4561DDBC4A471CA43CAA` | Replaces rwf_barn01xprops01x slot with mp_tes_coop01ax. |
| `A3_tes_single_sector_with_sp_counterpart_unload` | `skipped` | `` | `` | Skipped: sector_overlap_map has no clear TES SP counterpart to disable safely. |
| `A4_tes_small_set` | `built` | `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass2\A4_tes_small_set.rpf` | `47AC72ECBAB54274672449BD0455F6AD88B119BD` | Replaces four SP child-sector slots with TES coop sector names. |

## Decision

A2 uses one existing SP ENABLE_CHILD_SECTOR-labeled callsite and changes only its string operand to `mp_tes_coop01ax`.
A3 is skipped because the sector overlap map did not identify a clear TES SP counterpart to unload.
A4 uses four existing SP ENABLE_CHILD_SECTOR-labeled callsites, one per requested TES test sector.

## Validation

- MagicRDR WSC open: `{"command": "C:\\Users\\glitc\\AppData\\Local\\Programs\\Python\\Python312\\python.exe D:\\Games\\Red Dead Redemption\\Code_RED\\tools\\codered_magicrdr_wsc_compat.py --source D:\\Games\\Red Dead Redemption\\Code_RED\\build\\sp_freemode_sector_graft_pass2\\magicrdr_validation_inputs --out D:\\Games\\Red Dead Redemption\\Code_RED\\reports\\sp_freemode_sector_graft_pass2\\magicrdr_wsc_open --title SP FreeMode Sector Graft Pass 2 MagicRDR WSC Open", "returncode": 0, "stderr": "", "stdout": "{\n  \"tested\": 4,\n  \"passed\": 4,\n  \"failed\": 0,\n  \"out\": \"D:\\\\Games\\\\Red Dead Redemption\\\\Code_RED\\\\reports\\\\sp_freemode_sector_graft_pass2\\\\magicrdr_wsc_open\"\n}"}`
- RPF reparsed for every built clone.
- Changed WSC payloads were read back and SHA1-compared exactly.
- Code RED WSC reopen passed for changed WSCs.
