# Spawn Wiring Report

Pass: Peer Companion Spawn Fix

## Source Compared

Working Code RED trainer source:

`related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp`

Relevant helper:

`spawnSelectedNpc()`

## Copied Spawn Convention

PeerCompanion now uses the same `CREATE_ACTOR_IN_LAYOUT` calling convention as
the Code RED AI Menu:

```cpp
Vector3 playerPos = {};
nativeInvoke<void>(0x99BD9D6F, player, &playerPos);
float heading = nativeInvoke<float>(0x42DE39F0, player);
float radians = heading * (PI / 180.0f);
Vector2 spawnXY = {
    playerPos.x + std::sin(radians) * spawnDistance,
    playerPos.y + std::cos(radians) * spawnDistance
};
Vector2 orientXY = {0.0f, 1.0f};
Actor spawned = nativeInvoke<Actor>(
    0x8D67F397,
    layout,
    instanceName,
    actorEnum,
    spawnXY,
    playerPos.z,
    orientXY,
    heading
);
```

The helper uses:

- `GET_PLAYER_ACTOR` `0xE8CFDD53`
- `GET_POSITION` `0x99BD9D6F`
- `GET_HEADING` `0x42DE39F0`
- `FIND_NAMED_LAYOUT` `0x5699DE7E`
- `CREATE_LAYOUT` `0x6CA53214`
- `CREATE_ACTOR_IN_LAYOUT` `0x8D67F397`
- `IS_ACTOR_VALID` `0xBA6C3E92`

## Disabled For This Pass

F8 spawn does not call:

- `TELEPORT_ACTOR`
- `TASK_STAND_STILL`
- `TASK_FOLLOW_ACTOR`
- `TASK_CLEAR`
- `SET_ACTOR_FACTION`
- `GIVE_WEAPON_TO_ACTOR`
- invincibility natives
- repeated position nudges

`post_spawn_actions_enabled=false` by default.

## Config

`data/codered/peer_companion.ini`

- `companion_actor_enum=369`
- `fallback_actor_enum=111`
- `spawn_distance=3.0`
- `spawn_height_offset=0.0`
- `spawn_heading_offset=0.0`
- `post_spawn_actions_enabled=false`

If enum `369` fails validation, the spawn path tries fallback enum `111`.

## Required Log Lines

F8 writes:

- `ENTER spawn_companion`
- `player_valid=true/false`
- `player_xyz=x,y,z`
- `heading=h`
- `spawn_xyz=x,y,z`
- `actor_enum=n`
- `using_spawn_method=CodeRED_AI_Menu::spawnSelectedNpc`
- `create_actor_return=handle`
- `is_actor_valid_after_create=true/false`
- `EXIT spawn_companion OK/FAILED reason=...`
