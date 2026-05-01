# CodeREDCompanion ASI

`CodeREDCompanion.asi` is the first safe ASI lane for Code RED.

This pass is a loader proof only. It is intentionally harmless:

- no hooks
- no pattern scanning
- no memory patches
- no script injection
- no game file writes
- no actor spawning yet

When loaded by an ASI loader, it writes a proof log beside the host executable:

```text
CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
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

It builds on a Windows runner and uploads `CodeREDCompanion.asi` as an artifact.

## First test

1. Build `CodeREDCompanion.asi`.
2. Place it next to the target game's executable only in a backed-up test folder.
3. Make sure your ASI loader is installed for that game/runtime.
4. Launch the game.
5. Check for:

```text
CodeRED_ASI_Logs/CodeREDCompanion_loader_proof.log
```

A good first proof contains:

```text
Hooks installed: false
Memory patches applied: false
Game files modified: false
Loader proof complete: true
```

## Next pass after proof

After loader proof works, the next safe additions should be:

1. Read `data/codered/companion_commands.txt`.
2. Write `CodeRED_ASI_Logs/companion_status.json`.
3. Add a no-op command parser with validation.
4. Add version/compatibility checks.
5. Only then begin controlled trainer/actor command experiments.

## Credit

by GLITCHED MATRIX Prototype Lab
