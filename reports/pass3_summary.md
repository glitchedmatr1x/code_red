# Code RED Soul Stealer Reconstruction Pass 3 Summary

Pass 3 turns the Pass 2 logic module into a runtime-ready trainer component.

## Added

- `SoulStealerRuntime`: owns the module, hotkey polling, debug dump, reload request, logging, and tick loop.
- `HotkeyController`: isolated input edge-detection interface.
- `IInputBridge`: lets Codex wire Win32/ASI input without touching Soul Stealer logic.
- `RuntimeLogger`: in-memory + optional file logging.
- `DebugOverlay`: status message wrapper for HUD/subtitle integration.
- `MockInputBridge`: deterministic hotkey tests.
- `CodeRED_ASI_Runtime_TODO.cpp`: Codex-ready integration sketch.
- `CodeREDLinkGhostProtocol.md`: future pseudo-coop ghost/pupet data format.

## Validation

Both mock executables compiled and passed:

- `soul_stealer_mock_test`
- `soul_stealer_runtime_test`

The actual Windows `.asi` still needs the local Code RED ScriptHook/native bridge.
