# Contributing to Code RED

Thanks for helping improve Code RED.

## Public-Safe Contributions Only

This repository does not accept game files, extracted retail scripts, third-party mod bundles, or private build artifacts. Submit original source, documentation, schemas, examples, validators, and research summaries only.

## Pull Request Checklist

Before opening a pull request:

1. Confirm no `.rpf`, `.wsc`, `.sco`, `.csc`, `.xsc`, `.xtd`, `.wft`, audio, texture, model, or game archive files are included.
2. Confirm no `.asi`, `.dll`, `.exe`, `.obj`, `.pdb`, build folders, or logs are included unless the maintainers explicitly requested a release asset.
3. Replace local paths with placeholders such as `%RDR_GAME_DIR%`, `%CODERED_DEVKIT%`, or `%LOCAL_PATH%`.
4. Keep tool changes small and reversible.
5. Add or update documentation for any changed workflow.
6. Include validation steps for patch-builder or injector logic.

## Recommended Local Layout

Keep private material outside the repo:

```text
Code_RED_DevKit/
├─ private_input/
├─ extracted/
├─ working/
├─ output/
├─ logs/
└─ backups/
```

The public repo should contain source and docs. The private dev kit should contain test inputs and generated artifacts.
