# Code RED Patch Candidate Report

- Source: `imports\medium_update_thread.wsc`
- Candidate kind: `branch`
- Candidate rows: `8222`
- READ_ONLY: `7632`
- SAME_SIZE_SAFE: `0`
- CONTROL_FLOW_SAFE: `590`
- REBUILD_REQUIRED: `0`
- UNSUPPORTED: `0`

Patchability labels describe the current tool guarantee. `READ_ONLY` candidates are analysis evidence and must not be edited by a recipe yet.
Current `SAME_SIZE_SAFE` coverage is fixed-width constant operands, same-length printable strings, and mapped population table enum operands.
