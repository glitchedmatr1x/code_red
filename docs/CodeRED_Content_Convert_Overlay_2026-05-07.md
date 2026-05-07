# Code RED Content Convert Overlay - 2026-05-07

## Purpose

Compare `build/content convert.zip` against the current copied MP-injected `content.rpf` line and build safe test archives for multiplayer restoration/bypass experiments.

The zip is treated as reference material from a different content format/version. The builder never installs to the game folder. It writes copied test archives under `build/`.

## Tool

`tools/codered_content_convert_overlay_builder.py`

The tool:

- reads `build/content convert.zip`
- starts from `build/content_mp_lan_fallback_test/content.rpf`
- appends selected replacement payloads at EOF
- rebuilds the RPF6 TOC
- keeps resource entries untouched unless a profile explicitly opts into full WSC/RSC85 replacement
- Zstandard-compresses UI XML/SCXML entries before insertion
- resolves hashed UI aliases by same-name hash so duplicate menu entries are not created

## Content Convert Findings

Useful multiplayer-related material in the zip:

- `content/release/multiplayer/**`
- `content/ui/pausemenu/networking.sc.xml`
- `content/ui/pausemenu/net/lanmenu.sc.xml`
- `content/ui/pausemenu/net/0x118473D0.xml`, same hash as `offlinemenu.sc.xml`
- `content/ui/pausemenu/net/0x1374443B.xml`, same hash as `plaympconf.sc.xml`
- `content/release/scripting/DesignerDefined/socialclub/**`

Important naming detail: the live/content RPF parser resolves `0x118473D0` to `offlinemenu.sc.xml` and `0x1374443B` to `plaympconf.sc.xml`. The builder now skips or replaces those same-hash entries instead of adding duplicates.

## Test Archives

1. LAN fallback bypass candidate:
   `D:\Games\Red Dead Redemption\Code_RED\build\content_mp_lan_fallback_test\content.rpf`

2. LAN fallback plus content-convert Social Club support scripts:
   `D:\Games\Red Dead Redemption\Code_RED\build\content_convert_variants\support_aliases\content.rpf`

3. Content-convert UI overlay plus Social Club support scripts:
   `D:\Games\Red Dead Redemption\Code_RED\build\content_convert_variants\convert_ui\content.rpf`

4. LAN-menu-only overlay plus Social Club support scripts:
   `D:\Games\Red Dead Redemption\Code_RED\build\content_convert_variants\lanmenu_only\content.rpf`

5. Offline/play-confirm-only overlay plus Social Club support scripts:
   `D:\Games\Red Dead Redemption\Code_RED\build\content_convert_variants\mp_confirm_only\content.rpf`

## Verification

Report:

`logs/content_convert_overlay/variant_verification_report.json`

All three archives verified:

- RPF parses
- no duplicate archive paths
- `mp_csc_count` remains `90`
- `freemode.csc` exists in `release` and `release64`
- `mp_idle.csc` exists in `release` and `release64`
- probed UI XML entries are Zstandard payloads and decode as XML-like text

After runtime feedback, `convert_ui` is marked as crash-prone because it crashed at the start screen. Keep it as a comparison sample only. The narrower `lanmenu_only` and `mp_confirm_only` archives were added to isolate whether the crash is caused by broad `networking.sc.xml` replacement or by the same-hash route files.

Current KML active test archive:

`D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\rpf\content.rpf`

Active profile:

`mp_confirm_only`

The previous active KML `content.rpf` was backed up before replacement under:

