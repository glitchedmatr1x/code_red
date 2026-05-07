# Code RED Peer Clone Sync v0.1

A standalone first-pass connection app for the simplest possible two-player Code RED test:

```text
two games
+ same sync client/plugin on both
+ one tiny relay host
+ each game displays the other player as a local clone/puppet actor
```

This package does **not** restore official multiplayer. It proves the connection and state relay layer that an in-game script/plugin can later use to spawn and move clone actors.

## What this pass includes

- TCP relay host/server.
- Mock client that simulates player movement.
- GUI launcher for quick tests.
- Local self-test that proves two clients exchange clone states.
- JSONL runtime logs for proof.
- A future game-plugin bridge contract.

No external packages required.

## First proof test on one PC

```bat
Run_SelfTest.bat
```

Expected:

```text
# Selftest result: PASS
player_a saw player_b: True
player_b saw player_a: True
```

## LAN/VPN test with your tester

### Player A / host machine

1. Run:

```bat
Run_Relay_Host.bat
```

2. Allow Windows Firewall if prompted.
3. Give Player B your LAN/VPN IP.
4. In another window, run:

```bat
Run_Mock_Client_A.bat
```

### Player B / second machine

Edit `Run_Mock_Client_B.bat` and replace `127.0.0.1` with Player A's IP, then run it.

Expected result:

- Player A sees logs like `remote player_b`.
- Player B sees logs like `remote player_a`.
- Runtime logs appear in `runtime/`.

## GUI mode

```bat
Run_GUI.bat
```

Use this when someone wants buttons instead of command lines.

## Ports

Default relay port:

```text
47666/tcp
```

For remote testing, use LAN first. If not on same network, use Radmin VPN, ZeroTier, Hamachi, or a forwarded TCP port.

## Current data sent

Each client sends:

```json
{
  "type": "state",
  "x": 1.0,
  "y": 2.0,
  "z": 0.0,
  "heading": 90.0,
  "speed": 1.6,
  "health": 100,
  "weapon": "WEAPON_REVOLVER",
  "action": "walk"
}
```

## Next game-integration milestone

The in-game side should do this:

```text
local player:
- read player position / heading / action state
- write/send that to relay

remote player:
- receive remote state
- spawn a clone actor if missing
- teleport/interpolate clone toward remote position
- set heading
- choose a simple animation/task from action field
```

Keep the first in-game pass simple:

```text
position + heading only
no vehicles
no ragdolls
no world ownership
no missions
no law/wanted sync
```

## Important limits

This is fake co-op / puppet sync. The remote player is a locally spawned actor replica, not an engine-owned network player.

That means the first pass can prove:

- connection
- remote clone visibility
- basic movement mirroring

But it will not yet prove:

- true lobby multiplayer
- official session joining
- world event sync
- vehicle authority
- real bullet authority
- perfect physics/ragdoll sync
