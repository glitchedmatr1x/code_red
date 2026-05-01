# CodeREDCompanion ASI

`CodeREDCompanion.asi` is the safe ASI lane for Code RED.

Current pass:

```text
0.3.0-polling-id-whitelist-proof
```

This pass is still intentionally harmless:

- no hooks
- no pattern scanning
- no memory patches
- no script injection
- no game file writes
- no actor spawning yet
- no trainer commands executed yet

## What Pass 0.3 adds

Pass 0.3 upgrades the ASI from a one-time startup scan to a low-rate live proof loop:

```text
poll interval: 3000 ms
command file: data/codered/companion_commands.txt
status file: CodeRED_ASI_Logs/companion_status.json
log file: CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
```

It now tracks command IDs so the same command does not get processed repeatedly every poll.

Supported command line format:

```text
ID=my_unique_command_id PING
ID=my_unique_command_id STATUS
ID=my_unique_command_id VERSION
ID=my_unique_command_id HELP
ID=my_unique_command_id SPAWN_ACTOR ACTOR_CAUCASIAN_ARMY_Easy01
```

If no `ID=` prefix is present, the ASI generates a stable automatic ID from the command body. That means identical repeated lines are treated as duplicates.

Only these commands are accepted in Pass 0.3:

```text
PING
STATUS
VERSION
HELP
```

They are still no-op proof commands. They only prove that the plugin can safely read, validate, and de-duplicate Code RED command text.

These future commands are recognized but blocked:

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

Actor-style future commands are checked against this whitelist before being reported:

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

Whitelisted future commands are still blocked. The whitelist only proves validation is working before we attempt any real trainer/actor lane.

## Helper command writer

A helper script was added:

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

The helper refuses unsupported commands and refuses future actor commands with actors outside the Pass 0.3 whitelist.

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
4. Create commands with the helper or copy:

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
```

A good Pass 0.3 proof contains:

```text
Hooks installed: false
Memory patches applied: false
Game files modified: false
Actor spawning enabled: false
actor_whitelist_enforced: true
poll_count increasing over time
future commands blocked
repeated command IDs skipped
```

The sample `SPAWN_ACTOR` and `FOLLOW` lines should be validated and blocked, not executed.

## Safety behavior

The plugin caps command intake to 32 non-comment commands per poll. Each line is clamped to 512 characters. Blank lines, `#` comments, and `;` comments are ignored.

## Next pass after proof

After polling and ID proof work, the next safe additions should be:

1. Add a small GUI tab/button in Code RED for companion commands.
2. Add a command archive file so completed IDs can be reviewed outside the ASI.
3. Add a trainer bridge stub that logs intended actor actions without calling game functions.
4. Keep actor/trainer commands disabled until the ASI artifact has been tested in-game.

## Credit

by GLITCHED MATRIX Prototype Lab