`D:\Games\Red Dead Redemption\RDR-SteamGG.NET\CodeRED_Backups\`

## ASI MP Access Menu

`CodeRED_AI_Menu.asi` now has a controlled MP access lane in the F8 menu. It restores the native bridge source path and adds actions from `data/codered/ai_behavior_actions.csv`:

- `MP Probe / Script Availability`
- `MP Enable Multiplayer Native`
- `MP Open Networking UI Probe`
- `MP Start Core Threads`
- `MP Launch Freemode`
- `MP Launch Deathmatch`
- `MP Launch CTF`

The launch actions call `DOES_SCRIPT_EXIST` first and log every path probe before attempting `LAUNCH_NEW_SCRIPT` / `START_NEW_SCRIPT`. This is intentionally diagnostic: it should tell us which script path form the PC runtime accepts before we hardwire a more aggressive route.

## Suggested Test Order

1. Test the active KML `mp_confirm_only` archive first.
2. If it crashes before the menu, swap to `lanmenu_only`.
3. If both boot but do not change behavior, use F8 and test MP actions in this order: status probe, enable multiplayer, start core threads, launch freemode.
4. Keep `convert_ui` out of the active `kml\rpf` folder unless we specifically need to reproduce the start-screen crash.

For each test, record:

- whether the game boots
- whether the pause menu still opens
- whether LAN/System Link appears or behaves differently
- whether it reaches the MP loading transition
- the first new failure line in the game log

Do not overwrite `D:\Games\Red Dead Redemption\game\content.rpf` without making a separate backup first.

## RDR2 Init WSC Pass

Runtime feedback corrected the init assumption: this PC path appears to read the `release64/init/*.wsc` resource scripts for init, not the added `.csc` probes. The earlier CSC/SCO init variants remain comparison material, but they are not the main route for `rdr2init`.

WSC donor scan:

- `build/content convert.zip` has no `.wsc` init donors.
- `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\rdr2init.wsc` is byte-identical to the extracted stock `release64/init/rdr2init.wsc`.
- Current useful stock WSC references are under `logs/content_rpf_full_extract_after_magic_names/content/release64/init/`.
- A tiny SC-CL RDR `#SC` probe was compiled, byte-swapped into WSC/RSC85 form, and staged at `logs/sccl_wsc_probe/codered_launch_freemode_probe.wsc`.

The overlay builder now supports explicit local-file WSC replacement only when `allow_resource_replace` is set and the payload starts with `RSC85`. It preserves the resource type in the RPF TOC, copies WSC resource flag words from the replacement header, and appends WSC resource replacements on a 2048-byte boundary so the RPF resource offset points at the actual payload.

WSC test archives in the KML folder:

1. Behavior-neutral WSC resource replacement proof:
   `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\content_init_variants\init_wsc_stock_refresh\content.rpf`

2. Active-source WSC hook replacing `initpopulation.wsc`:
   `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\content_init_variants\init_wsc_launch_freemode_population\content.rpf`

3. Active-source WSC hook replacing `rdr2init_each_load.wsc`:
   `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\content_init_variants\init_wsc_launch_freemode_each_load\content.rpf`

4. MP-injected source plus WSC hook replacing `initpopulation.wsc`:
   `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\content_init_variants_mp\init_wsc_launch_freemode_population\content.rpf`

5. MP-injected source plus WSC hook replacing `rdr2init_each_load.wsc`:
   `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\content_init_variants_mp\init_wsc_launch_freemode_each_load\content.rpf`

6. LAN-fallback MP source plus WSC hook replacing `initpopulation.wsc`:
   `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\content_init_variants_mp_lan\init_wsc_launch_freemode_population\content.rpf`

7. LAN-fallback MP source plus WSC hook replacing `rdr2init_each_load.wsc`:
   `D:\Games\Red Dead Redemption\RDR-SteamGG.NET\kml\content_init_variants_mp_lan\init_wsc_launch_freemode_each_load\content.rpf`

Verification report:

`logs/content_convert_overlay/init_wsc_variant_verification_report.json`

Suggested WSC test order:

1. `init_wsc_stock_refresh` first, only to prove the WSC replacement mechanics do not crash the loader.
2. `content_init_variants_mp/init_wsc_launch_freemode_population`, because it keeps core `rdr2init.wsc` and `rdr2init_each_load.wsc` intact while adding the MP script hook through a smaller init lane.
3. `content_init_variants_mp_lan/init_wsc_launch_freemode_population`, if LAN fallback UI behavior is still needed.
4. `content_init_variants_mp/init_wsc_launch_freemode_each_load`, only if the population hook does nothing.
5. `content_init_variants_mp_lan/init_wsc_launch_freemode_each_load`, last, because `rdr2init_each_load.wsc` is more central.

The WSC hook is intentionally experimental. It requests and launches:

- `content/release64/multiplayer/mp_idle`
- `content/release64/multiplayer/multiplayer_system_thread`
- `content/release64/multiplayer/multiplayer_update_thread`
- `content/release64/multiplayer/freemode/freemode`

If these paths do not resolve at runtime, the next pass should keep the WSC resource replacement machinery but adjust the script path strings or move the launch logic back into the ASI where runtime logging is stronger.
