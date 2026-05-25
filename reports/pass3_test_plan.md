# Soul Stealer Pass 3 Local Test Plan

## Sandbox tests already passed

- Configure/build CMake project.
- Run mock possession tests.
- Run runtime hotkey tests.

## First Windows/ASI test order

1. `ProbeOnly` mode.
   - Confirm F8 arms.
   - Confirm capture selects an NPC and logs actor/model/position.
   - No possession yet.

2. `ForceFallbackModelTeleport` mode.
   - Confirm capture teleports/model-swaps player safely.
   - Confirm Backspace cancel restores position/model.

3. `PreferRealSwap` mode.
   - Only after a real `swapPlayerToActor` wrapper is found.
   - Confirm emergency cancel works.

## Do not test first

- horses/animals,
- mission actors,
- online/MP,
- remote puppet sync.
