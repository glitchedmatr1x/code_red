Code RED Stage Report
=====================

Overall readiness snapshot: 50% of the currently tracked lanes are directly usable in this packaged fallback build.

Live branch
- Python fallback runner: D:\Games\Red Dead Redemption\Code_RED\main.py
- Workspace root: D:\Games\Red Dead Redemption\Code_RED
- Primary archive target: not staged yet
- Bundled demo archive: not found
- Latest archive proof: not run yet
- MP Companion: D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_MP_Companion_v19\mp_companion.py

Workspace footprint
- Files: 208
- Folders: 70
- Size: 32.7 MB
- Archives: 0
- Code-bearing files: 56
- Compiled scripts: 14
- Skipped generated/cache folders: 3
- Skipped generated/cache files: 0
- Scan capped: no

Lane status
- [READY] Python fallback UI: WorkbenchApp boots and the main interface is live in this branch.
- [READY] Archive inventory/export: RPF6 parse, inventory, export, and archive-copy patching are wired in the Python runner.
- [PARTIAL] Archive proof pass: A copied-archive proof pass has not been completed yet in this workspace.
- [READY] Source file editing: Code-bearing text files can be reviewed and edited directly.
- [PARTIAL] Source validation probes: Host-native C/C++/C# validation probes are available for at least part of the helper-source lane.
- [READY] MP companion handoff: Bundled companion path: D:\Games\Red Dead Redemption\Code_RED\related_apps\Code_RED_MP_Companion_v19\mp_companion.py
- [PARTIAL] Script compile-back: Compiler-backed rebuild remains Windows-first and depends on SC-CL availability.
- [PARTIAL] Rebuild-proven existing game scripts: Existing binary scripts are still not rebuild-proven end-to-end.

Host source-validation tooling
- C compiler probe: missing
- C++ compiler probe: missing
- C# compiler probe: missing
- dotnet host: C:\Program Files\dotnet\dotnet.EXE

Bundled script tooling
- Compile state: missing
- SC-CL compiler detected: no
- Magic-RDR staged: no

Most doable next
- 1. Use Stage Bundled Archive or drop a real content.rpf, then run Archive Proof Pass.
- 2. Use the Source lane to validate C/C++ helper files with the host compiler probes now available in this runtime.
- 3. Keep tightening guided one-click actions for imports, logs, and the primary archive target.

Actionable staging
- Imports folder: D:\Games\Red Dead Redemption\Code_RED\imports
- Logs folder: D:\Games\Red Dead Redemption\Code_RED\logs
- Expected archive drop path: D:\Games\Red Dead Redemption\Code_RED\imports\content.rpf
- Latest archive proof report: not run yet