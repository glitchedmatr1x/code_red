# SP FreeMode Sector Graft Pass 1

No live `content.rpf`, `RDR.exe`, ASI, trainer, networking, or MP launch changes were made.

- Required base SHA1: `91304EBA24B3759AE206783EBE4CA42EA0F2A134`
- Required base found: `False`
- Base path used: `not found`
- Inventory rows: `2387`
- MP sector/action candidates: `756`
- SP counterpart candidates: `52`

## Build Status

Cloned RPF variants were not built because the exact `A_disable_update_thread_refs.rpf` base was not found locally. This is intentional; the pass does not silently substitute a different archive.

## Files Scanned

- `release64/pressstart.wsc` exists=`True` MagicRDR=`True`
- `release64/sp_idle.wsc` exists=`True` MagicRDR=`True`
- `release64/main.wsc` exists=`True` MagicRDR=`True`
- `release64/init/rdr2init.wsc` exists=`True` MagicRDR=`True`
- `multiplayer/freemode/freemode.wsc` exists=`True` MagicRDR=`True`
- `multiplayer/PR_Multiplayer.wsc` exists=`True` MagicRDR=`True`
- `multiplayer/multiplayer_system_thread.wsc` exists=`True` MagicRDR=`True`
- `multiplayer/multiplayer_update_thread.wsc` exists=`True` MagicRDR=`True`

## Next Safe Step

Place or point the tool at the exact `A_disable_update_thread_refs.rpf` base, then build A0 only first. After A0 boots, create a single SP-side sector carrier for the first recommended low-risk candidate.
