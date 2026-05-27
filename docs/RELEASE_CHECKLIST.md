# Release Checklist

Use this checklist before publishing a Code RED zip or GitHub Release.

## Blocked File Scan

Confirm the package contains none of these:

```text
*.rpf
*.wsc
*.sco
*.csc
*.xsc
*.xtd
*.wtd
*.wft
*.asi
*.dll
*.exe
*.obj
*.pdb
*.log
```

## Directory Scan

Remove these if present:

```text
logs/
build/
dist/
CodeRED_Backups/
private_input/
extracted/
working/
output/
imports/
game/
```

## Content Scan

Search for local paths:

```text
D:\
C:\Users\
OneDrive\Desktop
AppData\Roaming
```

Replace them with placeholders.

## Documentation

Confirm these exist:

```text
README.md
AGENTS.md
CONTRIBUTING.md
docs/QUICK_START.md
docs/SAFETY_AND_LEGAL.md
docs/RPF_COMPARE_AND_INJECT.md
docs/WSC_RESEARCH_WORKFLOW.md
docs/ASI_DIAGNOSTICS.md
docs/RELEASE_CHECKLIST.md
docs/DOWNLOADS.md
```
