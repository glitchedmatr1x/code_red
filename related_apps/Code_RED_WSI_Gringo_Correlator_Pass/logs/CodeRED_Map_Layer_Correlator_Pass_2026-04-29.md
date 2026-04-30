# Code RED — Map Layer Correlator Pass

Date: 2026-04-29

This pass documents the already-added map-layer inventory/correlation tool:

```text
tools/codered_map_layer_correlator.py
```

## Purpose

The tool indexes territory, terrain bounds, terrain LOD, and map resource RPFs into CSV/JSON tables so Code RED can stop guessing which archive owns a world layer.

It is a read-only research/export pass. It does not patch map, WSI, WVD, WBD, WTB, WTL, WTD, or WTX data.

## Inputs

The tool accepts one or more RPF files or folders containing RPF files:

```text
python tools/codered_map_layer_correlator.py terrainboundres.rpf terrainlodres.rpf mapres.rpf territory_swall.rpf
```

Folders are searched recursively for `*.rpf` files.

## Outputs

Default output folder:

```text
exports/map_layer_correlation
```

Generated tables:

```text
archive_layers.csv
layer_summary.csv
all_resource_entries.csv
territory_assets_wsi_wvd_wbd.csv
terrainbound_tiles_wtb.csv
terrainlod_tiles_wtl_wvd.csv
map_texture_resources.csv
map_layer_correlation_master.json
```

## What it correlates

Layer classification:

```text
.wsi  -> sector_info_wsi
.wvd  -> drawable_wvd
.wbd  -> bounds_wbd
.wtb  -> terrain_bounds_wtb
.wtl  -> terrain_lod_world_wtl
.wtd  -> texture_dictionary_wtd
.wtx  -> texture_wtx
.xlist -> texture_xlist
.dlc  -> dlc_bounding_box
```

Terrainbound tile decoding:

```text
00000000_bnd.wtb-style names are split into signed/unsigned grid X/Y candidates.
Default bounds grid cell size guess: 0x40.
```

Terrain LOD decoding:

```text
resource_<lod>/tile_<x>_<y>.wvd paths are exported as visual terrain tile rows.
.wtl files are exported as terrain_lod_world rows.
```

## Why this matters

This gives the next passes a stable map inventory before touching placement or terrain data. It helps answer:

```text
- Which archive contains the Blackwater WSI/WVD/WBD layer?
- Which terrainbound cells correspond to a coordinate region?
- Which terrain LOD WVD tiles are visual geometry rather than props?
- Which map texture dictionaries belong to mapres-style archives?
```

## Connection to current vehicle research

The gringo vehicle path still belongs primarily to WSI/WGD/WSC research, but map-layer correlation helps choose a safe visible Blackwater test area and avoid patching the wrong archive layer.

## Risk rule

Continue using copied archives only. Do not bulk patch WSI, WGD, WVD, WBD, WTB, or WTL. Use proof JSON and reopen verification for any later write pass.
