# Code RED Active Route

Last active consolidation: 2026-05-08

## Active Target

Find the usable car / vehicle bundle for known actor enum `1194` and place it into the player camp refgroup route without touching live game files.

This is the only active route for the next pass.

## Parked / Do Not Spend Time On

- Peer Clone / multiplayer / friend-client setup
- dot simulator / old bot scripts
- official multiplayer restoration
- WSC source decompile / open WSC as C/source
- source-built WSC replacement unless explicitly requested
- live `content.rpf` writes

## Known Facts Already Established

### Car / Vehicle

- `1194` is the known car / vehicle actor enum from prior Code RED research.
- The pasted MagicRDR decompile showed `Function_15(&uLocal_4, 1194, 3, 0)`.
- The same script checked `WOULD_ACTOR_BE_VISIBLE(1194, ...)`.
- The streaming function treats asset type `2` / `3` as actor streaming through `STREAMING_REQUEST_ACTOR` and `STREAMING_IS_ACTOR_LOADED`.
- Conclusion: `1194` is not a random mesh number. It is actor/vehicle-streaming data.

### Player Camp Route

- Inventory route:
  - `CAMP` -> `$\content\scripting\gringo\UseItems\Camp`
  - `CAMP_LVL1` -> `$\content\scripting\gringo\UseItems\Camp_Lvl1`
- Camp script route:
  - `$/tune/refGroups/campsiteSets/cam_playerCamp03x`
- Camp script already handles camp layout, propsets, actors, gringos, `horse_stay`, and vehicle-aware logic such as `IS_ACTOR_VEHICLE(...)`.
- Refgroups can place props/meshes by `reference T:/rdr2/Art/...`, `transform ...`, and `attribute rstarInfoSnapping ...`.
- User has already proven refgroups can spawn props, unusable meshes, and build coordinate forts.
- User has also observed only some things are usable, like turrets and cannons.

### Refgroup / Path Layer

- Pasted refgroup-style file format uses:
  - `reference T:/rdr2/Art/Worlds/territory/shared/models/.../*.mb`
  - `transform X Y Z RX RY RZ`
  - `attribute rstarInfoSnapping rstarInfoSnapping_Type string align/flat`
- This means path resolution matters. A mesh-only car path can display a car but will not make it usable.
- Likely missing piece: the correct full usable car/vehicle bundle path, not just the fragment mesh.

### Why Cannons/Turrets Matter

- Cannons and turrets are usable because they are not just static mesh placements.
- They likely include a gringo/use/weapon behavior bundle, use components, and possibly actor/vehicle/tune resources.
- The useful comparison is: usable cannon/turret refgroup/gringo bundle vs. dead mesh car placement.

### WSV Suspicion

- WSV files may contain related model/reference paths or world/scene variants.
- WSV research is not proven complete.
- WSV should only be scanned for the active target: vehicle/car/gringo/reference-path clues.

## Tools / Lanes Already Built

### RPF / Archive Tools

- `tools/codered_rpf_utils.py`
  - parse/inventory/extract RPF archives through the Code RED backend.
- `tools/codered_rpf_utils_patch.py`
  - patch copied archives only.
- `tools/codered_content_convert_overlay_builder.py`
  - copied overlay / replacement builder used by WSC and content patch workflows.

### WSC Tools

- `tools/codered_wsc_edit_workflow.py`
  - default lane is now existing-file binary edit.
  - `init` / `decompile` create original-derived editable WSC workspaces.
  - supports `inspect`, `strings`, `replace-string`, `patch-bytes`, `pack`.
  - packs edited original-derived WSC into copied RPF.
- Explicit full replacement lane still exists:
  - `full-replace-init`
  - `full-replace-compile`
- WSC source decompile/rebuild is blocked and should not be treated as available.

### Peer Clone Tools

- Peer Clone v0.4 proved an external top-down two-player arena only.
- Game bridge ASI was built but did not yet give a clean visible in-game clone proof.
- Park this lane for now.

## Current Missing Link

Find the exact file/path/bundle that connects known vehicle actor enum `1194` to usable vehicle behavior.

Specifically find one of:

1. a refgroup entry that already places/uses the `1194` vehicle actor;
2. a gringo/use entry that owns the car interaction;
3. a WSV/path entry that reveals the correct car/vehicle internal path;
4. a cannon/turret-style usable bundle pattern that can be copied into `cam_playerCamp03x`;
5. a direct actor/vehicle slot in `cam_playerCamp03x` or related campsite set that can accept `1194`.

## Next Pass: Only This

Run a focused path scan. Do not create broad unrelated research.

Search only for:

- `1194`
- `cam_playerCamp03x`
- `playerCamp03x`
- `UseItems/Camp`
- `Camp_Lvl1`
- `vehicle`
- `car`
- `wagon`
- `coach`
- `seat`
- `UseCase1`
- `gringo`
- `cannon`
- `turret`
- `T:/rdr2/Art`
- `*.wsv`

Search locations:

- `tune.rpf`
- `tune_d11generic.rpf`
- `gringores.rpf` if present
- `content.rpf`
- extracted `tune/refGroups/campsiteSets`
- extracted `tune/refGroups`
- extracted gringo files
- WSV files
- fragments only to correlate visible mesh paths, not as the sole usability source

## Required Output For Next Pass

Create:

- `logs/active_route_1194_car_bundle_scan/1194_car_bundle_scan.md`
- `logs/active_route_1194_car_bundle_scan/1194_car_bundle_scan.json`

Report only:

1. exact files containing the search hits;
2. exact candidate `T:/rdr2/Art/...` paths;
3. whether each candidate is mesh-only, actor, gringo/use, WSV/path, or likely full usable bundle;
4. whether it can be inserted into or swapped into `cam_playerCamp03x`;
5. one recommended copied patch candidate if the target is editable.

## Working Rule

If a step does not directly answer “where is the usable 1194 car bundle or the camp slot for it?”, do not do it.
