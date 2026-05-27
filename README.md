# Code RED

**Code RED** is a public research and tooling project for Red Dead Redemption PC modding workflows.

The goal is to provide clean, documented tools and research notes for comparing, exporting, validating, and building patch-style mod work without distributing game files, extracted retail assets, or third-party mods.

Code RED is also used privately as a larger development kit for experiments, but this public repository only contains material that is safe to share.

---

## What Code RED Is

Code RED is focused on:

* RPF compare/export workflows
* Patch-builder and injection helper tooling
* WSC/script research notes
* Vehicle and tuning research
* Camp persistence research
* Actor, horse, and enum mapping research
* ASI/runtime diagnostic tooling
* Public-safe manifests, reports, and documentation
* Reproducible workflows for users working from their own legally owned game files

This repository is intended to be useful to modders, researchers, and tool builders.

---

## What Code RED Is Not

Code RED does **not** ship Red Dead Redemption game files.

This repository should not contain:

* Full `.rpf` archives
* Extracted retail `.wsc`, `.sco`, `.csc`, model, texture, audio, or asset files
* Rockstar-owned game content
* Third-party mods
* Private test archives
* Large zip dumps
* Personal logs or machine-specific build folders
* Compiled binaries unless they are attached to a GitHub Release and clearly marked

Users are expected to supply their own legally owned game files outside of the repository.

---

## Public Repo vs Private Dev Kit

Code RED has two lanes:

### Public Code RED Repo

This repository contains public-safe material:

```text
README.md
docs/
source/
tools/
manifests/
reports/
examples/
AGENTS.md
CONTRIBUTING.md
.gitignore
```

The public repo should stay clean, searchable, and easy to understand.

### Private Code RED Dev Kit

Private/local work may include:

```text
raw RPF archives
extracted scripts
WSC/SCO/CSC experiments
MagicRDR working folders
drop-in patch packages
vehicle test archives
zombie-mode graft tests
camp persistence tests
runtime logs
binary validators
compare outputs
```

Those files are for local research only and should not be committed to the public repository.

---

## Recommended Repository Layout

```text
Code_RED/
├─ README.md
├─ AGENTS.md
├─ CONTRIBUTING.md
├─ LICENSE
├─ .gitignore
├─ docs/
│  ├─ QUICK_START.md
│  ├─ SAFETY_AND_LEGAL.md
│  ├─ RPF_COMPARE_AND_INJECT.md
│  ├─ WSC_RESEARCH_WORKFLOW.md
│  ├─ ASI_DIAGNOSTICS.md
│  ├─ RELEASE_CHECKLIST.md
│  └─ DOWNLOADS.md
├─ source/
│  ├─ asi/
│  ├─ cpp/
│  └─ python/
├─ tools/
│  ├─ rpf_compare/
│  ├─ patch_builder/
│  ├─ manifest_tools/
│  └─ validators/
├─ manifests/
│  ├─ examples/
│  └─ schemas/
├─ reports/
│  └─ public_summaries/
└─ examples/
   └─ safe_dummy_inputs/
```

---

## Quick Start

### 1. Clone the repository

```bat
git clone https://github.com/GLITCHEDMATR1X/Code_RED.git
cd Code_RED
```

### 2. Create a private local workspace

Do not put game files inside the repo.

Recommended local structure:

```text
Code_RED_DevKit/
├─ private_input/
│  └─ put_your_own_game_files_here/
├─ extracted/
├─ working/
├─ output/
├─ logs/
└─ backups/
```

### 3. Install tool requirements

Python tools should be run from a normal local Python environment.

Example:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If a tool has its own requirements file, use the requirements file inside that tool folder.

### 4. Compare clean and modified files

The preferred workflow is:

```text
clean input archive/file
modified archive/file
compare output
manifest
patch package
validation report
```

Tools should generate reports and patch-style outputs rather than redistributing full game archives.

### 5. Review output before sharing

Before publishing anything, confirm that the output does not contain:

```text
.rpf
.wsc
.sco
.csc
.xtd
.wft
audio banks
textures
models
raw game scripts
third-party mod files
```

Only share public-safe tool output, reports, manifests, and instructions.

---

## RPF Compare and Patch Workflow

The intended workflow is:

1. Keep a clean copy of the user’s own original file outside the repo.
2. Keep the modified copy outside the repo.
3. Run a compare/export tool.
4. Generate a manifest of changed paths.
5. Export only the minimum changed data required for a patch workflow.
6. Validate that the patch can be reapplied.
7. Generate a report.
8. Share only the tool, manifest, public notes, and safe patch logic.

A good patch workflow should be reversible and should create backups before writing changes.

