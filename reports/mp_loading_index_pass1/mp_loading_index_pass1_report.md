# MP Loading Index Pass 1

Scope: index the current multiplayer experiment archive, the new XENON MULTIPLAYER/mp pass folder, and the MagicRDR-fixed converted WSC tree. No live RPF edits were made in this pass.

## Inputs
- Current live test RPF: `D:\Games\Red Dead Redemption\game\content.rpf`
  - SHA1: `970BFC26D438CBBDB453BC82ADB0F6AC89DA789F`
- Backup zip: `D:\Games\Red Dead Redemption\game\content zombie mp loading.zip`
  - SHA1: `386ACC8CE9DDD9CCEBF941657F13A6129BA52707`
- New pass folder: `D:\Games\Red Dead Redemption\game\XENON MULTIPLAYER\mp pass`
- MagicRDR-fixed converted tree: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe\import_ready_xsc_magicrdr_fixed_wsc`

## Inventory Results
- mp pass WSC files: `45`
- mp pass SCO files: `5`
- mp pass XML/SCXML files: `24`
- mp pass ZIP packages: `27`
- File inventory CSV: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_loading_index_pass1\mp_pass_file_inventory.csv`

## MagicRDR Compatibility
- Tested WSC files: `45`
- Passed: `45`
- Failed: `0`
- Report: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_loading_index_pass1\magicrdr_compat_mp_pass_wsc\magicrdr_wsc_compat_report.md`

## Current content.rpf Scan
- Entries indexed: `1715`
- Interesting MP/UI/script entries: `148`
- release64 multiplayer entries found by path: `44`
- Deep scan output: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_loading_index_pass1\current_content_deep_scan`
- Harness output: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_loading_index_pass1\current_content_harness`

## Core WSC Map Summary

| Script | Functions | Strings | Natives | Branch rows | Route term hits |
|---|---:|---:|---:|---:|---:|
| `multiplayer_update_thread` | 353 | 1065 | 901 | 2890 | 7 |
| `multiplayer_system_thread` | 483 | 1142 | 1336 | 4354 | 4 |
| `pr_multiplayer` | 225 | 747 | 644 | 1654 | 28 |
| `pressstart_D_full_force` | 7 | 119 | 184 | 54 | 3 |
| `main_mp_save_unblock` | 559 | 5993 | 3907 | 8734 | 3 |
| `main_z_mp_save_unblock` | 466 | 4224 | 4273 | 6300 | 1 |
| `sp_idle` | 298 | 1142 | 1877 | 3359 | 1 |
| `rdr2init` | 191 | 41331 | 6166 | 2312 | 7 |

## Freemode Index
- The top-level mp pass folder does not contain `freemode.wsc`; the editable MagicRDR-fixed copy is under the Code_RED conversion tree.
- release64 freemode scan hit count from CLI: 63 route/content terms.
- release64 freemode map result: 705 functions, 2,650 strings, 1,728 constants, 2,795 native candidates, 5,320 branch candidates, 1,424 string references.
- release64 freemode control-flow report: 8,820 candidates and 383 CONTROL_FLOW_SAFE rows from the current analyzer.

## Current RPF Core Readback Compare

| Logical file | Archive path | Entry | Status | Archive SHA1 | Source SHA1 |
|---|---|---:|---|---|---|
| `multiplayer_update_thread` | `root/content/release64/multiplayer/multiplayer_update_thread.wsc` | 753 | `exact_match` | `424A93A288848063591E93D1A0DDA1A0B8811C5C` | `424A93A288848063591E93D1A0DDA1A0B8811C5C` |
| `pr_multiplayer` | `root/content/release64/multiplayer/pr_multiplayer.wsc` | 759 | `exact_match` | `E92C01B3463C12455DD18018EF565D4E0B643122` | `E92C01B3463C12455DD18018EF565D4E0B643122` |
| `multiplayer_system_thread` | `root/content/release64/multiplayer/multiplayer_system_thread.wsc` | 761 | `exact_match` | `7749E850C76987746BB70EC818BB039B2C6D0143` | `7749E850C76987746BB70EC818BB039B2C6D0143` |
| `freemode_release64` | `root/content/release64/multiplayer/freemode/freemode.wsc` | 780 | `exact_match` | `F2A648E9CD922825E404B58574DF3215CCB69BB6` | `F2A648E9CD922825E404B58574DF3215CCB69BB6` |
| `pressstart` | `root/content/release64/pressstart.wsc` | 275 | `mismatch` | `EA357CFF0488E475060A905E8D56AEF68AB5ECBD` | `63FE7C191A85FA51E4A34CD2CF14CEA50A1975B2` |
| `main` | `root/content/release64/main.wsc` | 274 | `mismatch` | `CA956DCD9876AD257F9870D53DAA63780760148C` | `5A7255A1C3BC57061F84295EE25DBE2638359D1B` |

Important: the converted MP backend core files in the current RPF match the known `mp pass`/fixed sources exactly. `pressstart` and `main` do not match the loose copies, so the live RPF has a distinct patched/packed variant there and should be treated as its own baseline.

## Working Interpretation
- The WSC conversion/editability layer is not the immediate blocker: all 45 mp pass WSC files passed the MagicRDR parser.
- Do not reuse broad Pass 10 freemode string patches; that lane previously crashed even when patched freemode was only present.
- The next useful work is candidate-driven inspection of `PR_Multiplayer`, `multiplayer_system_thread`, `multiplayer_update_thread`, and clean `freemode.wsc`, then one-change variants only.
- Since zombie/MP route reaches loading and then stalls, likely blockers are runtime state/session flags, script launch timing, or missing/incorrect HUD/session frontend state rather than raw WSC readability.

## Suggested Next Build Step
Build a cloned RPF only, not live `content.rpf`, with these isolated variants:
1. current RPF repack/readback control.
2. current RPF plus clean MagicRDR-fixed freemode import only.
3. current RPF plus clean freemode + online HUD XML/HUDScene route only.
4. current RPF plus one WSC route candidate chosen from the new candidate maps.

Avoid direct `TriggerMultiplayerLoad`, direct `multiplayer_update_thread` startup, and broad freemode string replacement until a single candidate is proven safe.
