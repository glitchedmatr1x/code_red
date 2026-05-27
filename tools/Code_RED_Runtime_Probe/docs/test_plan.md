# Code RED Runtime Probe Test Plan

## Baseline

Start with no other experimental ASIs enabled. Do not combine this with Soul Stealer, MP bootstrap, avatar picker, or RPF patch experiments during the first probe test.

## Hotkey Tests

| Key | Expected behavior |
|---|---|
| F6 | Logs player actor, coords, heading, world-loaded status, and unavailable fields for unmapped systems. |
| F7 | Logs skipped while `enable_ui_events=false`. If enabled, sends only `CodeRED_RuntimeProbe_Test`. |
| F8 | Enables `mp_tes_coop01ax` through `ENABLE_CHILD_SECTOR`. |
| F9 | Disables `mp_tes_coop01ax` through `DISABLE_CHILD_SECTOR`. |
| F10 | Enables `mp_tes_coop01ax`, `mp_tes_coop01bx`, `mp_tes_coop01cx`, `mp_tes_coop02x`. |
| F11 | Disables the same TES group. |
| F12 | Logs help. If `draw_overlay=true`, shows a small text-only help overlay. |

## Success Criteria

- Game reaches single-player with the ASI installed.
- `data\codered\runtime_probe.log` is created.
- F6 writes a state snapshot without crashing.
- F8/F9 log before/after sector actions.
- No MP launch, no freemode launch, no save bypass.