---

## WSC Research Workflow

Code RED may document WSC and script research, but the public repo should not include extracted retail scripts.

Public-safe WSC research can include:

* Function names discovered through public notes
* High-level behavior descriptions
* Pseudocode written from scratch
* String/path references when necessary for research context
* Enum tables created by the project
* Clean-room helper tools
* Validation reports

Do not commit extracted retail script files.

---

## Current Research Lanes

Code RED currently tracks several research lanes.

### Vehicle and Tune Research

Research includes vehicle enum mapping, tuning experiments, wagon/car behavior differences, and patch workflows for vehicle-related files.

Public-safe outputs should focus on:

* Enum notes
* Tuning observations
* Tooling
* Patch workflow documentation
* Comparison reports

### Camp Persistence Research

Research includes campsite creation/removal behavior and patch strategies for preserving camps or changing camp behavior.

Public-safe outputs should focus on:

* State-machine notes
* Patch strategy notes
* Reversible workflow documentation
* Validation reports

### Zombie Mode Research

Research includes identifying which systems can be grafted safely into normal gameplay without replacing the normal boot/save/world owner.

Current strategy:

```text
normal main = keep as chassis
main_z = research donor only
init files = possible bridge
player/update/pause_z = runtime behavior candidates
```

Public-safe outputs should describe the research and workflow without distributing extracted retail scripts.

### Actor and Horse Enum Research

Research includes actor enum mapping, horse/deed testing, zombie animal ranges, and runtime spawn behavior.

Public-safe outputs may include:

* Project-generated enum maps
* CSV summaries
* Test observations
* Tooling to load user-provided maps locally

### ASI and Runtime Diagnostics

Code RED may include ASI/plugin source or diagnostics, as long as the source is original and does not include third-party code without permission.

Public-safe outputs may include:

* Original C++ source
* Build instructions
* Diagnostic logging tools
* Runtime test notes
* Config examples

---

## Release Assets

Large downloadable bundles should be attached to GitHub Releases, not committed to the main branch.

Recommended public release asset names:

```text
CodeRED-v0.1.x-tools.zip
CodeRED-v0.1.x-research.zip
CodeRED-v0.1.x-reports.zip
CodeRED-v0.1.x-build-public.zip
```

Release assets should still be checked before upload. Do not attach raw game archives or extracted game assets.

---

## Safety and Legal Notes

Code RED is a research and tooling project.

This project does not provide game files.
This project does not provide cracked files.
This project does not bypass ownership requirements.
This project does not include Rockstar-owned assets.
This project does not include third-party mods unless permission is clearly documented.

Users are responsible for owning the game and following applicable laws, licenses, and platform rules.

---

## Contributor Rules

Before opening a pull request:

1. Do not commit game files.
2. Do not commit extracted retail scripts.
3. Do not commit full RPF archives.
4. Do not commit third-party mod files.
5. Do not commit large private zip archives.
6. Keep tools source-based when possible.
7. Keep outputs reproducible.
8. Add a clear report or manifest for research changes.
9. Prefer small, reversible changes.
10. Include validation steps when a tool changes patch behavior.

---

## AI / Agent Rules

AI coding agents working on this repository should follow these rules:

```text
Do not commit game files.
Do not commit full RPF archives.
Do not commit extracted retail WSC/SCO/CSC files.
Do not commit third-party mods.
Do not commit private logs, temp folders, caches, or build dumps.
Prefer manifests, reports, patch notes, validators, and patch-builder logic.
Keep changes small and reversible.
Preserve backups.
For WSC patch research, verify by re-decoding or re-validating when possible.
If unsure whether a file is public-safe, do not commit it.
```

---

## Suggested Documentation To Add

Planned documentation:

```text
docs/QUICK_START.md
docs/SAFETY_AND_LEGAL.md
docs/RPF_COMPARE_AND_INJECT.md
docs/WSC_RESEARCH_WORKFLOW.md
docs/ASI_DIAGNOSTICS.md
docs/RELEASE_CHECKLIST.md
docs/DOWNLOADS.md
AGENTS.md
CONTRIBUTING.md
```

---

## Project Status

Code RED is experimental.

Some tools may be prototypes.
Some research notes may change as new tests are completed.
Patch workflows should always be tested on backups first.

The priority is to make Red Dead Redemption PC research safer, cleaner, more reproducible, and easier for other people to understand.

---

## Disclaimer

Code RED is an independent research/tooling project and is not affiliated with Rockstar Games, Take-Two Interactive, or any official Red Dead Redemption project.

All trademarks and game content belong to their respective owners.

This repository is intended for educational, archival, research, and modding-tool development purposes only.


