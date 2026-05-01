# CodeREDCompanion ASI

`CodeREDCompanion.asi` is the safe ASI lane for Code RED.

Current pass:

```text
0.5.0-override-manifest-proof
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

## What Pass 0.5 adds

Pass 0.5 keeps command polling, command IDs, command archiving, and the trainer bridge stub, then adds proof-only override manifest scanning:

```text
override root: CodeRED_Overrides/
override manifest: CodeRED_Overrides/manifest.json
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

New safe command:

```text
SCAN_OVERRIDES
```

Example:

```bat
py -3 tools\codered_companion_command_writer.py SCAN_OVERRIDES --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET"
```

This only scans and reports. It does not redirect files.

## Override manifest tool

New helper:

```text
tools/codered_override_manifest_tool.py
```

Initialize a proof manifest:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" --replace init
```

Add a proof override file:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" add my_test.xtbl content/tune/refgroups/my_test.xtbl
```

Scan without writing:

```bat
py -3 tools\codered_override_manifest_tool.py --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET" scan
```

The manifest is generated with:

```text
enabled: false
mode: proof_only
file_redirects_enabled: false
archive_writes_enabled: false
```

Allowed extensions in Pass 0.5:

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
6. Write a `SCAN_OVERRIDES` command.
7. Launch the game or wait for the ASI poll loop if already loaded.
8. Check for:

```text
CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
CodeRED_ASI_Logs/companion_status.json
CodeRED_ASI_Logs/companion_command_archive.jsonl
CodeRED_ASI_Logs/trainer_bridge_stub.json
CodeRED_ASI_Logs/file_override_stub.json
CodeRED_ASI_Logs/file_override_events.jsonl
```

A good Pass 0.5 proof contains:

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
SCAN_OVERRIDES archived and logged
```

## Safety behavior

The plugin caps command intake to 32 non-comment commands per poll. Each line is clamped to 512 characters. Blank lines, `#` comments, and `;` comments are ignored. Override scanning is proof-only and caps reported candidate details to 128 files.

## Next pass after proof

After the ASI artifact is tested in-game, the next safe additions should be:

1. Add manifest rule editing to the panel.
2. Add richer validation for virtual RPF paths.
3. Add a redirect adapter interface, still disabled by default.
4. Only then consider one controlled Windows file-open redirect experiment for loose files, not RPF internals yet.

## Credit

by GLITCHED MATRIX Prototype Lab
