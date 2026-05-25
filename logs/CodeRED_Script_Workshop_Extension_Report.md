# Code RED Script Workshop Extension Report

Generated: 2026-05-23T21:45:55Z
Version: `1.1.0-script-workshop-extension-hardening`

## Summary

- Records: `514`
- Editable source/text files: `503`
- Compiled binary read-only files: `11`
- Import queue items: `503`
- Recompile queue items: `9`
- New script templates: `3`

## Safety

Source/text files can be edited through safe workspace copies. Compiled script binaries are read/exported but remain blocked from bytecode roundtrip until Windows compiler/decompiler proof exists.
