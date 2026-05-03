# Code RED Scripting Guide

This file is the quick entry point for Code RED script work.

The goal is to keep script creation clear, testable, and separated from archive/resource tooling so we do not repeat the SC-CL/full-menu confusion.

## Start here

Use this order when adding script features:

1. Read `docs/code-red-script-workflow/README.md`.
2. Pick the correct lane from `docs/code-red-script-workflow/LANES.md`.
3. Add or update native/function evidence in `docs/code-red-script-workflow/NATIVE_VERIFICATION_TEMPLATE.csv`.
4. Create a tiny proof before editing a full menu.
5. Record the result in `logs/`.

## Current rule

Do not guess function signatures.

A script command is allowed only when at least one of these is true:

- The native or wrapper exists in real headers.
- The exact signature is verified from a known working wrapper/API.
- A tiny compile/runtime proof has already passed.
- The feature is explicitly marked as research-only and cannot reach the production menu.

## Main lanes

- Trainer / ScriptHook / RedHook lane: main menu work, actor control, teleport, weather, spawn, animation, and live debug commands.
- SC-CL lane: tiny internal script experiments only. Do not rebuild the full menu here.
- RPF/resource lane: archive inspection, tune edits, WSI/WGD/resource correlation, and controlled copied-archive patch tests.
- Research lane: notes, imported clues, reverse-engineering observations, and feature maps. Research does not become code until verified.

## Safe next target

Actor travel should be built in the trainer lane:

```text
select actor -> choose destination -> send actor / teleport actor / guard point -> log result
```

Start with coordinate display and saved locations before adding pathing.
