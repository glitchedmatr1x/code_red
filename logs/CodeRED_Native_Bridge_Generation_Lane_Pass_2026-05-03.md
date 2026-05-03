# Code RED Native Bridge Generation Report

Generated: `2026-05-03T09:08:32Z`
Profile: `ai_trainer_core`

## Result

- Selected natives: 26
- Ready wrappers: 26
- Partial entries: 0
- SDK native entries parsed: 3492
- Native database entries loaded: 9102

## Outputs

- `data/codered/native_bridge_manifest.json`
- `data/codered/native_bridge_manifest.csv`
- `data/codered/native_bridge_selected_wrappers.cpp`
- `data/codered/native_bridge_compile_probe.cpp`

## Safety Notes

- This is selected bridge prep only; it does not auto-patch the ASI.
- Use generated wrappers one lane at a time with compile and in-game proof.
- Partial entries are intentionally not emitted as callable wrappers.

## Selected Natives

| Status | Name | Hash | Category | Params | Warnings |
|---|---|---:|---|---:|---|
| ready | GET_PLAYER_ACTOR | `0xE8CFDD53` | actor | 1 |  |
| ready | IS_ACTOR_VALID | `0xBA6C3E92` | actor | 1 |  |
| ready | IS_ACTOR_ALIVE | `0x2F232639` | actor | 1 |  |
| ready | FIND_NAMED_LAYOUT | `0x5699DE7E` | world | 1 |  |
| ready | CREATE_LAYOUT | `0x6CA53214` | world | 1 |  |
| ready | CREATE_ACTOR_IN_LAYOUT | `0x8D67F397` | actor | 7 | param_count_diff_db_5_sdk_7 |
| ready | GET_POSITION | `0x99BD9D6F` | world | 2 |  |
| ready | TELEPORT_ACTOR | `0x2D54B916` | actor | 5 |  |
| ready | SET_ACTOR_HEADING | `0xECE8520B` | actor | 3 |  |
| ready | TASK_CLEAR | `0x16876A25` | ai_task | 1 |  |
| ready | TASK_STAND_STILL | `0x6F80965D` | ai_task | 4 |  |
| ready | TASK_WANDER | `0x17BCA08E` | ai_task | 2 |  |
| ready | TASK_FOLLOW_ACTOR | `0x12F0911A` | actor | 2 |  |
| ready | TASK_KILL_CHAR | `0x1AE4B75B` | actor | 2 |  |
| ready | AI_IS_HOSTILE_OR_ENEMY | `0x9AB964F4` | ai_task | 2 |  |
| ready | SET_ACTOR_FACTION | `0xCC63951A` | actor | 2 |  |
| ready | GET_ACTOR_FACTION | `0x52E2A611` | actor | 1 |  |
| ready | GIVE_WEAPON_TO_ACTOR | `0x6AA0EAF2` | actor | 5 |  |
| ready | TASK_MOUNT | `0xB6131204` | actor | 6 |  |
| ready | TASK_DISMOUNT | `0x5DEF5C4A` | actor | 2 |  |
| ready | GET_MOUNT | `0xDD31EC4E` | actor | 1 |  |
| ready | GET_VEHICLE | `0xA0936EB6` | vehicle | 1 |  |
| ready | START_VEHICLE | `0xE4442AB2` | vehicle | 1 |  |
| ready | STOP_VEHICLE | `0xC2232D29` | vehicle | 1 |  |
| ready | TASK_VEHICLE_LEAVE | `0x6C1218A4` | ai_task | 1 |  |
| ready | RELEASE_LAYOUT_REF | `0xD9AC8830` | world | 1 |  |
