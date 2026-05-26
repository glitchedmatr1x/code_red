# XENON Full Conversion Pass 2

Goal: make sure every XENON multiplayer script resource in the XENON folder is converted into PC WSC form for MagicRDR/Code RED indexing and future safe patching. No live RPF was edited.

## Source
- `D:\Games\Red Dead Redemption\game\XENON MULTIPLAYER\content\release64\multiplayer`

## Conversion Results
- Named `.xsc` resources converted: `56`
- Extensionless/hash-named XSC resources converted: `8`
- Total converted script resources: `64`

## Output Folders
- Editable WSC tree: `D:\Games\Red Dead Redemption\Code_RED\build\mp_xenon_full_conversion_pass2\all_converted_editable_wsc`
- Import-ready tree preserving hash names: `D:\Games\Red Dead Redemption\Code_RED\build\mp_xenon_full_conversion_pass2\all_converted_import_ready_preserve_hash_names`
- Convenience copy next to source: `D:\Games\Red Dead Redemption\game\XENON MULTIPLAYER\converted_full_pass2`

## Validation
- Code RED inspect smoke: `64/64` passed
- MagicRDR compatibility: `64/64` passed

## Important Layout Notes
- `all_converted_editable_wsc` is the folder to use for MagicRDR/Code RED editing and indexing.
- The 8 extensionless/hash-named scripts are also provided as `.wsc` sidecars under `_hash_named_extensionless_editable` so tools can open them.
- `all_converted_import_ready_preserve_hash_names` keeps those 8 files under their original no-extension archive names, because importing them with invented `.wsc` names would change the archive path semantics.

## Reports
- Manifest: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_xenon_full_conversion_pass2\all_converted_manifest.csv`
- Named XSC conversion report: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_xenon_full_conversion_pass2\xsc_named_conversion\xsc_lzx_to_pc_wsc_report.md`
- Extensionless conversion report: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_xenon_full_conversion_pass2\extensionless_conversion\xsc_lzx_to_pc_wsc_report.md`
- MagicRDR report: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_xenon_full_conversion_pass2\magicrdr_all_converted_compat\magicrdr_wsc_compat_report.md`
- Code RED inspect smoke: `D:\Games\Red Dead Redemption\Code_RED\reports\mp_xenon_full_conversion_pass2\codered_all_converted_inspect_smoke.csv`

## Not Done
- No live `game/content.rpf` modification.
- No runtime compatibility claim beyond parser/open validation.
- No PSN `.csc` / RSC86 conversion in this pass.
