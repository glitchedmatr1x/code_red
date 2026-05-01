# CodeREDCompanion ASI

`CodeREDCompanion.asi` is the safe ASI lane for Code RED.

Current pass:

```text
0.2.0-command-status-proof
```

This pass is still intentionally harmless:

- no hooks
- no pattern scanning
- no memory patches
- no script injection
- no game file writes
- no actor spawning yet
- no trainer commands executed yet

## What Pass 0.2 adds

When loaded by an ASI loader, it now writes:

```text
CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
CodeRED_ASI_Logs/companion_status.json
```

It also checks for an optional command file beside the host executable:

```text
data/codered/companion_commands.txt
```

Only these commands are accepted in Pass 0.2:

```text
PING
STATUS
VERSION
HELP
```

They are still no-op proof commands. They only prove that the plugin can safely read and validate Code RED command text.

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

Any blocked command is reported in `companion_status.json` with:

```text
recognized_future_command_disabled_in_pass_0_2
```

Unknown commands are reported as:

```text
unknown_command
```

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
4. Optionally create:

```text
data/codered/companion_commands.txt
```

Example contents:

```text
PING
STATUS
VERSION
HELP
SPAWN_ACTOR ACTOR_CAUCASIAN_ARMY_Easy01
```

5. Launch the game.
6. Check for:

```text
CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
CodeRED_ASI_Logs/companion_status.json
```

A good Pass 0.2 proof contains:

```text
Hooks installed: false
Memory patches applied: false
Game files modified: false
Actor spawning enabled: false
Command/status proof complete: true
```

The sample `SPAWN_ACTOR` line should be blocked, not executed.

## Safety behavior

The plugin caps command intake to 32 non-comment commands. Each line is clamped to 512 characters. Blank lines, `#` comments, and `;` comments are ignored.

## Next pass after proof

After loader proof and status JSON work, the next safe additions should be:

1. Add a tiny Code RED desktop helper that writes `companion_commands.txt`.
2. Add repeated polling with a slow interval instead of one startup read.
3. Add command IDs so repeated commands are not reprocessed.
4. Add a stricter actor roster whitelist.
5. Keep actor/trainer commands disabled until log proof is solid.

## Credit

by GLITCHED MATRIX Prototype Lab
