# IMPORTANT: Code RED Magic-RDR Parity Extraction

Generated: 2026-05-06

## Result

Code RED now uses the local Magic-RDR `ImportedFileNames.txt` resources for RPF6 hash-name recovery. This restores the main readable inventory parity path without requiring unsafe guesses at MagicRDR.exe command-line syntax.

## Validated Live Archive

Archive:

`D:\Games\Red Dead Redemption\game\content.rpf`

Inventory command:

```bat
py -3 tools\codered_rpf_utils.py inventory --archive "D:\Games\Red Dead Redemption\game\content.rpf" --out logs\content_rpf_inventory_after_magic_names
```

Result:

- Entries: 1636
- Files: 1320
- Dirs: 316
- Resolved names: 1636/1636
- Encrypted TOC: true

Full extraction command:

```bat
py -3 tools\codered_rpf_utils.py extract --archive "D:\Games\Red Dead Redemption\game\content.rpf" --all --out logs\content_rpf_full_extract_after_magic_names
```

Result:

- Extracted files: 1320/1320
- Failures: 0
- Script counts: 197 `.sco`, 886 `.wsc`

## Multiplayer / Freemode Correlation

Live PC `content.rpf` extracted as `content\release64` and did not contain the older `content\release\multiplayer` `.csc` branch.

The extracted root reference contains the multiplayer branch here:

`D:\Games\Red Dead Redemption\game\BACKUP BEFORE MODDING\rdr1\mods\root\content\release\multiplayer`

Confirmed important reference scripts:

- `content\release\multiplayer\mp_idle.csc`
- `content\release\multiplayer\multiplayer_system_thread.csc`
- `content\release\multiplayer\multiplayer_update_thread.csc`
- `content\release\multiplayer\pr_multiplayer.csc`
- `content\release\multiplayer\freemode\freemode.csc`
- `content\release\multiplayer\deathmatch\deathmatch.csc`
- `content\release\multiplayer\ctf\ctf_base_game.csc`

Freemode/init inspector command:

```bat
py -3 tools\codered_freemode_init_inspector.py --source "D:\Games\Red Dead Redemption\game\BACKUP BEFORE MODDING\rdr1\mods\root\content\release\multiplayer" --source logs\content_rpf_full_extract_after_magic_names --out logs\content_freemode_init_inspector_path_signals
```

Result:

- Files inspected: 1141
- Signal hits: 2856
- Freemode literal hits: 1
- MP/network hits: 38
- Status: `literal_freemode_found`

## Tooling Fixes

- `python_workbench.py` now searches Code RED research and the game backup Magic-RDR folders for imported filename lists.
- `tools\codered_magic_rdr_bridge.py` now auto-detects MagicRDR.exe under the game backup folder.
- `tools\codered_magic_rdr_bridge.py`, `tools\codered_freemode_init_inspector.py`, and `tools\codered_full_backend_rpf6_harness.py` now treat `.csc` as a script extension.
- `tools\codered_freemode_init_inspector.py` now records path-based script signals, which is required for compiled binary scripts whose internal strings are sparse.

## Boundary

MagicRDR.exe is present locally, but its documented batch examples cover import/replace. Direct `--help` and `/?` probes did not expose a safe extract/list CLI contract. Code RED should keep using the internal RPF6 extractor plus Magic-RDR name-list resources until a real MagicRDR CLI wrapper is confirmed.

No source game RPF was modified.
