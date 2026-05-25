# Code RED Soul Stealer Pass 2 — Native Wiring TODO

## Status

The Soul Stealer logic is now separated from the native layer. Codex only needs to wire `RdrNativeBridge` to the local Code RED ASI / ScriptHook RDR project.

## Highest-priority native mappings

| Bridge method | Needed native/wrapper | Notes |
|---|---|---|
| `getPlayerActor()` | `GET_PLAYER_ACTOR` | Must return current controllable actor. |
| `getActorUnderReticle()` | targeted/reticle actor native | Optional. If missing, nearest-forward target works. |
| `getAllActors()` | actor pool iterator / object iterator | Needed for nearest-forward fallback. |
| `clearActorTasksImmediately()` | `TASK_CLEAR_IMMEDIATELY` | Old trainer had `TASK_CLEAR_IMMEDIATELY8`. |
| `swapPlayerToActor()` | `SwapPlayerToActorR` equivalent | Most important for real Soul Stealer. Return false until proven. |
| `setPlayerControl()` | `SetPlayerControlR` / `SET_PLAYER_CONTROL` | Use after swap or fallback. |
| `setPlayerModel()` | `SetPlayerModel8` equivalent | Fallback mode. |
| `setActorPos()` | `SetActorPos8` equivalent | Fallback mode. |
| `setActorHeading()` | heading setter | Fallback mode. |
| `setActorFrozen()` | freeze/AI-off/native task loop | Keeps target body from walking away during fallback. |
| `showMessage()` | print/HUD/message native | Debug feedback. |

## Safe first integration

1. Wire only actor read functions first.
2. Set `possessionMode = ProbeOnly`.
3. Confirm F8/E can select an actor and print model/position.
4. Wire fallback model/teleport.
5. Only then test direct actor swap.

## Do not do yet

- Do not delete/kills target actors.
- Do not touch live `content.rpf`.
- Do not patch WSC for Soul Stealer v0.2.
- Do not enable online/multiplayer use.
