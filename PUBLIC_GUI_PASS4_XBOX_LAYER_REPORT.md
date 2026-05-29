# Code RED Public GUI Pass 4 - Xbox Layer Resolver

This pass adds a public-safe Xbox/Xenia research lane to Code RED.

## Added

- `tools/codered_xbox_layer_resolver.py`
  - Read-only layer resolver for folders, ZIPs, and RPF name probes.
  - Builds an effective file tree where higher-priority layers override lower-priority paths.
  - Tags profile/avatar/networking and init/pop/zombie files for faster research.
  - Includes XSC/SCO/WSC/CSC detector mode.
- `python_workbench.py`
  - New **Xbox Layers** tab.
  - Add folder/archive layers in priority order.
  - Build effective file tree from the GUI.
  - Export layer reports/GPT packet.
- `docs/XBOX_LAYER_RESOLVER.md`
- `Run_Xbox_Layer_Resolver.bat`

## What this solves

Older Xbox-style RDR layouts distribute content across multiple layers. The same path can exist in more than one RPF or extracted folder. If a lower-layer copy is edited while a higher layer wins, the game may ignore the patch.

The resolver makes this visible before editing.

## Public safety

This pass does not include Disc 2, RPF, XSC, SCO, WSC, STFS, profile, save, or extracted game files.

The tools are read-only unless the user chooses to separately create patch outputs from their own private files.

## Validation

- GUI self-test passed.
- Xbox layer resolver self-test passed.
- Python compile check passed.
- No blocked raw game/script/binary files were added.
