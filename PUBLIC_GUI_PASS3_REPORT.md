# Code RED Public GUI Pass 3 Report

## Summary

Replaced the default public GUI with a focused Script Lab + RPF Browser front door. The old button-wall workbench is no longer launched by default.

## Primary workflows

- Script Lab for `.wsc`, `.xsc`, `.csc`, and `.sco` viewing/inspection.
- Same-size string recipe generation.
- Same-size patched-copy output. Originals are not overwritten.
- RPF/ZIP Browser for read-only inventory and reports.
- GPT Packet export for compact handoff to users or AI agents.

## Top-level actions

- Open Script
- Open RPF/ZIP
- Open Folder
- Inspect
- Save Patch Copy
- Export GPT Packet

## Tabs

- Script Lab
- RPF Browser
- Recipe
- GPT Packet
- Log

## Public safety

- No raw RPF files are bundled.
- No extracted retail script files are bundled.
- No compiled ASI/EXE/DLL/OBJ files are bundled.
- RPF GUI operations are read-only.
- Script edits write a user-selected copy.

## Validation

```json
{
  "python_files": 158,
  "python_compile_failures": [],
  "blocked_file_hits": [],
  "blocked_dir_hits": [],
  "file_count": 337
}
```
