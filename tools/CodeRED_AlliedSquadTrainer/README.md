# CodeRED Allied Squad Trainer

Minimal ScriptHookRDR SDK-linked ASI for testing existing allied actors as squad members.

This pass does not spawn actors, draw overlays, edit RPF/WSC/TR files, or call multiplayer code.

## Controls

- F6: log a nearby actor/faction snapshot.
- F7: run the configured staged squad probe.
- F8: clear goals and empty the CodeRED squad.

Logs are written to:

```text
logs/codered_allied_squad_trainer.log
```

## Config

Copy:

```text
data/codered/allied_squad_trainer.ini
```

beside the game executable with the ASI. Defaults join same-faction actors and faction `20` within `45.0` meters.

`f7_mode` is deliberately staged:

```text
snapshot_only
create_squad_only
join_player_only
join_allies_no_goal
join_allies_follow_goal
```

Start with `snapshot_only`. If the game stays stable and the log shows `EXIT snapshot OK`, move one step at a time.

## Build

From `D:\Games\Red Dead Redemption\Code_RED`:

```powershell
powershell -ExecutionPolicy Bypass -File tools\CodeRED_AlliedSquadTrainer\build_allied_squad_trainer_windows.ps1
```

Output:

```text
tools/CodeRED_AlliedSquadTrainer/build/CodeRED_AlliedSquadTrainer.asi
tools/CodeRED_AlliedSquadTrainer/build/install_package/
```
