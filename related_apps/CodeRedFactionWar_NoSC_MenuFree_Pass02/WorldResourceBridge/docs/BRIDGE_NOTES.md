# WorldResourceBridge Notes

This folder is the no-EXE/no-SC-CL lane for continuing Faction War.

It converts v26's hardcoded seed data into readable resource-side files that match the coding styles found in `tune_d11generic.rpf`:

- `.tr` AI rule-script style
- `.pop` population profile style
- `.traffic` route/traffic profile style
- JSON patch recipe for Code RED's future RPF merge workflow

These files are not meant to be blindly dropped into the game. They are merge targets for the next Code RED archive-editing pass after Zstandard decode/rebuild is wired into the workbench.


## Pass 02

The bridge is now functional enough for Code RED merge testing.

Important corrections from the archive research:

- Many `tune_d11generic.rpf` entries are Zstandard-compressed text resources.
- `.tr` AI files use a C-like rule language with includes, `program` blocks, `rules` blocks, custom predicates, and existing stock actions.
- The Faction War bridge should **not** call imaginary functions such as `FactionPressure(...)` inside TR logic.
- The generated TR now derives Code RED predicates from recovered stock conditions like `WantToHurt`, `UnknownWeaponFired`, `RecentExplosion`, `Ally`, and `ScreamedRecently`.
- The `.pop` and `.traffic` outputs are merge blocks, not blind replacement files.

Recommended test order:

1. Use the merge preview diff against `root/tune/ai/game_main.tr` first. It is small and clean.
2. Add the loose `code_red_factionwar_world.tr` beside the target AI file.
3. Rebuild/recompress the target entry using the same compression type the original entry used.
4. Reopen the archive in Code RED and verify the patched include plus the new TR file.
5. Only after that, test content-side AI.
6. Leave population and traffic as merge-only until Code RED has a proper DSL merge editor.
