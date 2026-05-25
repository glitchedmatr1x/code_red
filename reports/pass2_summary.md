# Soul Stealer Reconstruction Pass 2 Summary

## What changed from Pass 1

- Split native calls behind `INativeBridge`.
- Added `TargetSelector` with reticle, last-damaged, nearest-forward, and nearest-radius target modes.
- Added `PossessionController` with real-swap, fallback model/teleport, and probe-only modes.
- Added config structure and sample JSON.
- Added mock bridge and expanded mock tests.
- Added ASI integration TODO skeleton for Codex.

## Why this matters

This package lets Codex wire the Soul Stealer logic into the actual Code RED PC plugin without rewriting the gameplay/state logic. The native bridge is the only piece that needs project-specific implementation.

## Old trainer reference map

Static inspection of the JediJosh trainer found strings/helpers such as:

- `Soul Stealer`
- `Soul Stealer: attack an NPC to switch to them`
- `SwapPlayerToActorR`
- `SetPlayerControlR`
- `GetAllActors`
- `TASK_CLEAR_IMMEDIATELY8`
- `SetPlayerModel8`
- `SetActorPos8`

This package does not port the old trainer. It reconstructs the feature cleanly for PC.
