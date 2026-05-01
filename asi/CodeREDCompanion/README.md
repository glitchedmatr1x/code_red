# CodeREDCompanion ASI

`CodeREDCompanion.asi` is the safe ASI lane for Code RED.

Current pass:

```text
0.4.0-archive-bridge-stub-proof
```

This pass is still intentionally harmless:

- no hooks
- no pattern scanning
- no memory patches
- no script injection
- no game file writes
- no actor spawning yet
- no trainer commands executed yet

## What Pass 0.4 adds

Pass 0.4 keeps the Pass 0.3 polling/id/whitelist proof and adds:

```text
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

## Command IDs and archive

Supported command line format:

```text
ID=my_unique_command_id PING
ID=my_unique_command_id STATUS
ID=my_unique_command_id VERSION
ID=my_unique_command_id HELP
ID=my_unique_command_id SPAWN_ACTOR ACTOR_CAUCASIAN_ARMY_Easy01
```

New command IDs are appended to:

```text
CodeRED_ASI_Logs/companion_command_archive.jsonl
```

Duplicate command IDs are skipped and are not re-archived.

## Trainer bridge stub

Future commands are still blocked, but intended actor/trainer actions are now summarized in:

```text
CodeRED_ASI_Logs/trainer_bridge_stub.json
```

This file is proof-only. It logs what would be sent to a trainer bridge later. It does not call a trainer, does not spawn actors, and does not patch memory.

## Accepted commands

Only these commands are accepted in Pass 0.4:

```text
PING
STATUS
VERSION
HELP
```

These future commands are recognized, whitelist-checked, archived, and bridge-stub logged, but blocked:

```text
SPAWN_ACTOR
FOLLOW
GUARD
ATTACK
DISMISS
MOUNT
WAYPOINT
TELEPORT
SET_FORMATION
```

Actor-style future commands are checked against this whitelist:

```text
ACTOR_CAUCASIAN_ARMY_Easy01
AE_CAUCASIAN_ARMY_EASY01
ACTOR_CAUCASIAN_MALE_TownFolk02
ACTOR_RIDEABLE_ANIMAL_Horse01
ACTOR_RIDEABLE_ANIMAL_MEX_Mule01
ACTOR_VEHICLE_Car01
ACTOR_VEHICLE_Truck01
ACTOR_VEHICLE_Stagecoach
ACTOR_VEHICLE_Wagon02
ACTOR_VEHICLE_Coach01
```

Whitelisted future commands are still blocked. The whitelist only proves validation is working before real trainer/actor work.

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
- write safe commands and future blocked commands
- open the ASI logs folder
- read `companion_status.json`

## CLI command writer

A helper script is still available:

```text
tools/codered_companion_command_writer.py
```

Examples from the Code_RED repo root:

```bat
py -3 tools\codered_companion_command_writer.py PING --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET"
py -3 tools\codered_companion_command_writer.py STATUS --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET"
py -3 tools\codered_companion_command_writer.py SPAWN_ACTOR --actor ACTOR_CAUCASIAN_ARMY_Easy01 --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET"
py -3 tools\codered_companion_command_writer.py PING --replace --game-root "D:\Games\Red Dead Redemption\RDR-SteamGG.NET"
```

Dry run:

```bat
py -3 tools\codered_companion_command_writer.py SPAWN_ACTOR --actor ACTOR_VEHICLE_Car01 --dry-run
```

The helper refuses unsupported commands and refuses future actor commands with actors outside the Pass 0.4 whitelist.

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
4. Create commands with the panel, the helper, or copy:

```text
asi/CodeREDCompanion/samples/companion_commands.txt
```

to:

```text
data/codered/companion_commands.txt
```

5. Launch the game.
6. Check for:

```text
CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
CodeRED_ASI_Logs/companion_status.json
CodeRED_ASI_Logs/companion_command_archive.jsonl
CodeRED_ASI_Logs/trainer_bridge_stub.json
```

A good Pass 0.4 proof contains:

```text
Hooks installed: false
Memory patches applied: false
Game files modified: false
Actor spawning enabled: false
Trainer calls enabled: false
trainer_bridge_stub_only: true
actor_whitelist_enforced: true
poll_count increasing over time
future commands archived and bridge-stub logged, not executed
repeated command IDs skipped
```

## Safety behavior

The plugin caps command intake to 32 non-comment commands per poll. Each line is clamped to 512 characters. Blank lines, `#` comments, and `;` comments are ignored.

## Next pass after proof

After the ASI artifact is tested in-game, the next safe additions should be:

1. Add a Code RED workbench button that launches `Run_CodeRED_Companion_Command_Panel.bat`.
2. Add a true trainer bridge adapter interface, still stubbed by default.
3. Add per-command enable flags so actor commands can be enabled one at a time.
4. Keep all game execution disabled until one command is proven in a backed-up test folder.

## Credit

by GLITCHED MATRIX Prototype Lab
