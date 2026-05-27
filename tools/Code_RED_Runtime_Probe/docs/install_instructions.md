# Code RED Runtime Probe Install Instructions

This probe is manual-only. It does not modify `content.rpf`, `RDR.exe`, WSC, XML, ASI loader files, or trainer files.

## Files

- ASI: `related_apps\Code_RED_Runtime_Probe\build\CodeRED_Runtime_Probe.asi`
- Config: `related_apps\Code_RED_Runtime_Probe\runtime_probe.ini`
- Runtime log path after install: `data\codered\runtime_probe.log`

## Install

Copy beside `RDR.exe`:

```text
CodeRED_Runtime_Probe.asi
```

Copy config to the game folder:

```text
data\codered\runtime_probe.ini
```

Recommended first test config keeps:

```ini
enable_ui_events=false
enable_sector_probe=true
enable_mp_events=false
enable_script_launch_probe=false
startup_delay_ms=15000
draw_overlay=false
```

## First Test Order

1. Launch single-player and wait until the world is loaded.
2. Wait at least 15 seconds after ASI attach.
3. Press `F6` and check `data\codered\runtime_probe.log`.
4. Press `F8` to enable `mp_tes_coop01ax`.
5. Press `F9` to disable `mp_tes_coop01ax`.
6. Press `F10`/`F11` only after F8/F9 do not crash.

`F7` is disabled by default because UI event dispatch is config-gated.
