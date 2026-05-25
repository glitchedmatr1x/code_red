# Codex Handoff — Soul Stealer Pass 3

Use this package as the source baseline. Do not restart from the old PS3 CSC trainer.

## Task

Wire the Pass 3 C++ module into the local Code RED ASI / ScriptHook RDR project.

## Main files

- `source/NativeBridge.h`
- `source/SoulStealerRuntime.h/.cpp`
- `source/SoulStealerModule.h/.cpp`
- `integration/CodeRED_ASI_Runtime_TODO.cpp`
- `integration/CodeRED_ASI_Integration_TODO.cpp`

## First integration objective

Compile with a real `RdrNativeBridge` that implements only enough methods for `ProbeOnly`:

- player actor handle,
- actor validity/alive,
- position/heading/model,
- all actors or nearest actor iterator,
- HUD/log messages.

Then add fallback possession primitives.

## Rules

- Do not port or run the old cracked PS3 trainer.
- Do not patch live content.rpf.
- Do not use online/MP mode.
- Keep emergency cancel.
- Keep logs in `Code_RED/logs/soul_stealer.log`.
