# Remote Menu Crash Response

Generated: 2026-05-23T23:11:53

User reported Soul Stealer crashed and the menu brought a cursor/interfered with gameplay. The ASI was changed to safe mode:

- `overlay_enabled=false`: F7/Insert no longer opens or draws the overlay; it logs a blocked toggle.
- `actor_scan_enabled=false`: F8 no longer arms Soul Stealer; E cannot scan actors.
- `teleport_write_enabled=false`: F6 cannot teleport/write position; F5 can only read/log a slot.
- `log_interval_ms=10000`: ghost stub logging is slowed.
- captured actor polling is no longer automatic.

Installed ASI SHA1: `C17B123B01997886E662CFA1A5C2ABD57C4D9BF2`

Do not re-enable actor scan or teleport write until the native signatures and runtime timing are isolated in a read-only test build.
