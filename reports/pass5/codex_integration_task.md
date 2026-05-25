# Codex Integration Task — Code RED Remote Menu Pass 5

## Goal

Integrate the Code RED Remote Menu scaffold into the local Windows ASI/ScriptHook project, keeping Soul Stealer, teleport, remote puppet/blip, and sector toggle in one trainer menu.

## Current package contains

- Soul Stealer core from prior passes
- TeleportManager
- RemotePuppetController and RemotePuppetBlip
- New CodeRedRemoteMenu menu model
- New SectorCatalog and SectorPatchQueue
- New territory sector catalog builder
- Bundled Workbench v0.3 sector toggle tool

## Required local wiring

1. Wire `INativeBridge` to real RDR PC natives.
2. Wire `IInputBridge` to real key polling.
3. Add menu draw/input handling:
   - open/close Code RED Remote Menu
   - up/down/select/back
   - render `RemoteMenuView` lines
4. Wire sector catalog loading:
   - parse `config/sector_catalog.json` or generate it with `tools/territory_sector_catalog_builder.py`
   - load into `SectorCatalog`
5. Wire sector patch queue export:
   - save `SectorPatchQueue::exportJson()` to `logs/sector_patch_queue.json`
   - optionally save `exportWorkbenchCommands(...)` as a `.bat` or `.ps1`
6. Do not apply sector patches live in-game yet.

## Test order

1. Compile ASI with menu classes only.
2. Open menu in game.
3. Verify Soul Stealer page still shows/arms.
4. Verify Teleport page still saves/loads slot.
5. Verify Remote Puppet page does not crash even before blip natives are wired.
6. Verify Sector Toggle page loads sample catalog and queues a request.
7. Export queue and apply it to a copied `medium_update_thread.wsc` with Workbench v0.3.

## Non-goals

- No live `content.rpf` edits.
- No WSC patching from ASI at runtime.
- No full trainer feature port yet.
- No online/GameSpy/MP backend interaction.

## Future pass

Once the menu compiles and opens, add feature pages one at a time:

- Ped spawner
- Vehicle spawner
- Object spawner
- Animation player
- World/game options
- Inventory options
