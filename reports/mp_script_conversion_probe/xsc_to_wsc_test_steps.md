# XSC to WSC Candidate Test Steps

This pass produced real PC-wrapped WSC candidates from XENON XSC files. They are not extension renames.

## Outputs

- Converted WSC folder: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe\xsc_lzx_pc_wsc_converted`
- Import-ready tree: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe\import_ready_xsc_converted_wsc`
- Conversion report: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_script_conversion_probe\xsc_lzx_to_pc_wsc\xsc_lzx_to_pc_wsc_report.md`
- Import manifest: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_script_conversion_probe\xsc_converted_wsc_import_ready_manifest.csv`

## Safe Test Order

1. Do not overwrite the live `game\content.rpf` directly.
2. Clone a known-booting `content.rpf` into a test RPF.
3. Import only the `import_ready_xsc_converted_wsc` tree into the cloned RPF.
4. Reopen the cloned RPF in Magic RDR.
5. Export a sample converted WSC back out and compare SHA1 with the import manifest.
6. Only then install the cloned RPF for a boot test.
7. If the game boots, test the existing Code RED MP menu/bootstrap route.

## Risk Notes

- Code RED can reopen the converted WSC wrappers and inspect strings/functions/natives.
- Runtime execution is still unproven because the decoded payload originated from XENON bytecode.
- If the game crashes only when a converted script starts, the next blocker is bytecode/native-table/platform compatibility, not RPF import or compression.
