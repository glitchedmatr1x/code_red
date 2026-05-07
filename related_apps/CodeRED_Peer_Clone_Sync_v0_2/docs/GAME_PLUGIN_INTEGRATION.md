# Future Game Plugin Integration Notes

This is the bridge from the standalone app to the actual game script/plugin.

## Game client output

A game plugin can either:

1. Open a socket directly and speak the JSONL protocol, or
2. Write this file repeatedly and let the Python client run with `--bridge`:

```text
runtime/<client_id>_local_player_state.json
```

Example:

```json
{
  "x": 10.2,
  "y": -4.8,
  "z": 35.0,
  "heading": 180.0,
  "speed": 2.2,
  "health": 94,
  "weapon": "WEAPON_REVOLVER",
  "action": "walk"
}
```

## Game client input

Received remote states are logged to:

```text
runtime/<client_id>_remote_states.jsonl
```

A first in-game bridge can tail/read this and update clone actors.

## Minimal in-game algorithm

```text
for each remote client:
    if clone actor missing:
        spawn safe actor clone near player
    read latest remote state
    teleport/interpolate clone to x/y/z
    set heading
    if action changed:
        set basic task/animation
```

## First safe clone actor

Use a known safe actor entry first. Do not start with mission vehicles.

Suggested initial clone:

```text
ACTOR_player_jack
or a safe MP player actor if proven
```

## Hard rules for first game pass

- Do not sync vehicles yet.
- Do not sync ragdolls yet.
- Do not sync missions yet.
- Do not modify RPF archives.
- Do not try to make this an official lobby.
- Prove two visible puppets first.
