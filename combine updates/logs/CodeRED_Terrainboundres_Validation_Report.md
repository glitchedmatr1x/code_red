# Code RED Terrainboundres Validation Report

Generated: `2026-05-03T07:54:37Z`
Result: **PASS**
Archive: `/mnt/data/codered_work/imports/terrainboundres.rpf`

## Counts

- Entries: 5381
- Files: 5378
- WTB tiles: 5376
- TXT sidecars: 2
- Territories: 1
- Decoded samples: 5
- Decoded OK: 5
- Decoded failed: 0

## Grid extent guess

- min_x: 1024
- max_x: 7616
- min_y: 6656
- max_y: 11712
- cell_size: 64

## Errors

- none

## Notes

- Validation is read-only and does not patch source archives.
- Copied-archive patching remains available through codered_terrainboundres_tool.py patch-folder and patch-wtb-bytes.
- Semantic WTB editing is still conservative; this proof validates inventory/decode readiness, not arbitrary terrain mutation.

## Inventory summary

# Code RED terrainboundres Inventory

Archive: `/mnt/data/codered_work/imports/terrainboundres.rpf`
Entries: 5381  Files: 5378  WTB tiles: 5376  TXT sidecars: 2
Grid extent guess: x=1024..7616 y=6656..11712 cell=64

## Territories

- `territory_swall_noid`: 5376 WTB tiles

## Decoded Sample Tiles

- `root/terrainboundres/territory_swall_noid/08c022c0_bnd.wtb` index=3 stored=28177 decoded=45056 decode=ok
- `root/terrainboundres/territory_swall_noid/108029c0_bnd.wtb` index=4 stored=49821 decoded=77824 decode=ok
- `root/terrainboundres/territory_swall_noid/13402b40_bnd.wtb` index=5 stored=74787 decoded=118784 decode=ok
- `root/terrainboundres/territory_swall_noid/12402b40_bnd.wtb` index=6 stored=44126 decoded=69632 decode=ok
- `root/terrainboundres/territory_swall_noid/1d801c00_bnd.wtb` index=7 stored=1115 decoded=16384 decode=ok

## Edit Safety

- Source archives are never modified by this tool.
- Use `export` to create a patchable extracted folder.
- Use `patch-folder` to apply edited `.wtb` resources to a copied archive and verify by re-reading.
- Decoded payload size must stay equal to the original decoded WTB payload unless the RPF resource flag updater is extended for changed resource page totals.
