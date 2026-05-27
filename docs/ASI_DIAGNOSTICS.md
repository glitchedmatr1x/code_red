# ASI Diagnostics

Code RED may include original ASI/plugin source and diagnostic logic, but compiled binaries should not live in the default branch.

## Public Repo

- Original C++ source
- Build scripts with placeholder paths
- Config examples
- Diagnostic design notes
- Safe test plans

## Release Assets

Compiled ASI/DLL/EXE builds, if published, should be attached to GitHub Releases only after review. They should not be committed directly to the main branch.

## Path Hygiene

Use placeholders such as `%RDR_GAME_DIR%`, `%CODERED_DEVKIT%`, and `%LOCAL_PATH%` instead of local machine paths.
