# Code RED Script Workshop Extension Report

Generated: 2026-05-05T04:28:42Z
Version: `1.1.0-script-workshop-extension-hardening`

## Summary

- Records: `345`
- Editable source/text files: `334`
- Compiled binary read-only files: `11`
- Import queue items: `334`
- Recompile queue items: `6`
- New script templates: `3`

## Safety

Source/text files can be edited through safe workspace copies. Compiled script binaries are read/exported but remain blocked from bytecode roundtrip until Windows compiler/decompiler proof exists.
