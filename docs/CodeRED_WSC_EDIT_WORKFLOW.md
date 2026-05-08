# Code RED WSC Edit Workflow

This workflow is source-first and intentionally safe:

- It does not overwrite `D:\Games\Red Dead Redemption\game\content.rpf`.
- It does not pretend compiled `.wsc` bytecode can be recovered as original source.
- It creates editable source in `build\wsc_edit\<name>\src\main.c`.
- It compiles through SC-CL, converts the resulting XSC to WSC/RSC85, and packs a copied RPF under `build\wsc_edit\<name>\packed\content.rpf`.

## Commands

```bat
Run_CodeRED_WSC_Edit_Workflow.bat decompile --name codered_wait_probe --archive-path root/content/release64/init/initpopulation.wsc
Run_CodeRED_WSC_Edit_Workflow.bat recompile --workspace build\wsc_edit\codered_wait_probe --clean
Run_CodeRED_WSC_Edit_Workflow.bat pack --workspace build\wsc_edit\codered_wait_probe
Run_CodeRED_WSC_Edit_Workflow.bat pack --workspace build\wsc_edit\codered_wait_probe --write
```

`decompile` extracts and inspects the original binary WSC and creates an editable source scaffold. It does not recover the original game source. The first `pack` command is a dry-run. The `--write` command writes only the copied archive declared in the workspace manifest.

The pack command refuses to overwrite its source archive and refuses outputs inside the live `game` or `RDR-SteamGG.NET` folders.

## Inspection

```bat
Run_CodeRED_WSC_Edit_Workflow.bat inspect --input logs\content_mp_singleplayer_build_probe\extracted_signals\root_content_release64_init_initpopulation.wsc
```

Inspection reports headers, hash, size, and printable strings. It is not a source decompiler.

## Verified Smoke Test

The `codered_wait_probe` smoke test was run against `root/content/release64/init/initpopulation.wsc` from `D:\Games\Red Dead Redemption\game\content.rpf`.

Validated outputs:

- Compiled WSC: `build\wsc_edit\codered_wait_probe\compiled\codered_wait_probe.wsc`
- Packed copied RPF: `build\wsc_edit\codered_wait_probe\packed\content.rpf`
- Pack report: `logs\wsc_edit\codered_wait_probe\manual_wsc_codered_wait_probe_overlay_report.json`
- Packed inventory: `logs\wsc_edit\codered_wait_probe\packed_inventory\rpf_inventory.json`

The compiled WSC SHA1 matched the extracted packed replacement SHA1:

`0806E5B49EACA462E10CFDFCF73C85CB977D260A`
