# Soul Stealer Pass 2 Test Plan

## Stage 0 — Mock

Expected output:

- arms Soul Stealer
- captures reticle target
- uses fallback when real swap unavailable
- cancels and restores
- uses real swap when mock bridge permits it
- rejects animal reticle and falls back to NPC when animals are disabled

## Stage 1 — In-game probe only

Config:

```json
{ "possessionMode": "ProbeOnly" }
```

Test:

1. Load single-player.
2. Press F8 to arm.
3. Aim at a nearby NPC.
4. Press capture key.
5. Confirm a HUD/debug message with target/model/position.

## Stage 2 — Fallback possession

Config:

```json
{ "possessionMode": "ForceFallbackModelTeleport" }
```

Test:

1. Arm Soul Stealer.
2. Capture a normal ambient NPC.
3. Confirm the player moves to the NPC location and takes its model if `setPlayerModel` works.
4. Press cancel.
5. Confirm player control and position restore.

## Stage 3 — Real swap

Config:

```json
{ "possessionMode": "PreferRealSwap" }
```

Only test after `swapPlayerToActor` is wired and logged.

## Emergency rule

Always keep Backspace/Esc cancel available. If the actor/control state gets stuck, reload without saving.
