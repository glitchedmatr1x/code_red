# Code RED Script Pipeline Guide

Workflow target:

```text
scan -> read -> open -> edit -> export decompiled/readable -> import/recompile queue
```

## Safe folders

- `scan_index/` - script inventory and state tables.
- `read_full/` - full read copies/reports for every indexed script item.
- `edit_workspace/` - safe editable source/text copies.
- `decompiled_export/` - source decompiled exports and binary readable reports.
- `import_queue/` - edited files staged for import/recompile decisions.
- `recompile_queue/` - source candidates and Windows recompile helper.
- `new_script_templates/` - starter scripts for adding new Script Workshop entries.

Compiled `.wsc`, `.csc`, `.xsc`, `.sco`, and `.ysc` binaries remain read-only until real bytecode/compiler roundtrip proof exists.
