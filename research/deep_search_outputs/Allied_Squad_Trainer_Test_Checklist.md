# Code RED Allied Squad Trainer Test Checklist

This test is for the separate `CodeRED_AlliedSquadTrainer.asi` only. Do not install it alongside PeerCompanion, Silent Virtues, JediJosh, Remote Menu, avatar picker tests, or MP restore tests.

## Install

Copy from:

```text
D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_AlliedSquadTrainer\build\install_package
```

to the normal Red Dead Redemption game folder beside `RDR.exe`.

Expected files:

```text
CodeRED_AlliedSquadTrainer.asi
data\codered\allied_squad_trainer.ini
```

## First run

1. Launch normal single-player.
2. Wait until the world is loaded and stable.
3. Press `F6`.
4. Check:

```text
logs\codered_allied_squad_trainer.log
```

Expected result: `EXIT snapshot OK` with player position, player faction, nearby actor counts, and any allied candidates.

## Staged F7 tests

The new default is:

```text
f7_mode=snapshot_only
```

Do not jump straight to full squad follow. Edit `data\codered\allied_squad_trainer.ini` one stage at a time:

```text
snapshot_only
create_squad_only
join_player_only
join_allies_no_goal
join_allies_follow_goal
```

For each stage:

1. Launch normal single-player.
2. Wait 20 seconds after world load.
3. Press `F7` once.
4. Do not press other keys for 15 seconds.
5. Check the last `ENTER ...` line and matching `EXIT ...` line.

When `join_allies_no_goal` works, the expected log includes:

```text
ENTER squad_nearby_allies
squad_nearby_allies: joined_player
squad_nearby_allies: joined_actor
EXIT squad_nearby_allies OK
```

Only test `join_allies_follow_goal` after `join_allies_no_goal` survives.

If the game soft-crashes, send back the last 30 lines of:

```text
logs\codered_allied_squad_trainer.log
```

## Reset

Press `F8` to clear goals and empty the Code RED squad.

Expected log:

```text
EXIT reset_squad OK
```

## Tuning

If your allies are visible in game but not joined, edit:

```text
data\codered\allied_squad_trainer.ini
```

Try increasing:

```text
radius=70.0
```

If `F6` logs their faction, add it to:

```text
ally_factions=20,<their faction id>
```

Keep `set_actor_companion_flag=false` for the first test.
