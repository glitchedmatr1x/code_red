# Code RED Portable Script Reader

`tools/codered_portable_script_reader.py` is a dependency-free, read-first scanner for loose extracted RDR script/resource files.

It does **not** decompile script bytecode, bypass authentication, patch archives, or edit game files. Compiled resources such as `.wsc`, `.sco`, `.csc`, `.xsc`, and `.wsv` are inspected by string mining only. SCXML/XML/text resources are read as text.

## Why this exists

Code RED already has Script Workshop, Script Pipeline, RPF lanes, and Magic-RDR bridge tooling. This tool is the portable fallback for situations where:

- Codex is unavailable.
- MagicRDR or SC-CL is not installed on the current machine.
- Extracted files are scattered across local folders.
- We need a quick auth/session/freeroam/DLC signal report without touching archives.

## Basic usage

```bat
py -3 tools\codered_portable_script_reader.py --source game --out logs\portable_script_reader
```

Scan multiple folders:

```bat
py -3 tools\codered_portable_script_reader.py --source game --source imports --source research --out logs\portable_script_reader
```

Focused DLC / bonus-pack pass:

```bat
py -3 tools\codered_portable_script_reader.py --source game --profile dlc --out logs\dlc_mode_reader
```

Wide pass:

```bat
py -3 tools\codered_portable_script_reader.py --source game --profile all --out logs\script_reader_all
```

Add custom terms:

```bat
py -3 tools\codered_portable_script_reader.py --source game --profile freeroam --term TriggerMultiplayerLoad --term StartGameWish --term MULTI_FREE_ROAM --out logs\freeroam_trace
```

## Outputs

The output folder contains:

- `portable_script_reader_summary.json`
- `portable_script_reader_files.json`
- `portable_script_reader_hits.json`
- `portable_script_reader_files.csv`
- `portable_script_reader_hits.csv`
- `portable_script_reader_report.md`

## Best current Code RED use

For the freeroam/bootstrap issue, use this after extracting `content.rpf` or DLC/bonus archives into a local ignored folder:

```bat
py -3 tools\codered_portable_script_reader.py --source game --profile all --out logs\freeroam_bootstrap_reader
```

Then inspect the highest scoring files for:

- `TriggerMultiplayerLoad`
- `StartMultiplayer`
- `RequestJoin`
- `SetGameWish`
- `StartGameWish`
- `NetMachine`
- `HudSceneOnline`
- `MULTI_FREE_ROAM`
- loading/safe spawn/save/profile/resource mount signals

## Limitations

- This is not a bytecode decompiler.
- String hits from compiled resources prove only that a signal exists nearby in the binary resource, not exact control flow.
- It cannot extract RPFs by itself. Use Code RED archive lanes, MagicRDR, or another safe extractor first.
- It should not be used to build authentication bypasses or live archive patches.
