# Code RED Runtime Probe Native Wiring Report

All natives are invoked through ScriptHookRDR exports resolved at runtime:

- `nativeInit`
- `nativePush64`
- `nativeCall`

Required ScriptHook registration exports:

- `scriptRegister`
- `scriptUnregister`
- `keyboardHandlerRegister`
- `keyboardHandlerUnregister`
- `scriptWait`

Optional drawing export:

- `drawText`

Mapped native hashes:

| Purpose | Hash | Status |
|---|---:|---|
| `GET_PLAYER_ACTOR` | `0xE8CFDD53` | F6 snapshot |
| `GET_POSITION` | `0x99BD9D6F` | F6 snapshot |
| `GET_HEADING` | `0x42DE39F0` | F6 snapshot |
| `STREAMING_IS_WORLD_LOADED` | `0x87B74064` | F6 snapshot |
| `UI_SEND_EVENT` | `0xB58825F5` | F7, disabled by config |
| `ENABLE_CHILD_SECTOR` | `0x7ECE15BE` | F8/F10 |
| `DISABLE_CHILD_SECTOR` | `0x9E1AE585` | F9/F11 |

Unmapped and intentionally reported as unavailable:

- current region/sector query
- save/load state query
- session/network state query
- script count query

No official multiplayer launch natives or script launch calls are wired in this pass.
