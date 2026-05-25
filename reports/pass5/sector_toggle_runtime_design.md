# Sector Toggle Runtime Design

## Why sector toggles belong in the trainer menu

The user wants a central **Code RED Remote Menu** that exposes trainer features and world restoration tools. World/child sector toggles are not live native toggles yet; they are WSC patch operations. The menu therefore acts as a planner/queue, while Code RED Mod Workbench performs the actual validated patching outside the game.

## Territory swall mapping

Working model:

- RPF names under `territory_swall` are parent/world groups.
- Child sectors are inside those parent RPFs or appear in WSC update-thread sector calls.
- `medium_update_thread.wsc` / `long_update_thread.wsc` hold enable/disable sector calls.

The builder can merge:

- `territory_swall dlc.zip` parent RPF names, such as `dlc02x.rpf`.
- `redemption part1.zip` parent RPF names, such as `blackwater.rpf`.
- Workbench `sector_inventory.csv` from WSC scans.

## Safe patch method

The actual patch still uses the proven WSC lane:

```text
decode WSC/RSC85
find sector call markers
patch same-width marker/name fields
repack
reopen/decode validate
import copied WSC through Magic RDR/RPF workflow
```

## Menu actions

- Enable selected sector
- Disable selected sector
- Convert selected child sector to world sector
- Convert selected world sector to child sector
- Replace sector name where same-size/shorter null-padded is safe

## Risk control

The menu should display and queue actions, not blindly patch files. This avoids crashes from live content edits and preserves reviewable manifests.
