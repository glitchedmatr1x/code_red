# Public Test Flow

## Proof target

This package only needs to prove that two machines can exchange player state.

## Pass condition

- Player A sees `remote player_b`.
- Player B sees `remote player_a`.
- `runtime/*.jsonl` files are created.

## Do not test yet

- Real game joining.
- Official multiplayer menus.
- Vehicles/mounts.
- Combat authority.
- Ragdolls.
- Mission state.

## Why this first

The engine-level multiplayer/session layer is not proven. A clone-sync relay is the simplest safe proof before trying game integration.
