# CodeRED RDR MP LAN RPF Status - 2026-05-26

## Active restored state

The installed last-working `content.rpf` is:

- `build/content_mpconv_lan_startonline/content.rpf`
- SHA-256: `9623388d24e0a941d0e7eee5ef5a3f3f99a6d9a18bc58e52d5e183d5e407d30a`

This state is installed in both the working game folder and the Wine prefix:

- `Red Dead Redemption/game/content.rpf`
- `Red Dead Redemption/override/content.rpf`
- `/home/chairman/Games/red-dead-redemption/drive_c/Program Files/Rockstar Games/Red Dead Redemption/game/content.rpf`
- `/home/chairman/Games/red-dead-redemption/drive_c/Program Files/Rockstar Games/Red Dead Redemption/override/content.rpf`

Observed behavior:

- The in-game pause menu reaches the multiplayer profile/menu surface.
- `ONLINE PRIVATE` no longer stops at the earlier network alert.
- The actual world bootstrap is still incomplete: the player remains in a single-player world context, without MP spawn/teleport/world setup.

## RPF variants tested

| Variant | SHA-256 | Result |
| --- | --- | --- |
| `content_mpconv_auth_restore` | `c44f450e7174ae93f1909d5c30696272f1697b7faaddf67970d7a55cba941df8` | Restored stock authentication path; LAN still ends in the network alert. |
| `content_mpconv_lan_fail_bypass` | `1bac3f6f2b8e14c114fc254e6fc7cd30a4b616d34e8db5b4d4b449524e4713b2` | Direct `TriggerMultiplayerLoad('LAN')`; crashes with `BREAKPOINT`. |
| `content_mpconv_lan_startonline` | `9623388d24e0a941d0e7eee5ef5a3f3f99a6d9a18bc58e52d5e183d5e407d30a` | Current last-working state; MP menu/profile reachable, world still SP. |
| `content_mpconv_lan_twophase` | `7d7fa96cca42500c3b7ce30d6557cef63b56f64bee7be6412866f84555a1adda` | `StartOnline`, delayed trigger/load; crashes with `ACCESS_VIOLATION` in title storage boot. |
| `content_mpconv_lan_startonline_loadstart` | `c4ed9f8ff1f0acd392955e11fde59f1507a9745af0abbcc14ec83914b880dd35` | `StartOnline`, delayed `loadStart`; crashes with `ACCESS_VIOLATION` in title storage boot. |
| `content_mpconv_lan_loadstart_tms_sco_stub` | `aa08f2621c2b0e8e2a0ba437d45f96a3833d4aab5c05b852370bb6049f4cac44` | Tiny `tms_boot_360.sco`/`tms_run_360.sco` stubs; immediate main-menu `BREAKPOINT`. Negative test. |
| `content_mpconv_lan_bootflow` | `dfb4393d9e1ba49d4c04e80d31172c4e4e90163dd06210d55263f2605b31c972` | Calls a fuller boot flow before load; crashes with `ACCESS_VIOLATION` in `tms_boot_360.sco`. |
| `content_mpconv_lan_bootflow_tms_run_as_boot` | `0e7b02d408d13e1203e18987c34e2daa2f0ea763a456a35de557d005dbd4418c` | Bootflow plus original-format `tms_run_360.sco` copied to `tms_boot_360.sco`; not kept as active state. |

## Current read

The RPF wiring is now far enough to expose MP UI/profile paths, but not enough to build the MP world. The remaining blocker appears to be the session/world bootstrap after `net.StartOnline`, especially the title-storage/boot path around:

- `content/release64/dlc/titlestorage/tms_boot_360.sco`
- `content/release64/dlc/titlestorage/tms_run_360.sco`
- `content/ui/pausemenu/networking.sc.xml`
- the original `boot.sc.xml` `net.EnterOnline` and `Startup_Checks` flow

`ScriptHook` and ASI injection were not treated as root cause; the same class of MP crash was observed independently of those being present.

## Next likely step

Keep `content_mpconv_lan_startonline` as the baseline. The next useful experiment is to reproduce the missing part of stock `net.EnterOnline`/`Startup_Checks` without replacing title-storage SCOs with invalid or mismatched stubs. In practice that means:

1. Compare the exact event sequence from stock `boot.sc.xml`, `taskmachine.sc.xml`, and `networking.sc.xml`.
2. Instrument or minimally patch only the transition from `net.StartOnline` to the MP world setup.
3. Treat direct `loadStart` and replacement `tms_boot_360.sco` as high-risk paths because they already crash before the world setup completes.
