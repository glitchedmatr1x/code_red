# AGENTS.md

Rules for AI agents and automation working on Code RED.

## Hard Rules

- Do not commit game files.
- Do not commit full RPF archives.
- Do not commit extracted retail WSC, SCO, or CSC scripts.
- Do not commit Rockstar-owned models, textures, audio, maps, or other assets.
- Do not commit third-party mods unless permission and licensing are documented.
- Do not commit local logs, build folders, backup folders, caches, or private scan output.
- Do not commit compiled ASI, DLL, EXE, OBJ, PDB, or LIB files to the source tree.

## Preferred Public Work

Commit public-safe source, docs, manifests, schemas, validators, and patch-builder logic.
Use examples with dummy data or user-supplied local paths only.
Keep changes small, reversible, and documented.

## WSC / RPF Research

Document research as notes, pseudocode, reports, or tool logic.
Do not include extracted retail scripts or raw game archive contents.
When adding a patch workflow, include validation notes and backup/revert guidance.

## Path Hygiene

Use placeholders such as `%RDR_GAME_DIR%`, `%CODERED_DEVKIT%`, and `%USERPROFILE%`.
Do not hardcode personal paths.
