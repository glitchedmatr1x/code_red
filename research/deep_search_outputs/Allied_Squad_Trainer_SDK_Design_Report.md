# Code RED Allied Squad Trainer SDK Design Report

## Scope

This is a minimal no-spawn, no-overlay ScriptHookRDR ASI design for placing existing nearby allied actors into a squad with the player. It intentionally avoids the failed PeerCompanion spawn/target path.

## SDK natives used

- `worldGetAllActors(int* arr, int size)` from `main.h`: enumerates world actors without relying on crosshair target detection.
- `ACTOR::GET_PLAYER_ACTOR(Player player)`: obtains local player actor.
- `ENTITY::IS_ACTOR_VALID(Actor actor)`: validates actors before other calls.
- `ACTOR::IS_ACTOR_ALIVE(Actor actor)`: skips dead actors.
- `ACTOR::IS_ACTOR_LOCAL_PLAYER(Actor actor)`: skips player during scan.
- `ACTOR::GET_POSITION(Actor actor, Vector3* position)`: radius filtering.
- `FACTION::GET_ACTOR_FACTION(Actor actor)`: same-faction and allowlist filtering.
- `OBJECT::FIND_NAMED_LAYOUT(const char* layoutName)`: attempts to reuse the Code RED layout.
- `OBJECT::CREATE_LAYOUT(const char* layoutName)`: creates a Code RED layout if missing.
- `OBJECT::CREATE_SQUAD_IN_LAYOUT(Layout layout, const char* squadName)`: creates the squad.
- `SQUADS::SQUAD_IS_VALID(Any squad)`: validates squad handle.
- `SQUADS::SQUAD_JOIN(Any squad, Any actor)`: joins player and allies.
- `SQUADS::SQUAD_SET_FACTION(Any squad, Any faction)`: optionally aligns squad faction to player faction.
- `SQUADS::SQUAD_GOALS_CLEAR(Any squad)`: clears old Code RED squad goals.
- `SQUADS::SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION(Any squad, Any object, Any, Any, Any, Any)`: optional follow goal targeting the player.
- `SQUADS::SQUAD_MAKE_EMPTY(Any squad)`: explicit reset/clean join.

## Controls

- `F6`: read-only actor/faction snapshot.
- `F7`: squad nearby allies.
- `F8`: clear goals and empty Code RED squad.

## Safety decisions

- No actor spawning.
- No actor deletion.
- No crosshair/target detection.
- No overlay/cursor.
- No WSC/TR/content edits.
- No live install or runtime test was performed by this pass.
- `ENTITY::SET_ACTOR_IS_COMPANION` is present in the SDK, but disabled by default in config.
- `DllMain` performs only SDK registration/unregistration. File logging and config reads happen in `ScriptMain`.
- `F7` defaults to `snapshot_only` and must be advanced by config one stage at a time.

## Unresolved SDK semantics

- Exact faction relationship status values are not proven, so the first filter uses same-faction plus explicit configured `ally_factions`.
- `SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION` uses generic `Any` parameters for formation details. The trainer passes zeros for optional fields and logs the returned goal handle.
- Leadership semantics are not explicitly exposed. The trainer joins the player first and sets the follow goal target to the player.

## F7 staged modes

- `snapshot_only`: no squad mutation.
- `create_squad_only`: creates/reuses the Code RED layout and squad only.
- `join_player_only`: creates squad and joins the player only.
- `join_allies_no_goal`: joins player plus nearby configured allies, but does not add a follow goal.
- `join_allies_follow_goal`: joins actors and adds a follow goal targeting the player.

## Build result

- Built output: `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_AlliedSquadTrainer\build\CodeRED_AlliedSquadTrainer.asi`
- Install package: `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_AlliedSquadTrainer\build\install_package`
- SHA1: `AFE48D3023822494EEC66A82BEAB771223067CB5`
- Build log: `D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_AlliedSquadTrainer\build\build_log.txt`
- Runtime test: not performed in this pass.

## Soft-crash response

The first build was found installed in the live Red Dead Redemption folder:

- Old ASI SHA1: `DCDED13910A4E2EB78E9C808C251106B074A936E`
- Old INI SHA1: `1C84289B28D4E5161A094ADB9B9FADE55A3D5979`

It was quarantined to:

```text
D:\Games\Red Dead Redemption\Code_RED\quarantine\allied_squad_soft_crash_20260603_024616
```

The safer diagnostic build was installed in its place:

- Live ASI: `D:\Games\Red Dead Redemption\CodeRED_AlliedSquadTrainer.asi`
- Live ASI SHA1: `AFE48D3023822494EEC66A82BEAB771223067CB5`
- Live INI: `D:\Games\Red Dead Redemption\data\codered\allied_squad_trainer.ini`
- Live INI SHA1: `167B80B22601760964BFF10C75768BE42C8E45DA`

The diagnostic defaults are:

```text
startup_delay_ms=15000
f7_mode=snapshot_only
```

This means F7 should only scan/log and should not create squads or join actors until the INI is advanced to the next stage.
