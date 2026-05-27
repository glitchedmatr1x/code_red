# Code RED Runtime Probe

Manual-only ScriptHookRDR ASI for testing live runtime state, UI event dispatch, and TES sector enable/disable calls after single-player has loaded.

This pass does not edit `content.rpf`, `RDR.exe`, WSC, XML, trainer files, or ASI loader files.

## Build

From the Code_RED repo root:

```bat
related_apps\Code_RED_Runtime_Probe\build_bridge.bat
```

Output:

```text
related_apps\Code_RED_Runtime_Probe\build\CodeRED_Runtime_Probe.asi
```

## Install

Copy beside `RDR.exe`:

```text
CodeRED_Runtime_Probe.asi
```

Copy config to:

```text
data\codered\runtime_probe.ini
```

Runtime log:

```text
data\codered\runtime_probe.log
```

## Hotkeys

- F6: write state snapshot to log.
- F7: send harmless UI event only when `enable_ui_events=true`; otherwise logs skipped.
- F8: enable `mp_tes_coop01ax`.
- F9: disable `mp_tes_coop01ax`.
- F10: enable TES group.
- F11: disable TES group.
- F12: write help to log, or draw a small help overlay if `draw_overlay=true`.

## Safety

The ASI does not auto-run sector changes, UI events, MP events, script launches, or save bypasses at startup. All runtime actions are hotkey/manual only and pass through config gates.
