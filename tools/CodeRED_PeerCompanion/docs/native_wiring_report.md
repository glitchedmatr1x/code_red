# Native Wiring Report

`CodeRED_PeerCompanion.asi` resolves ScriptHookRDR exports dynamically with
`GetProcAddress`. It does not link against `ScriptHookRDR.lib`.

Required ScriptHook exports:

- `scriptRegister`
- `scriptUnregister`
- `keyboardHandlerRegister`
- `keyboardHandlerUnregister`
- `scriptWait`
- `nativeInit`
- `nativePush64`
- `nativeCall`

Native hashes used in Pass 1:

- `GET_PLAYER_ACTOR` `0xE8CFDD53`
- `IS_ACTOR_VALID` `0xBA6C3E92`
- `GET_POSITION` `0x99BD9D6F`
- `GET_HEADING` `0x42DE39F0`
- `GET_ACTOR_HEALTH` `0xF246F15D`
- `FIND_NAMED_LAYOUT` `0x5699DE7E`
- `CREATE_LAYOUT` `0x6CA53214`
- `CREATE_ACTOR_IN_LAYOUT` `0x8D67F397`
- `SET_ACTOR_HEADING` `0xECE8520B`
- `TELEPORT_ACTOR` `0x2D54B916`
- `TASK_CLEAR` `0x16876A25`
- `TASK_STAND_STILL` `0x6F80965D`
- `TASK_FOLLOW_ACTOR` `0x12F0911A`
- `SET_ACTOR_FACTION` `0xCC63951A`
- `SET_ACTOR_INVULNERABILITY` `0xE38EF526`
- `GIVE_WEAPON_TO_ACTOR` `0x6AA0EAF2`
- `ACTOR_PUT_WEAPON_IN_HAND` `0x8F4B473D`
- `DELETE_ALL_WEAPONS_FROM_ACTOR` `0xD695F857`
- `DESTROY_ACTOR` `0x8BD21869`

All actor commands validate the player and/or companion handle before issuing
native calls. No multiplayer, network-auth, RPF, WSC, SCXML, or EXE paths are
called by this ASI.
