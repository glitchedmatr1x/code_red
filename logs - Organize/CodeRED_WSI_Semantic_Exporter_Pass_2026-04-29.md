# Code RED — WSI Semantic Exporter Pass

Date: 2026-04-29

This pass adds the first CodeX-aligned semantic WSI exporter:

```text
tools/codered_wsi_sector_export.py
```

It builds on:

```text
tools/codered_wsi_explorer.py
```

## What landed

The new exporter reads `.wsi` resources and finds `sagSectorInfo` / `Rsc6SectorInfo` blocks using the known VFT:

```text
0x01909C38
```

It exports stable top-level sector fields based on the CodeX.Games.RDR1 layout:

```text
Name
Scope
ScopedNameHash
SectorNameHash
LODFade
PropsGroup
ParentLevelIndex
CurveExtraData
MinAndBoundingRadius
MaxAndInscribedRadius
BoundMin
BoundMax
PlacedLightsGroup pointer
Props array pointer
Children array pointer
ChildGroup pointer
ChildPtrs pointer
DrawableInstances pointer
DrawableInstances2 pointer
LowLODFade
ResidentStatus
PropNames pointer/preview
AnyHighInstanceLoaded
HasVLowLODResource
District
IsTerrain
RefCount
Flags
Disabled flag guess
BoundInstances pointer
NamedNodeMap
```

## Outputs

For each WSI, the tool writes:

```text
*.sectors.csv
*.sectors.json
wsi_sector_export_master.json
```

## Usage examples

Export every WSI in a territory RPF:

```bat
py -3 tools\codered_wsi_sector_export.py path\to\dlc03x.rpf --outdir exports\dlc03x_wsi_sectors
```

Export one named WSI:

```bat
py -3 tools\codered_wsi_sector_export.py path\to\blackwater.rpf --path root/blackwater/0x3EC4B1F5/blackwater.wsi --outdir exports\blackwater_wsi_sectors
```

When debug names are unavailable, the exporter can still process resource type `134` WSI entries if `--path` is omitted.

## Local test result

Tested against the small DLC sample extracted from the uploaded territory files:

```text
dlc03x.rpf
root/dlc03x/0xA79C05A9/dlc03x.wsi
```

Result:

```text
3 sagSectorInfo blocks exported
```

Recovered fields include:

```text
root sector offset: 0x00000000
child sector offsets: 0x000001E0 and 0x000003C0
Scope strings: dlc03x
Name strings: dlc03x and dlc_placeholder03x
BoundMin: 1227.949951, 87.457474, 2807.949951
BoundMax: 1228.050049, 87.457474, 2808.050049
ResidentStatus: 85
```

This confirms that the earlier heuristic VFT scan can now be upgraded into stable semantic export for at least the fixed top-level sector structure.

## Notes

This pass is still conservative. It does not yet walk every managed array, pointer array, prop instance, drawable instance, locator, portal, or map attribute. It exposes their pointer lanes so the next pass can add array walking safely.

## Next pass targets

```text
1. Implement RSC6 virtual pointer resolver helpers.
2. Implement managed array and pointer-array readers.
3. Walk ChildGroup / Sectors arrays.
4. Walk ChildPtrs and Children arrays.
5. Export Props and DrawableInstances as separate CSVs.
6. Add coordinate-only semantic patching once target fields are confirmed through structure export.
```

Risk rule remains:

```text
WSI is the first semantic edit target. WVD/WBD stay extract/view/replace-only until their structures are ported.
```
