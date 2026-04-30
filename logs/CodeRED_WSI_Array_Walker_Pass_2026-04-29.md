# Code RED — WSI Array Walker Pass

Date: 2026-04-29

This pass adds:

```text
tools/codered_wsi_array_export.py
```

It builds on the earlier WSI tools:

```text
tools/codered_wsi_explorer.py
tools/codered_wsi_sector_export.py
```

## Purpose

The previous semantic exporter exposed top-level `sagSectorInfo` fields and pointer lanes. This pass starts walking those pointer lanes into separate export tables.

## What the array walker exports

For each WSI, it writes:

```text
*.sectors.csv
*.child_groups.csv
*.child_group_items.csv
*.pointer_items.csv
*.drawable_instances.csv
*.arrays.json
wsi_array_export_master.json
```

## Exported lanes

Top-level sector rows still include:

```text
Name
Scope
ScopedNameHash
SectorNameHash
BoundMin
BoundMax
Flags
ResidentStatus
District
RefCount
array pointers/counts/capacities
```

New child group export:

```text
ChildGroup offset
ChildGroup ScopeName
Sectors pointer array
SectorsParents pointer array
SectorsIndices array
```

New child group item export:

```text
child_group_sector pointer rows
child_group_parent pointer rows
child_group_index rows
```

New pointer item export:

```text
ChildPtrs array entries
```

New drawable-instance export:

```text
sector offset
array name
instance index
instance offset
VFT
last-known position/flags guess
node raw value
matrix guess
bbox min/max guess
instance hash guess
name pointer/name guess
room pointer guess
next drawable pointer guess
```

## Local test result

Tested locally against the small DLC WSI sample:

```text
dlc03x.rpf
root/dlc03x/0xA79C05A9/dlc03x.wsi
```

Result:

```text
sector_count: 3
child_group_count: 1
child_group_item_count: 6
pointer_item_count: 2
drawable_instance_count: 1
```

This confirms the exporter can now walk beyond sector headers into child sector hierarchy and first drawable-instance table lanes.

## Important caution

The drawable instance reader is still conservative and labels several fields as guesses. The offsets are aligned with the CodeX `Rsc6DrawableInstanceBase` layout, but this pass does not yet fully resolve room, attribute, prop, portal, locator, or bound-instance structures.

## Next pass targets

```text
1. Add managed-array readers for props and locators.
2. Add Rsc6SectorChild reader.
3. Add Rsc6DrawableInstance name/hash resolution against WVD pieces.
4. Add semantic coordinate patching only after field offsets are verified on more than one WSI.
5. Run this on blackwater.wsi and inspect high-count outputs for stable patterns.
```

Risk rule remains:

```text
WSI is the first semantic edit target. WVD/WBD remain extract/view/replace-only until their structures are ported.
```
