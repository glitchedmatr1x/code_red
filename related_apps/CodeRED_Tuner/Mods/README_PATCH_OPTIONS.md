# Code RED Tuner Patch Options

This folder is now treated as the tuner-side patch option library.

- Each direct child folder is one selectable mod pack.
- The Tuner `Patch Options` tab keeps selected packs separated in `02_mod_packs` and also builds a combined loose tree at `03_merged_loose_patch`.
- Conflicts are not overwritten; conflicting files are copied with a `.conflict_from_<pack>` suffix so the package stays reviewable.
- Apply everything to copied archives first.

Current first-class options:

1. `Game - Driveable vehicles +` — driveable vehicle support files for Car01/Truck01/rafts/canoe.
2. `Game - Train Spawns Cars` — train gringo/common-script test pack plus locset payload for spawning car behavior near train activity.

The multiplayer client bridge is not stored here. The Tuner export writes that into `04_multiplayer_client` when enabled.
