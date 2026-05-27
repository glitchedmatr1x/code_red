# AGENTS.md

Rules for AI agents and automation working on Code RED.

## Repository Boundary

Code RED public repo material must stay source-based and public-safe. The private dev kit may contain raw game files, extracted scripts, generated logs, and patch experiments, but those files do not belong in this repository.

## Never Commit

- Full RPF archives or other game archives
- Extracted retail WSC/SCO/CSC/XSC scripts
- Rockstar-owned models, textures, audio, video, string tables, or assets
- Third-party mods without explicit permission and license notes
- Compiled ASI/DLL/EXE/OBJ/PDB files in the default branch
- Private logs, machine paths, cache folders, build folders, or giant zip dumps
- Files from `private_input/`, `extracted/`, `working/`, `output/`, or `logs/`

## Preferred Contributions

- Original source code
- Patch-builder logic
- Validators and reports that do not include raw game data
- Public-safe manifests and schemas
- Documentation and clean-room research summaries
- Reversible workflows with backup/restore notes

## WSC / Script Research Rule

Do not commit extracted retail script files. Public documentation may describe behavior, paths, enum observations, and clean-room pseudocode, but should not include raw decompiled game script payloads.

## Validation Expectations

Before committing, run a public-safety scan for blocked extensions and local paths. If unsure whether a file is safe, keep it out of the repo and document how users can generate it locally from their own files.
