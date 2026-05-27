# CodeRED Build Assistant — Polish Pass 2

Date: 2026-05-01
Branch: `codered-build-assistant-polish-pass2`

## Reason

The first Build Assistant pass worked, but the user still had to run too many individual command-line steps. The repo also had two cleanup issues:

- `main` missed the late actor-tool argument fix, so `--replace` only worked before a subcommand.
- A generated local report was accidentally committed under `tools/logs/`.

## Fixed

```text
tools/codered_actor_enum_tool.py
```

- `--replace` now works before or after subcommands.
- Python 3.13 `datetime.utcnow()` warning was removed by using timezone-aware UTC timestamps.
- The tool remains compatible with both classic C++ enum format and the current INI-style `enums.h` format.

## Added

```text
Run_CodeRED_AI_Menu_Setup.bat
```

This is the intended simple user entry point. It performs the setup sequence automatically:

1. Rebuild actor enum map from `enums.h` when present.
2. Validate `npc_roster.txt` against the enum map.
3. Write a resolved safe roster.
4. Apply compact AI menu layout patch if the patcher is present.
5. Open the Build Assistant GUI.

Normal user flow after pulling this pass:

```text
Double-click Run_CodeRED_AI_Menu_Setup.bat
Then press Build + Install in the Build Assistant.
```

## Removed

```text
tools/logs/CodeRED_Actor_Enum_Validation_Report.json
```

This was a generated local report and should not have been committed.

## Updated ignore rules

```text
.gitignore
```

Now ignores local CodeRED-generated reports, local AI Menu build outputs, backup files, and generated safe roster output.

## Intended result

This pass reduces the workflow from multiple manual commands to one setup launcher plus the Build Assistant GUI.
