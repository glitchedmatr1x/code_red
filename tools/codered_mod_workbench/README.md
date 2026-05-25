# Code RED Mod Workbench

A conservative scanner/patcher for Red Dead Redemption PC modding files.

It is designed for the workflow we have been using on WSC scripts and frontend XML files:

1. inspect/decode
2. identify readable strings and safe replacement candidates
3. patch a copy, never overwrite the original
4. validate the patched copy
5. drop the output into Magic RDR / your RPF import workflow

## What it can patch

### Text/XML/SCXML/TUNE/etc.
These are patched as normal text and can use longer or shorter replacements.

Examples:

```bat
py -3 codered_mod_workbench.py replace savegame.sc.xml --find fileNoSaveEvent --replace fileSaveEvent --out patched\savegame.sc.xml
```

### WSC / RSC85 resources
The tool can decode many PC/Switch-style RSC85 WSC resources, scan readable decoded strings, replace same-size or shorter strings, repack the WSC, reopen it, and validate that the decoded data matches the patched data.

For WSC/RSC85, replacements must be the same length or shorter. Shorter replacements are padded with null bytes by default.

```bat
py -3 codered_mod_workbench.py replace medium_update_thread.wsc --find beh_grave01x --replace dlc02x --out patched\medium_update_thread.wsc
```

### Raw binary
The tool can scan and replace ASCII/UTF-16LE byte strings only when the replacement is the same size or shorter.

### ZIP files
The tool can scan a ZIP or apply a replacement across files inside a ZIP, then rebuild a new ZIP.

```bat
py -3 codered_mod_workbench.py scan netstats.zip --out reports\netstats_scan
py -3 codered_mod_workbench.py replace netstats.zip --find auth.fail_NotSignedIn --replace auth.success --out netstats_patched.zip
```

## What it does not do yet

This is **not** a script compiler and does not convert edited MagicRDR C decompile text back into WSC.

It does not safely support:

- inserting longer strings into WSC/RSC85 decoded payloads
- adding new WSC functions
- rewriting native call arguments unless you are doing exact same-width byte edits manually
- broad branch rewrites
- XSC LZX/XCompress decoding/repacking
- raw RPF injection

## Install

Run:

```bat
install_requirements.bat
```

or:

```bat
py -3 -m pip install -r requirements.txt
```

The `cryptography` package is required for encrypted RSC85 WSC files.
The `zstandard` package is required for Zstandard-compressed PC/Switch resources.

## Quick start

Scan a WSC:

```bat
py -3 codered_mod_workbench.py scan medium_update_thread.wsc --out reports\medium_update_scan
```

Get RSC85 info:

```bat
py -3 codered_mod_workbench.py info medium_update_thread.wsc
```

Patch a copy:

```bat
py -3 codered_mod_workbench.py replace medium_update_thread.wsc --find esc_villaWall04x --replace esc_villaWall04x --out build\medium_update_thread.wsc
```

Interactive mode:

```bat
py -3 codered_mod_workbench.py interactive medium_update_thread.wsc --outdir build\medium_update_patched
```

## Safe WSC rule

For WSC/RSC85, use equal-length or shorter replacements.

Good:

```text
beh_grave01x -> dlc02x
```

Risky/blocked by this tool:

```text
dlc02x -> dlc_beh_catacombs01props01x
```

The second one is longer and needs a real string/bytecode rebuild lane.

## Output files

Every patch writes:

- patched file
- `.manifest.json` next to it

The manifest records:

- input path
- output path
- find/replace text
- mode used
- replacement count
- SHA-256 before/after
- RSC85 compression/validation details when applicable

## Notes for Code RED passes

Use this as the general-purpose first pass tool. For deeper edits like changing integer operands (`1166 -> 1193`) or changing sector call marker bytes (`child -> world`), use the specialized Code RED WSC tooling or extend this tool with a reviewed recipe lane.


## Integer / enum lane

For known enum or constant values, use `find-int` and `replace-int`.

This is useful for patches like:

```text
1166 -> 1193
train car enum -> Truck01 enum
```

Find a 2-byte little-endian enum inside a WSC decoded payload:

```bat
py -3 codered_mod_workbench.py find-int long_update_thread.wsc --value 1166 --width 2 --endian little --out reports\train_1166.csv
```

Patch one reviewed decoded offset:

```bat
py -3 codered_mod_workbench.py replace-int long_update_thread.wsc --old 1166 --new 1193 --width 2 --endian little --offset 0x35D4A --out build\long_update_thread.wsc
```

Patch all matches only after reviewing the scan report:

```bat
py -3 codered_mod_workbench.py replace-int long_update_thread.wsc --old 1166 --new 1193 --width 2 --endian little --all --out build\long_update_thread.wsc
```

Use `--all` carefully. Many scripts reuse the same constants for unrelated logic.
