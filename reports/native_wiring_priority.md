# Soul Stealer Native Wiring Priority

Wire these first for a useful proof:

1. `getPlayerActor`
2. `isActorValid`
3. `isActorAlive`
4. `getActorPos`
5. `getActorHeading`
6. `getActorModel`
7. `getAllActors`
8. `clearActorTasksImmediately`
9. `setActorPos`
10. `setActorHeading`
11. `setPlayerModel`
12. `setPlayerControl`

Then try real possession:

13. `swapPlayerToActor`
14. `getActorUnderReticle`
15. `getLastActorDamagedByPlayer`

Fallback possession can work without #13 if #11/#9/#10 are available.
