# Contributing to Code RED

Code RED is a public-safe modding research and tooling project.

## Before Opening a Pull Request

Confirm your change does not include:

- `.rpf`, `.wsc`, `.sco`, `.csc`, `.xtd`, `.wtd`, `.wtx`, `.wft`, `.wfd`, `.wvd`, `.xsf`, `.wsf`
- Compiled `.asi`, `.dll`, `.exe`, `.obj`, `.pdb`, `.lib`, `.ilk`, `.exp`
- Game assets, extracted retail scripts, third-party mods, private logs, cache folders, or build folders
- Personal absolute paths

## What To Add

Good contributions include:

- Original source code
- Public-safe documentation
- Manifests and schemas that do not redistribute game content
- Patch-builder logic requiring the user to supply their own files
- Validators and reports
- Dummy/sample inputs

## Testing

Include the command you ran and the result. If a tool writes files, test it on a disposable copy and document backup/revert behavior.
