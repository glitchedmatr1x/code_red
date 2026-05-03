# Code RED Script Pipeline Report

Generated: 2026-05-03T10:13:10Z
Version: `1.0.0-script-pipeline`

## Workflow

`scan -> read -> open -> edit -> export decompiled/readable -> import/recompile queue`

## Summary

- Records scanned: `58`
- Full reads OK: `58`
- Full reads failed: `0`
- Open targets: `58`
- Editable safe copies: `35`
- Source/text decompiled exports: `35`
- Binary readable exports: `23`
- Import queue items: `35`
- Recompile queue items: `11`
- Blocked compiled-binary roundtrip items: `23`
- New script templates: `3`
- Native hits: `1546`
- Bridge-ready native hits: `26`
- Warnings: `0`

## State Counts

- `compiled_binary_readable_only`: `23`
- `editable_source_pipeline`: `35`

## Outputs

- pipeline_root: `scratch/script_workshop_pipeline`
- scan_index_json: `scratch/script_workshop_pipeline/scan_index/script_pipeline_scan_index.json`
- scan_index_csv: `scratch/script_workshop_pipeline/scan_index/script_pipeline_scan_index.csv`
- open_helper: `scratch/script_workshop_pipeline/open_script_workshop.bat`
- guide: `scratch/script_workshop_pipeline/SCRIPT_PIPELINE_GUIDE.md`
- import_queue: `scratch/script_workshop_pipeline/import_queue/IMPORT_QUEUE.json`
- recompile_queue: `scratch/script_workshop_pipeline/recompile_queue/RECOMPILE_QUEUE.json`
- recompile_helper: `scratch/script_workshop_pipeline/recompile_queue/run_import_recompile_probe.bat`
- report_json: `logs/CodeRED_Script_Pipeline_Report.json`
- report_md: `logs/CodeRED_Script_Pipeline_Report.md`
- pipeline_manifest_json: `data/codered/script_pipeline_manifest.json`
- pipeline_manifest_csv: `data/codered/script_pipeline_manifest.csv`
- capabilities: `data/codered/script_pipeline_capabilities.json`

## Safety

Compiled script binaries are fully read and exported, but binary bytecode roundtrip remains locked until a real compiler/decompiler proof exists.
Source/text files can be edited through safe copies and staged into import/recompile queues.
