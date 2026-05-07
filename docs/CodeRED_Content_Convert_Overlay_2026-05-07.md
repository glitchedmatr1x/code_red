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
- keeps resource entries untouched
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
