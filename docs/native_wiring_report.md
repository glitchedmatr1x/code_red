# Code RED Remote Menu Native Wiring

This pass uses the existing Code RED ScriptHookRDR native invoker pattern. Exports are resolved dynamically from `ScriptHookRDR.dll`; no `ScriptHookRDR.lib` link is required.

## ScriptHook Exports

- `scriptRegister`
- `scriptUnregister`
- `keyboardHandlerRegister`
- `keyboardHandlerUnregister`
- `scriptWait`
- `drawRect`
- `drawText`
- `nativeInit`
- `nativePush64`
- `nativeCall`
- optional `worldGetAllActors`

## Native Wrappers

- `GET_PLAYER_ACTOR` `0xE8CFDD53`
- `GET_POSITION` `0x99BD9D6F`
- `GET_ACTOR_HEADING` `0x42DE39F0`
- `TELEPORT_ACTOR` `0x2D54B916`
- `SET_ACTOR_HEADING` `0xECE8520B`
- `IS_ACTOR_VALID` `0xBA6C3E92`
- `IS_ACTOR_ALIVE` `0x2F232639`
- `TASK_CLEAR` `0x16876A25`

## Not Wired Yet

- true possession / player-control swap
- player model swap
- camera follow actor
- real map/radar blip creation

Those remain blocked until the native hashes and stack behavior are verified in-game.
