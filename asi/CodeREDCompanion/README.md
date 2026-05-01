# CodeREDCompanion ASI

`CodeREDCompanion.asi` is the safe ASI lane for Code RED.

Current pass:

```text
0.6.0-override-editor-validator-proof
```

This pass is intentionally harmless:

- no hooks
- no pattern scanning
- no memory patches
- no script injection
- no game file writes
- no file redirects yet
- no archive writes yet
- no actor spawning yet
- no trainer commands executed yet

## What Pass 0.6 adds

Pass 0.6 keeps command polling, command IDs, command archiving, the trainer bridge stub, and proof-only override scanning. It adds a stronger override editor/validator lane:

```text
override root: CodeRED_Overrides/
override manifest: CodeRED_Overrides/manifest.json
override validation report: CodeRED_ASI_Logs/override_manifest_validation_report.json
override proof report: CodeRED_ASI_Logs/file_override_stub.json
override event log: CodeRED_ASI_Logs/file_override_events.jsonl
command archive: CodeRED_ASI_Logs/companion_command_archive.jsonl
trainer bridge stub: CodeRED_ASI_Logs/trainer_bridge_stub.json
standalone GUI panel: tools/codered_companion_command_panel.py
root launcher: Run_CodeRED_Companion_Command_Panel.bat
writer history: CodeRED_ASI_Logs/companion_command_writer_history.jsonl
```

The ASI still polls:

```text
poll interval: 3000 ms
command file: data/codered/companion_commands.txt
status file: CodeRED_ASI_Logs/companion_status.json
log file: CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
```

## Override proof command

Safe command:

```text
SCAN_OVERRIDES
```

Example:

```bat
py -3 tools\codered_companion_command_writer.py SCAN_OVERRIDES --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET"
```

This only scans and reports. It does not redirect files.

## Override manifest tool

Helper:

```text
tools/codered_override_manifest_tool.py
```

Initialize a proof manifest:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" --replace init
```

List presets:

```bat
py -3 tools\codered_override_manifest_tool.py presets
```

Add a proof override file by virtual path:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" --replace add my_test.xtbl content/tune/refgroups/my_test.xtbl
```

Add a proof override with a preset:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" --replace add-preset tune-refgroup blackwater my_test.xtbl
```

Validate and write a report:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" validate
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" write-report
```

Enable or disable proof rules by id or virtual path:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" enable content/tune/refgroups/blackwater.xtbl
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" disable content/tune/refgroups/blackwater.xtbl
```

The manifest is forced to remain proof-only:

```text
enabled: false
mode: proof_only
file_redirects_enabled: false
archive_writes_enabled: false
redirect_adapter.enabled: false
redirect_adapter.mode: disabled_proof_only
```

Virtual path presets:

```text
tune-refgroup -> content/tune/refgroups/{name}.xtbl
tune-table    -> content/tune/{name}.xtbl
string-table  -> content/strings/{name}.strtbl
script-source -> content/scripts/{name}.wsc
config-json   -> content/config/{name}.json
text-note     -> content/notes/{name}.txt
```

Allowed extensions in Pass 0.6:

```text
.xtbl
.xml
.txt
.strtbl
.wsc
.json
.ini
.cfg
```

Denied extensions:

```text
.exe
.dll
.asi
.bat
.cmd
.ps1
```

## Command IDs and archive

Supported command line format:

```text
ID=my_unique_command_id PING
ID=my_unique_command_id STATUS
ID=my_unique_command_id VERSION
ID=my_unique_command_id HELP
ID=my_unique_command_id SCAN_OVERRIDES
ID=my_unique_command_id SPAWN_ACTOR ACTOR_CAUCASIAN_ARMY_Easy01
```

New command IDs are appended to:

```text
CodeRED_ASI_Logs/companion_command_archive.jsonl
```

Duplicate command IDs are skipped and are not re-archived.

## Trainer bridge stub

Future actor commands are still blocked, but intended actor/trainer actions are summarized in:

```text
CodeRED_ASI_Logs/trainer_bridge_stub.json
```

This file is proof-only. It logs what would be sent to a trainer bridge later. It does not call a trainer, does not spawn actors, and does not patch memory.

## GUI command panel

Run from the repo root:

```bat
Run_CodeRED_Companion_Command_Panel.bat
```

Or directly:

```bat
py -3 tools\codered_companion_command_panel.py
```

The panel can:

- choose the game folder
- write command IDs
- dry-run commands
- initialize `CodeRED_Overrides/manifest.json`
- add override files by virtual path
- add override files by preset
- validate the manifest
- write the validation report
- write `SCAN_OVERRIDES`
- open the ASI logs folder
- read `companion_status.json`

## Build from Windows

Requirements:

- Windows 10 or newer
- Visual Studio 2022 Build Tools or Visual Studio 2022
- CMake 3.21+

From this folder:

```bat
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

Output:

```text
build/dist/RELEASE/CodeREDCompanion.asi
```

## Build through GitHub Actions

Use the workflow:

```text
.github/workflows/build-codered-asi.yml
```

It builds on a Windows runner and uploads `CodeREDCompanion.asi` plus `CodeREDCompanion_ASI_manifest.txt` as an artifact.

## First test

1. Build `CodeREDCompanion.asi`.
2. Place it next to the target game's executable only in a backed-up test folder.
3. Make sure your ASI loader is installed for that game/runtime.
4. Run the panel or initialize the manifest manually.
5. Add test files under `CodeRED_Overrides/`.
6. Validate the manifest and write a report.
7. Write a `SCAN_OVERRIDES` command.
8. Launch the game or wait for the ASI poll loop if already loaded.
9. Check for:

```text
CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
CodeRED_ASI_Logs/companion_status.json
CodeRED_ASI_Logs/companion_command_archive.jsonl
CodeRED_ASI_Logs/trainer_bridge_stub.json
CodeRED_ASI_Logs/file_override_stub.json
CodeRED_ASI_Logs/file_override_events.jsonl
CodeRED_ASI_Logs/override_manifest_validation_report.json
```

A good Pass 0.6 proof contains:

```text
Hooks installed: false
Memory patches applied: false
Game files modified: false
File redirects enabled: false
Archive writes enabled: false
Actor spawning enabled: false
Trainer calls enabled: false
override root scanned
override manifest detected if initialized
allowed and rejected override candidate counts
validation report written
redirect adapter disabled
SCAN_OVERRIDES archived and logged
```

## Safety behavior

The plugin caps command intake to 32 non-comment commands per poll. Each line is clamped to 512 characters. Blank lines, `#` comments, and `;` comments are ignored. Override scanning is proof-only and caps reported candidate details to 128 files.

## Next pass after proof

After the ASI artifact is tested in-game, the next safe additions should be:

1. Add a disabled redirect adapter interface in C++ with explicit per-rule gates.
2. Add one controlled loose-file redirect experiment for non-archive files only.
3. Keep RPF internals untouched until loose-file redirection is proven safe.

## Credit

by GLITCHED MATRIX Prototype Lab
