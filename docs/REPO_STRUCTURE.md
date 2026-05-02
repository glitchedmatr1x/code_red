# Code RED Repository Structure

This document defines the intended layout so Code RED does not keep growing as a loose collection of one-off buttons, pass folders, logs, temp files, and duplicate apps.

## Active user entry points

Keep these at the repo root because they are meant to be double-clicked:

```text
Run_CodeRED_AI_Menu_Setup.bat
Run_CodeRED_Build_Assistant.bat
```

Do not add a new root launcher for every new button. Add new actions inside the existing Build Assistant or setup flow unless the launcher is a truly separate product.

## Active runtime/build code

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/
```

Active ScriptHookRDR AI Menu source and config live here.

```text
tools/codered_build_assistant.py
tools/codered_actor_enum_tool.py
tools/codered_ai_menu_layout_patch.py
```

Active automation tools live here.

```text
data/codered/
```

Runtime data copied to the game folder lives here. Generated local reports and temporary proof output should not be committed.

## Research and older passes

Older experimental apps, faction-war pass folders, RPF research, and prototype lanes currently live under:

```text
related_apps/
```

For now, do not delete these blindly. Most of them are research artifacts. Future cleanup should move inactive pass folders into:

```text
archive/related_apps/
archive/research_logs/
```

only after an active/inactive manifest confirms they are not part of the current ASI/Menu workflow.

## Logs

Use `logs/` for curated project notes and pass reports only.

Do commit:

```text
logs/CodeRED_*_Pass*.md
logs/CodeRED_LOG_INDEX.md
logs/CodeRED_RESEARCH_MANIFEST.csv
logs/README.md
```

Do not commit generated local runtime files:

```text
logs/CodeRED_Actor_Enum_Validation_Report.json
logs/CodeRED_Build_Assistant_last.log
logs/CodeRED_Build_Assistant_last_report.json
logs/external_patch_status.json
```

## Build outputs and backups

Do not commit:

```text
related_apps/Code_RED_ScriptHookRDR_AI_Menu/build/
*.bak_*
CodeRED_Backups/
__pycache__/
```

## Rule for new work

Before adding a new file, choose one of these buckets:

```text
active runtime source
active automation tool
runtime data
curated log/report
archived research
local/generated output
```

If it is generated output, it belongs in `.gitignore`, not in Git.
