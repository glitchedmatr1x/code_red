# commongringos WGD car_gringo PlayerCar-use experimental pass 1

This is an experimental WGD-side test patch for the driving/seat-use problem.

## What changed
- `car_gringo` previously had `Childs = null` and `InstanceSlotCount = 0`.
- This pass makes `car_gringo` borrow the same child pointer array used by `PlayerCar`, and sets `InstanceSlotCount` from `0` to `3`.
- No strings were resized, no new data was appended, and the unpacked WGD stays the exact same size.

## Why this is the first WGD patch candidate
- `PlayerCar` has a decoded `UseContext`: `PlayerUsable=True`, `AllowNavigateTo=True`, `FixUserMover=True`, radius `0.5`.
- `ClimbOntoWagon` has nearly the same usable pattern.
- `car_gringo` had no decoded use child at all, so the WSC seat patches may not be reached if the spawned object resolves to `car_gringo` rather than `PlayerCar`.

## Validation
- Original unpacked size: 806,912 bytes
- Patched unpacked size: 806,912 bytes
- Packed WGD size: 174,841 bytes
- Zstd repack/decompress validation: passed
- Parsed patched WGD with Code Red inspector: passed

## Patched rows
- `content\scripting\gringo\CommonScripts\PlayerCar` at `0x4C8FC`: child_count=1, instance_slot_count=3, activation_radius=200
- `content\scripting\gringo\CommonScripts\trainCar_gringo` at `0x49768`: child_count=0, instance_slot_count=0, activation_radius=200
- `content\scripting\gringo\CommonScripts\car_gringo` at `0x3D398`: child_count=1, instance_slot_count=3, activation_radius=200

## Risk
This aliases `car_gringo` to PlayerCar’s existing child pointer array instead of duplicating the child component. It is reversible and very small, but it may fail if the engine requires the child UseContext parent pointer to match the owning gringo exactly. If it crashes or removes prompts, roll back to the original `commongringos.wgd`.

## Files
- `commongringos_car_gringo_player_use_pass1.wgd` — packed replacement test
- `commongringos_car_gringo_player_use_pass1_unpacked.wgd` — unpacked validation copy
- `commongringos_car_gringo_player_use_pass1_DIFF.txt`
- `commongringos_car_gringo_player_use_pass1_changes.csv`
