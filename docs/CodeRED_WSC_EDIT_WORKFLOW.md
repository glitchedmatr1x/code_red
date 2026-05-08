# Code RED WSC Edit Workflow

Code RED now has two separate WSC lanes.

## WSC Binary Edit / Existing-File Patch

This is the default edit workflow. It preserves the original WSC as the base:

- extracts the selected WSC from the source RPF
- writes `original\...wsc`
- writes editable `edited\...wsc` as an exact copy
- inspects header, body, section candidates, printable strings, and offsets
- applies controlled length-preserving string or byte patches
- packs the edited original-derived WSC into a copied RPF

It does not generate `src\main.c` and call that an edit.

```bat
Run_CodeRED_WSC_Edit_Workflow.bat init --name binary_initpopulation --archive-path root/content/release64/init/initpopulation.wsc
Run_CodeRED_WSC_Edit_Workflow.bat inspect --workspace build\wsc_edit\binary_initpopulation
Run_CodeRED_WSC_Edit_Workflow.bat strings --workspace build\wsc_edit\binary_initpopulation
Run_CodeRED_WSC_Edit_Workflow.bat replace-string --workspace build\wsc_edit\binary_initpopulation --find OLD_TEXT --replace NEW_TEXT
Run_CodeRED_WSC_Edit_Workflow.bat patch-bytes --workspace build\wsc_edit\binary_initpopulation --offset 0x20 --expected-hex AA --hex BB
Run_CodeRED_WSC_Edit_Workflow.bat pack --workspace build\wsc_edit\binary_initpopulation --write
```

Length-changing string replacement is refused unless a future RSC85/script-container rebuilder is implemented. Shorter replacements can be made length-preserving with `--pad nul` or `--pad space`.

The pack command refuses to overwrite its source archive and refuses outputs inside the live `game` or `RDR-SteamGG.NET` folders.

## WSC Full Replacement / Source-Built Replacement

This lane remains available, but it is explicitly named as full replacement. It creates `src\main.c`, compiles through SC-CL, converts XSC to WSC/RSC85, and replaces the selected archive entry with that newly built WSC.

```bat
Run_CodeRED_WSC_Edit_Workflow.bat full-replace-init --name source_wait_probe --archive-path root/content/release64/init/initpopulation.wsc
Run_CodeRED_WSC_Edit_Workflow.bat full-replace-compile --workspace build\wsc_edit\source_wait_probe --clean
Run_CodeRED_WSC_Edit_Workflow.bat pack --workspace build\wsc_edit\source_wait_probe --write
```

## Boundary

Code RED still does not have a proven WSC bytecode-to-source decompiler. `decompile` is an alias for creating an existing-file binary edit workspace: it extracts and inspects the original WSC, but it does not recover original source.
