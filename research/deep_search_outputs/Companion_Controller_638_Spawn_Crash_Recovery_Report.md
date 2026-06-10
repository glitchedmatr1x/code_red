# Companion Controller 638 Spawn Crash Recovery Report

Scope: Code RED source/build packaging only. No RPF, WSC, TR, tune, content, retail executable, ScriptHookRDR DLL, or game install files were modified.

## What Was Rechecked

- `tools/CodeRED_PeerCompanion/CodeRED_PeerCompanion.cpp`
- `tools/CodeRED_PeerCompanion/data/codered/peer_companion.ini`
- `tools/CodeRED_PeerCompanion/build_peer_companion_windows.ps1`
- `D:\Games\Red Dead Redemption\logs\codered_peer_companion.log`
- `D:\Games\Red Dead Redemption\ScriptHookRDR\sdk\inc\natives.h`
- `tools/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp`
- `tools/CodeRED_Peer_Clone_Game_Bridge_v0_1/CodeRED_Peer_Clone_Game_Bridge.cpp`
- `tools/Code_RED_ScriptHookRDR_AI_Menu/data/codered/actor_enum_map.csv`

## Findings

Actor enum `638` is confirmed as `ACTOR_misc_son`.

The old working spawn lane used the same convention as the ScriptHookRDR SDK overload and AI menu:

```text
Vector2(position.x, position.y), position.z
```

The current PeerCompanion source had drifted to `spawn_use_xz_ground_plane=true`, which passes:

```text
Vector2(position.x, position.z), position.y
```

That alternate mode can return a valid actor handle while placing the actor at the wrong coordinate/elevation. The live log showed exactly that kind of risk:

```text
player_xyz=294.923,0,106.017
spawn_xyz=296.447,0.35,107.999
xz_ground_plane=true
create_actor_return=4595
```

Earlier logs from the first trainer path showed valid spawns using the SDK/AI-menu convention:

```text
player_xyz=176.599,0,111.177
spawn_xyz=177.033,2.96835,111.177
actor_enum=369
using_spawn_method=CodeRED_AI_Menu::spawnSelectedNpc
create_actor_return=2880
is_actor_valid_after_create=true
```

The runtime also previously logged a missing config case:

```text
load_config defaulted reason=missing_ini path=D:\Games\Red Dead Redemption\data\codered\peer_companion.ini
```

That means the installed ASI could silently use source defaults instead of the intended INI.

## SDK Signatures Confirmed

From `D:\Games\Red Dead Redemption\ScriptHookRDR\sdk\inc\natives.h`:

| Native | Signature | Hash | Status |
|---|---|---:|---|
| `GET_POSITION` | `void GET_POSITION(Actor actor, Vector3* position)` | `0x99BD9D6F` | used |
| `GET_HEADING` | `float GET_HEADING(Actor actor)` | `0x42DE39F0` | used |
| `SET_ACTOR_HEADING` | `void SET_ACTOR_HEADING(Actor actor, float heading, BOOL p2)` | `0xECE8520B` | used, now guarded |
| `GET_PLAYER_ACTOR` | `Actor GET_PLAYER_ACTOR(Player player)` | `0xE8CFDD53` | used |
| `CREATE_ACTOR_IN_LAYOUT` | `Actor CREATE_ACTOR_IN_LAYOUT(Layout, const char*, int, Vector2, float, Vector2, float)` | `0x8D67F397` | used |
| `CREATE_ACTOR_IN_LAYOUT` overload | `Actor CREATE_ACTOR_IN_LAYOUT(Layout, const char*, int, Vector3, Vector3)` packs `Vector2(x,y), z` | `0x8D67F397` | used as default convention |
| `STREAMING_REQUEST_ACTOR` | `void STREAMING_REQUEST_ACTOR(int actorEnum, BOOL p1, BOOL p2)` | `0xB0A79FEE` | used |
| `STREAMING_IS_ACTOR_LOADED` | `BOOL STREAMING_IS_ACTOR_LOADED(int actorEnum, int p1)` | `0x7DF72579` | used |
| `SET_ACTOR_FACTION` | `void SET_ACTOR_FACTION(Actor actor, int faction)` | `0xCC63951A` | used |
| `SET_ACTOR_IS_COMPANION` | `void SET_ACTOR_IS_COMPANION(Actor actor, BOOL toggle)` | `0x4C94EB9E` | config-gated |
| `TASK_FOLLOW_ACTOR` | `void TASK_FOLLOW_ACTOR(Actor actor, Actor followActor)` | `0x12F0911A` | used |
| `CREATE_SQUAD_IN_LAYOUT` | `int CREATE_SQUAD_IN_LAYOUT(Layout layout, const char* squadName)` | `0xF7277A0F` | present, disabled by default |
| `SQUAD_JOIN` | `void SQUAD_JOIN(Any p0, Any p1)` | `0xB14302C8` | present, disabled by default |
| `SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION` | `int ... (Any p0, Any p1, Any p2, Any p3, Any p4, Any p5)` | `0x1AC03C80` | present, disabled by default |
| `TASK_MOUNT` | `void TASK_MOUNT(Any p0, Any p1, Any p2, Any p3, Any p4, Any p5)` | `0xB6131204` | research-only for now |
| `TASK_USE_TURRET` | `int TASK_USE_TURRET(Any p0, Any p1, float p2, Any p3, Any p4)` | `0x6484F21E` | research-only for now |

## Changes Made

- Defaulted `spawn_use_xz_ground_plane=false` in source and INI.
- Kept the alternate X/Z mode available for diagnostics.
- Added spawn logging that reports:
  - coordinate mode
  - requested spawn position
  - actual actor position after creation
  - distance from player
  - distance from requested spawn point
- Wrapped `SET_ACTOR_HEADING` and Code RED-owned `DESTROY_ACTOR` cleanup in exception-safe helper calls.
- Updated the build script to create:

```text
tools/CodeRED_PeerCompanion/build/install_package/
  CodeRED_PeerCompanion.asi
  data/codered/peer_companion.ini
```

This prevents testing a new ASI with a missing or stale INI.

## Build Result

Command:

```powershell
powershell -ExecutionPolicy Bypass -File tools\CodeRED_PeerCompanion\build_peer_companion_windows.ps1
```

Result:

- Build succeeded.
- ASI: `tools/CodeRED_PeerCompanion/build/CodeRED_PeerCompanion.asi`
- SHA1: `B2A511B65590798B698593D72BE114965A1DAFE8`
- Install package: `tools/CodeRED_PeerCompanion/build/install_package`

## What This Does Not Claim Yet

- It does not prove squad route is safe at runtime.
- It does not enable driving/turret commands yet.
- It does not change actor appearance yet.
- It does not edit game content.

Those should come after F7 visibly spawns actor 638 and F10 fallback follow works reliably.
