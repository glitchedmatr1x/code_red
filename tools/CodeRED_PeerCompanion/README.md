# CodeRED Peer Companion Spawn Near Player Fix

Use this when F8 seems close but the game crashes or no actor is visible.

- `source_patch/` contains the patched C++ source and diff.
- `dropin_config_safe/` uses actor enum 111.
- `dropin_config_alt_enum_369/` uses actor enum 369, which earlier smoke logs showed could create a valid actor.
- `codex_task/` is the exact instruction file for Codex.
