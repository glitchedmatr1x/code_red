# SP FreeMode Sector Graft Pass 1 - Build Report

Status: reconstructed base built; A0 and A1 built; A2-A5 blocked for safety.

- source RPF: `D:\Games\Red Dead Redemption\Code_RED\build\mp_content_restore_pass5\content_mp_restore_pass5_access_trainer_sectors.rpf`
- source SHA1: `F1D9391F4EE5CC32634B8625F32F63302F92ABB4`
- reconstructed base: `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass1\reconstructed_A_disable_update_thread_refs_from_F1D9391F4EE5CC32634B8625F32F63302F92ABB4.rpf`
- reconstructed SHA1: `C637CE34DA8CD34F96F83F879AD60B8B0535D6B2`

## Reconstructed A_disable_update_thread_refs

Applied only same-size decoded string reroutes for multiplayer_update_thread references:

- `$/content/multiplayer/multiplayer_update_thread` -> `$/content/multiplayer/codered_disabled_thread__`
- `multiplayer/multiplayer_update_thread` -> `multiplayer/codered_disabled_thread__`

No calls were added to net.EnterOnline, TriggerMultiplayerLoad, freemode, PR_Multiplayer, or multiplayer_update_thread.
No save prompt, auth, XML, EXE, ASI, or trainer files were changed.

## Built Variants

| Variant | Status | Output | SHA1 |
|---|---|---|---|
| `reconstructed_base` | `built` | `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass1\reconstructed_A_disable_update_thread_refs_from_F1D9391F4EE5CC32634B8625F32F63302F92ABB4.rpf` | `C637CE34DA8CD34F96F83F879AD60B8B0535D6B2` |
| `A0_repack_control` | `built` | `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass1\A0_repack_control.rpf` | `DB4119CD22CCFDB89E51A3A3496EE0D26D5593F2` |
| `A1_sp_wsc_noop_probe` | `built` | `D:\Games\Red Dead Redemption\Code_RED\build\sp_freemode_sector_graft_pass1\A1_sp_wsc_noop_probe.rpf` | `4E6669BBE571A35D5E5CA3B86BD5022EEAC41EC8` |
| `A2_one_mp_sector_only` | `blocked_no_rpf_built` | `` | `` |
| `A3_one_mp_sector_plus_sp_counterpart_unload` | `blocked_no_rpf_built` | `` | `` |
| `A4_small_region_sector_set` | `blocked_no_rpf_built` | `` | `` |
| `A5_gap_mine_lid_test` | `blocked_no_rpf_built` | `` | `` |

## Sector Variants

A2, A3, A4, and A5 were not built because this pass does not yet have a validated WSC authoring path for adding sector native calls.
Changing sector name strings alone would be a fake patch: it would not call ENABLE_CHILD_SECTOR or ENABLE_WORLD_SECTOR.

## Validation Outputs

- `reconstructed_base_changed_offsets.csv`
- `wsc_edit_validation.csv`
- `rpf_readback_validation.csv`
- `sector_test_variants.csv`
- `magicrdr_wsc_open/`

MagicRDR summary: `{"command": "C:\\Users\\glitc\\AppData\\Local\\Programs\\Python\\Python312\\python.exe D:\\Games\\Red Dead Redemption\\Code_RED\\tools\\codered_magicrdr_wsc_compat.py --source D:\\Games\\Red Dead Redemption\\Code_RED\\build\\sp_freemode_sector_graft_pass1\\magicrdr_validation_inputs --out D:\\Games\\Red Dead Redemption\\Code_RED\\reports\\sp_freemode_sector_graft_pass1\\magicrdr_wsc_open --title SP FreeMode Sector Graft Pass 1 MagicRDR WSC Open", "returncode": 0, "stderr": "", "stdout": "{\n  \"tested\": 5,\n  \"passed\": 5,\n  \"failed\": 0,\n  \"out\": \"D:\\\\Games\\\\Red Dead Redemption\\\\Code_RED\\\\reports\\\\sp_freemode_sector_graft_pass1\\\\magicrdr_wsc_open\"\n}"}`
