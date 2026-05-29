# Xbox ISO / XDVDFS Tool

Code RED's Xbox ISO lane is a conservative replacement for the unstable parts of older tools such as Xbox Backup Creator.

It is designed for **user-owned local ISO images** and Xenia research. It does not include game files, keys, disc content, or third-party tools.

## What it does

- Scans an Xbox ISO for XDVDFS volume descriptors.
- Builds a file tree with sector, offset, size, and focus tags.
- Finds useful files such as `layer_0.rpf`, `layer_1.rpf`, `content.rpf`, `default.xex`, profile UI files, lobby/networking files, init files, population files, and ZombiePack-related paths.
- Extracts selected ISO files to a folder.
- Creates replacement safety plans.
- Can create a copied ISO with an **exact-size** replacement only.

## What it does not do yet

- It does not rebuild XDVDFS when file sizes change.
- It does not expand the ISO filesystem.
- It does not modify the original ISO in-place.
- It does not bypass online services, authentication systems, or ownership requirements.
- It does not edit RPF internals directly. Extract the RPF first, then use MagicRDR or Code RED RPF tools.

## Recommended workflow

```text
Xbox ISO
└─ XDVDFS file tree
   └─ layer_0.rpf / content.rpf / layer_1.rpf
      └─ Code RED layer resolver / MagicRDR / RPF tool
```

1. Index the ISO.
2. Extract `layer_0.rpf`, `layer_1.rpf`, or `content.rpf`.
3. Inspect/edit the RPF externally.
4. Compare the modified RPF size to the original.
5. If the modified RPF is exact-size, use `replace-copy-exact` on a copied ISO.
6. If the modified RPF is larger or smaller, use an extracted Xenia folder layout or a future full ISO rebuild tool.

## Commands

Index an ISO:

```bat
python tools\codered_xiso_tool.py index "D:\Games\RDR_XBOX_DISC2.iso" --out reports\xiso
```

Extract a file:

```bat
python tools\codered_xiso_tool.py extract "D:\Games\RDR_XBOX_DISC2.iso" --path "layer_0.rpf" --out extracted_iso_files
```

Create a replacement safety plan:

```bat
python tools\codered_xiso_tool.py plan-replace "D:\Games\RDR_XBOX_DISC2.iso" --path "layer_0.rpf" --replacement "D:\CodeRED\work\layer_0_modded.rpf" --out reports\xiso_replace_plan.json
```

Create a copied ISO with an exact-size replacement:

```bat
python tools\codered_xiso_tool.py replace-copy-exact "D:\Games\RDR_XBOX_DISC2.iso" --path "layer_0.rpf" --replacement "D:\CodeRED\work\layer_0_modded_same_size.rpf" --output-iso "D:\Games\RDR_XBOX_DISC2_CodeRED.iso"
```

Run the synthetic parser self-test:

```bat
python tools\codered_xiso_tool.py selftest --out reports\xiso_selftest
```

## Safety rule

The original ISO is never modified in-place. Write-back is only allowed through an output copy and only when the replacement is the same exact byte size as the original file entry.

## Pass 6: Stable RPF Replacement

Pass 6 adds stable replacement planning for RPF files inside Xbox ISOs.

Use `replace-copy-safe` instead of raw sector replacement. It allows exact-size replacements and smaller replacements padded back to the original file size. It refuses larger replacements because they require XDVDFS metadata changes or a full rebuild.

For oversized RPFs, use `export-overlay` and test through a Xenia extracted-folder layout.

## Pass 7: Direct Nested RPF Patches Inside a Copied ISO

Pass 7 adds a safer alternative to replacing a whole RPF file inside the ISO.

Instead of extracting `layer_0.rpf`, rebuilding it, and importing the entire RPF back into the ISO, Code RED can now patch a same-length byte/string change **directly inside the ISO-contained RPF entry**.

This avoids the common corruption case where a rebuilt RPF grows larger than its original XDVDFS slot.

### What this is good for

Use nested patch mode for small surgical edits such as:

```text
same-length XML route changes
same-length script path swaps
same-length string toggles
same-length byte/constant probes
research patches where the old bytes can be verified exactly
```

### What this cannot do

Nested patch mode does not rebuild RPF tables and does not import larger files.

It will not:

```text
add a new file to an RPF
grow an inner file
rewrite RPF directory tables
expand the ISO filesystem
modify the original ISO in-place
```

### Safety rules

```text
old bytes must be found inside the selected ISO entry
new bytes must be the exact same byte length
Code RED writes only to a copied output ISO
Code RED verifies the old bytes before writing
Code RED verifies the new bytes after writing
```

### Find bytes/text inside an ISO-contained RPF

```bat
python tools\codered_xiso_tool.py nested-find "D:\Games\RDR_DISC2.iso" ^
  --path "layer_0.rpf" ^
  --needle "NetMachine.Authenticate(arg1)" ^
  --out reports\nested_find.json
```

### Plan a same-size nested patch

```bat
python tools\codered_xiso_tool.py nested-plan-patch "D:\Games\RDR_DISC2.iso" ^
  --path "layer_0.rpf" ^
  --old "NetMachine.Authenticate(arg1)" ^
  --new "NetMachine.TriggerLoad(arg1)" ^
  --out reports\nested_patch_plan.json
```

The `--old` and `--new` values must have the same byte length. If they do not, Code RED refuses the patch.

### Apply a same-size nested patch to a copied ISO

```bat
python tools\codered_xiso_tool.py nested-patch-copy "D:\Games\RDR_DISC2.iso" ^
  --path "layer_0.rpf" ^
  --old "OLD_TEXT_SAME_LENGTH" ^
  --new "NEW_TEXT_SAME_LENGTH" ^
  --output-iso "D:\Games\RDR_DISC2_CodeRED.iso" ^
  --report reports\nested_patch_copy_report.json
```

### Hex and exact-file byte mode

For non-text patches, use hex or exact byte files:

```bat
python tools\codered_xiso_tool.py nested-patch-copy "D:\Games\RDR_DISC2.iso" ^
  --path "layer_0.rpf" ^
  --old-hex "12 34 56 78" ^
  --new-hex "12 34 9A BC" ^
  --output-iso "D:\Games\RDR_DISC2_CodeRED.iso"
```

```bat
python tools\codered_xiso_tool.py nested-patch-copy "D:\Games\RDR_DISC2.iso" ^
  --path "layer_0.rpf" ^
  --old-file old_bytes.bin ^
  --new-file new_bytes.bin ^
  --output-iso "D:\Games\RDR_DISC2_CodeRED.iso"
```

### When to use this instead of whole-RPF replacement

Use nested patch mode first when the change is a same-length string/byte edit. It keeps the RPF and ISO sizes stable.

Use whole-RPF replacement only when you have rebuilt the RPF and the replacement is exact-size or smaller/padded. If the replacement is larger, use an extracted Xenia overlay or a future full rebuild/relayout tool.
