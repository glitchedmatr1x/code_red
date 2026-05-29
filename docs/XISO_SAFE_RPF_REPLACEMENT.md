# Safe RPF Replacement in Xbox ISO / XDVDFS Images

Code RED's ISO replacement workflow is intentionally conservative because Xbox disc images store each file's size and sector location in the XDVDFS directory tree.

If a modified RPF is written over the original ISO sector range while the modified file is larger than the original directory entry, the ISO can become corrupted or the game can read a truncated file.

## Safe Rules

Use these rules for Xbox/Xenia RPF replacement:

1. Never modify the original ISO in place.
2. Always write to a copied output ISO.
3. Exact-size replacement is safest.
4. Smaller replacement is allowed only when padded back to the original file size.
5. Larger replacement is refused for ISO write-back.
6. Larger replacement should use a Xenia extracted-folder overlay or a future full XDVDFS rebuild/relayout pass.

## Why Larger RPFs Break

An ISO file entry has metadata like:

```text
path: layer_0.rpf
sector: 123456
size: 987654321
allocated sector span: rounded up to 2048-byte sectors
```

If `layer_0_modded.rpf` is larger than the original `size`, simply writing it into the old sector range is not enough. The XDVDFS directory entry still advertises the old size. The game or emulator may only read the old length, or the write can overlap later files.

## Commands

Index an ISO:

```bat
python tools\codered_xiso_tool.py index "D:\Games\RDR_DISC2.iso" --out reports\xiso
```

Extract a target RPF:

```bat
python tools\codered_xiso_tool.py extract "D:\Games\RDR_DISC2.iso" --path "layer_0.rpf" --out extracted_iso_files
```

Plan a replacement:

```bat
python tools\codered_xiso_tool.py plan-replace "D:\Games\RDR_DISC2.iso" --path "layer_0.rpf" --replacement "D:\CodeRED\work\layer_0_modded.rpf" --out reports\xiso_replace_plan.json
```

Stage an exact-size padded replacement if the edited RPF is smaller than the original:

```bat
python tools\codered_xiso_tool.py prepare-exact "D:\Games\RDR_DISC2.iso" --path "layer_0.rpf" --replacement "D:\CodeRED\work\layer_0_modded.rpf" --out "D:\CodeRED\staged\layer_0.rpf.exactsize"
```

Create a copied output ISO with exact or smaller-padded replacement:

```bat
python tools\codered_xiso_tool.py replace-copy-safe "D:\Games\RDR_DISC2.iso" --path "layer_0.rpf" --replacement "D:\CodeRED\work\layer_0_modded.rpf" --output-iso "D:\Games\RDR_DISC2_CodeRED.iso"
```

If the modified RPF is larger, export an overlay instead:

```bat
python tools\codered_xiso_tool.py export-overlay "D:\Games\RDR_DISC2.iso" --path "layer_0.rpf" --replacement "D:\CodeRED\work\layer_0_modded.rpf" --out "D:\CodeRED\xenia_overlay"
```

## GUI Workflow

Open the `ISO/XDVDFS` tab:

1. Open ISO.
2. Index ISO.
3. Select `layer_0.rpf`, `layer_1.rpf`, or another RPF.
4. Use `Plan RPF Replace` to see whether the modified file is safe.
5. Use `Stage Exact/Padded` if the modified file is same-size or smaller.
6. Use `Export Overlay` if the modified file is larger.

The GUI does not write modified ISOs directly. ISO copy-write remains a CLI action so it cannot happen by accident.

## Current Limitation

Code RED does not yet rebuild XDVDFS directory trees for larger replacements. That is a future pass. Until then, larger RPFs should be handled through extracted Xenia layouts or a full disc rebuild toolchain.
