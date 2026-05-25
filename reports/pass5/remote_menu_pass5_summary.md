# Code RED Remote Menu Pass 5 Summary

## Scope

This pass turns the trainer scaffold into **Code RED Remote Menu** and adds a menu-facing sector toggle lane beside the existing Soul Stealer, teleport, and remote puppet/blip systems.

No live `content.rpf` or game files are edited by this package. Sector toggles are queued as reviewable patch requests and applied later by Code RED Mod Workbench v0.3 to copied WSC files.

## New C++ modules

- `CodeRedRemoteMenu.h/.cpp`
  - top-level menu model
  - pages: Soul Stealer, Teleport, Remote Puppet, Sector Toggle, Debug
  - can render menu rows for an ASI overlay or FUI-style trainer UI

- `SectorCatalog.h/.cpp`
  - holds parent/world/child sector entries
  - supports parent list, child list, and name lookups

- `SectorPatchQueue.h/.cpp`
  - queues enable/disable/child-to-world/world-to-child/name-replacement actions
  - exports reviewable JSON
  - exports Workbench command templates

## New tools/config

- `tools/territory_sector_catalog_builder.py`
  - scans territory_swall zips/folders and Workbench sector inventory CSVs
  - outputs `sector_catalog.json`, `sector_catalog.csv`, and a report

- `tools/workbench_v0_3_sector_toggle/`
  - bundled Code RED Mod Workbench v0.3 for offline WSC sector patching

- `config/CodeRedRemoteMenu.json`
  - menu sections and sector toggle behavior

- `config/sector_catalog.sample.json`
  - sample catalog from `territory_swall dlc.zip`, `redemption part1.zip`, and sample `medium_update_thread.wsc` sector scan

- `presets/sector_toggle_presets.json`
  - Morning Star / Escalera enable preset
  - DLC grave replacement preset
  - MP/DLC scan-only preset

## Validation

Built and ran in the sandbox:

```text
code_red_remote_menu_test: passed
soul_stealer_pass4_test: passed
```

Sector catalog builder sample:

```text
Sectors: 167
Parents: 13
```

## Intended runtime behavior

The in-game trainer menu should eventually show:

```text
Code RED Remote Menu
- Soul Stealer
- Teleport Options
- Remote Puppet / Ghost Blip
- World / Child Sector Toggle
- Debug
```

Sector Toggle menu flow:

```text
Sector Toggle
-> choose parent territory/RPF
-> choose child/world sector
-> queue Enable / Disable / Convert to World / Convert to Child
-> export patch queue JSON
-> apply to copied WSC with Workbench v0.3 outside the running game
```

## Important safety rule

Do not patch live RPF/WSC while the game is running. The menu should queue sector patch requests. Workbench applies them to copied WSC files and validates decode/repack before import.
