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

## Suggested Test Order

1. Test `content_mp_lan_fallback_test` first. This is the smallest bypass archive and keeps the previously generated LAN fallback UI.
2. Test `support_aliases` second. This keeps the LAN fallback UI but adds missing content-convert Social Club support scripts.
3. Test `convert_ui` third. This is the more aggressive restoration candidate because it replaces `networking`, `lanmenu`, `offlinemenu`, and `plaympconf` UI entries with content-convert versions.

For each test, record:

- whether the game boots
- whether the pause menu still opens
- whether LAN/System Link appears or behaves differently
- whether it reaches the MP loading transition
- the first new failure line in the game log

Do not overwrite `D:\Games\Red Dead Redemption\game\content.rpf` without making a separate backup first.
