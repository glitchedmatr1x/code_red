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

## WSC As C/Source Editing

This is not implemented yet. Code RED will not fake it.

The requested capabilities are blocked until the project has a real WSC bytecode decompiler/rebuilder:

- open existing WSC as C/source
- change recovered functions
- add new code into an existing WSC
- expand strings freely
- rebuild internal WSC sections
- understand bytecode automatically

Use this command to write the current blocked-status report for a workspace or WSC:

```bat
Run_CodeRED_WSC_Edit_Workflow.bat source-edit-status --workspace build\wsc_edit\binary_initpopulation
```

Required missing pieces:

- WSC/RSC85 internal section table parser with validated offsets, lengths, alignment, and checksums
- RDR WSC bytecode decoder with opcode table, operand formats, jump/call targets, locals, globals, and native call metadata
- control-flow graph and function boundary recovery
- IR-to-C or pseudocode lifter that can round-trip enough structure for edits
- assembler/recompiler from edited IR/source back to valid WSC bytecode
- container rebuilder that can expand strings/code and update all affected section offsets, lengths, relocations, and resource metadata
- runtime validation corpus proving rebuilt WSCs boot and execute beyond trivial string/byte patches

## Boundary

Code RED still does not have a proven WSC bytecode-to-source decompiler. `decompile` is an alias for creating an existing-file binary edit workspace: it extracts and inspects the original WSC, but it does not recover original source.
