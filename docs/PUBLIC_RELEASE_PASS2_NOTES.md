# Public Release Pass 2 Notes

This package was cleaned for public release hygiene.

Removed from the public zip:

- compiled ASI/EXE/OBJ/binary build output
- build folders and backup folders
- logs and generated runtime output
- generated script pipeline manifests
- generated script workshop manifests
- generated tune syringe manifest
- private Settings files and imported filename lists
- stale private handoff notes and legacy game-root launcher folders
- hardcoded personal/local paths where found

The public repository should contain source, documentation, manifests, examples, and patch-builder logic only.
Raw game archives, extracted retail scripts, and private development-kit output belong outside the public repo.
