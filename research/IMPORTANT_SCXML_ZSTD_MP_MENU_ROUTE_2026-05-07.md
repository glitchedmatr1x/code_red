# IMPORTANT: SCXML Zstandard MP Menu Route

Date: 2026-05-07

## Decoder Result

- Tool: `tools\codered_scxml_zstd_probe.py`
- Source: `logs\content_mp_ui_gate_target_pack\targets`
- Output: `logs\content_mp_scxml_zstd_probe`
- Decoded output folder: `logs\content_mp_scxml_zstd_probe\decoded`
- Result: 36 Zstandard-packed SCXML files decoded as XML-like text.
- Failed Zstandard decodes: 0

The packed UI files use the Zstandard frame magic `28 b5 2f fd`. This confirms the useful route is Zstandard decode/export first, not XOR patching.

## High-Value MP Route Findings

### `root_content_ui_pausemenu_networking.sc.xml.decoded.xml`

- `NetTab_Private` routes to `NetConf_PlayPrivate` and calls `NetMachine.Authenticate('Online Multiplayer')`.
- `NetTab_LAN` targets `NetConf_PlayLAN`.
- `NetConf_PlayPrivate` includes `net/PlayMpConf.sc` with args `NetConf_PlayPrivate,'Online Multiplayer','Private'`.
- `NetConf_PlayLAN` includes `net/PlayMpConf.sc` with args `NetConf_PlayLAN,'LAN Multiplayer','LAN'`.
- `NetConf_PlayLAN` has an `auth.fail_NotSignedIn` transition that exits the LAN confirmation and calls `NetAlert_NotSignedInSysLink`.

### `root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml`

- The confirmation action calls `NetMachine.TriggerMultiplayerLoad(arg2)`.
- For LAN, `arg2` resolves from the include above to `LAN`.
- This is the clean UI-side handoff into the MP load path.

### `root_content_ui_pausemenu_net_offlinemenu.sc.xml.decoded.xml`

- `NetContent_LAN` is present and displays `mp_fe_play_lan` / `mp_fe_play_lan_detail`.
- The offline menu still calls `NetMachine.Authenticate('Online Multiplayer')`.
- `auth.fail_NotOnline` routes to `NetMachine.ShowSignInUI(true)`.

### `root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml`

- `Net_LANMenu` exists.
- The public/private buttons call `NetMachine.Authenticate('Online Multiplayer')`.
- No direct LAN load action was found here; the confirmed LAN load route is through `Networking.sc.xml` -> `NetConf_PlayLAN` -> `PlayMpConf.sc`.

## Patch Planning Notes

- Keep `.csc` / `.sco` script binaries out of the UI patch lane.
- Patch candidates should be copied archives or patch-layer files, not destructive edits to source archives.
- For the next UI test, the likely gates are:
  - `NetMachine.Authenticate('Online Multiplayer')`
  - `auth.fail_NotSignedIn`
  - `auth.fail_NotOnline`
  - `NetAlert_NotSignedInSysLink`
  - `NetMachine.ShowSignInUI(true)`
- The actual MP launch call to preserve is `NetMachine.TriggerMultiplayerLoad(arg2)`.

## Native Bridge Follow-Up

- `tools\codered_native_bridge_generation.py` now supports SDK-only fallback when `data\codered\native_database.json` is missing.
- It also reuses the existing generated native bridge manifest as a metadata fallback, so local regeneration keeps known Code RED categories and DB line notes.
- It parsed 3492 ScriptHookRDR SDK native entries.
- `ai_trainer_core` now emits 26 ready wrappers and 0 partial entries.
- The selected bridge prep was copied to:
  - `related_apps\Code_RED_ScriptHookRDR_AI_Menu\native_bridge\native_bridge_manifest.json`
  - `related_apps\Code_RED_ScriptHookRDR_AI_Menu\native_bridge\native_bridge_manifest.csv`
  - `related_apps\Code_RED_ScriptHookRDR_AI_Menu\native_bridge\native_bridge_selected_wrappers.cpp`
  - `related_apps\Code_RED_ScriptHookRDR_AI_Menu\native_bridge\native_bridge_compile_probe.cpp`

These are prep files only. They do not auto-patch the ASI or enable new unsafe behavior by themselves.
