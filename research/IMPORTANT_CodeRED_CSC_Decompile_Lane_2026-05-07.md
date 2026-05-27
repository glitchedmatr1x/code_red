# IMPORTANT: Code RED CSC Script Lane Pass

Date: 2026-05-07

## Summary

Code RED now routes `.csc` files through the same safe script inventory and pseudo-decompile workflow lanes as `.wsc`, `.xsc`, `.sco`, and `.wsv`.

This does not claim real bytecode-to-source decompile. It makes extracted `.csc` files visible to the tools so an explicit decompiler command/template can run once a real CSC-capable decompiler is found.

## Updated Lanes

- Main Workbench script lane: `.wsc`, `.csc`, `.xsc`, `.sco`, `.wsv`
- Script Decompile Attempt inventory and filename scans include `.csc`
- Script Workshop inventory includes `.csc`
- RPF Deep Probe script/resource scans include `.csc`
- Full Workbench script binary analysis/viewer/export gates include `.csc`
- Anti-regression now guards `.csc` in filesystem, synthetic RPF, ZIP, and CLI archive scans

## Validation

- `py -3 -m py_compile code_red_main.py python_workbench.py tools\codered_script_decompile_attempt.py tools\codered_script_workshop.py tools\codered_rpf_deep_probe.py tools\codered_anti_regression.py tools\codered_script_compile_validation.py`
- `py -3 code_red_main.py --self-test`
- `py -3 tools\codered_anti_regression.py`
- `py -3 tools\codered_script_decompile_attempt.py --source "D:\Games\Red Dead Redemption\game\BACKUP BEFORE MODDING\rdr1\mods\root\content\release\multiplayer" --out logs\freemode_csc_decompile_attempt_inventory`
- `py -3 tools\codered_script_workshop.py --source "D:\Games\Red Dead Redemption\game\BACKUP BEFORE MODDING\rdr1\mods\root\content\release\multiplayer" --out logs\freemode_csc_script_workshop_inventory`
- `py -3 tools\codered_freemode_init_inspector.py --source "D:\Games\Red Dead Redemption\game\BACKUP BEFORE MODDING\rdr1\mods\root\content\release\multiplayer" --out logs\freemode_csc_init_inspector`

## Results

- Script Decompile Attempt found `45` extracted `.csc` files.
- Script Workshop found `45` script resources, all `.csc`.
- Freemode Init Inspector found `45` files, `80` signal hits, `1` freemode literal hit, and `3` MP/network hits.
- Anti-regression passed with `.csc` included in script lane guards.

## Decompiler Status

Local tool search found SC-CL compiler binaries and MagicRDR archive tools, but no proven CSC/WSC/XSC/SCO bytecode-to-source decompiler executable or command template. Keep using readable/pseudo-decompile reports until that tool is proven.
