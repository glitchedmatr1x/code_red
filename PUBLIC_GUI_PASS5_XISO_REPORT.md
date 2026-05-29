# Code RED Public GUI Pass 5 - Xbox ISO / XDVDFS Tool

This pass adds a public-safe Xbox ISO lane to Code RED.

## Added

- `tools/codered_xiso_tool.py`
- GUI tab: `ISO/XDVDFS`
- `docs/XISO_XDVDFS_TOOL.md`
- `Run_XISO_Tool.bat`

## Purpose

Older tools such as Xbox Backup Creator can extract and replace files inside Xbox ISO images, but they are unstable and opaque. Code RED now provides a conservative copy-first alternative:

- index the XDVDFS file tree,
- extract RPF containers from an ISO,
- make replacement safety plans,
- only write an exact-size replacement into a copied ISO.

## Public-safety notes

The package does not contain ISO files, RPF files, XEX files, extracted game scripts, or private disc content.

## Current limitation

Changed-size RPF replacement still requires either an extracted Xenia folder layout or a future full XDVDFS rebuild pass.
