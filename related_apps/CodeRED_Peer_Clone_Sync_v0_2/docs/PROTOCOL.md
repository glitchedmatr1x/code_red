# Code RED Peer Clone Sync Protocol v1

Transport: TCP JSON lines.

## Hello

Client must send first:

```json
{
  "type": "hello",
  "protocol": "codered.peer.clone.v1",
  "client_id": "player_a",
  "name": "Player A",
  "actor": "ACTOR_player_jack",
  "client_kind": "mock"
}
```

## Welcome

Relay replies:

```json
{
  "type": "welcome",
  "protocol": "codered.peer.clone.v1",
  "client_id": "player_a",
  "roster": []
}
```

## State

Client sends repeatedly:

```json
{
  "type": "state",
  "protocol": "codered.peer.clone.v1",
  "seq": 1,
  "client_ms": 1760000000000,
  "x": 0.0,
  "y": 0.0,
  "z": 0.0,
  "heading": 0.0,
  "speed": 0.0,
  "health": 100,
  "weapon": "WEAPON_REVOLVER",
  "action": "idle",
  "mount": null,
  "vehicle": null
}
```

Relay broadcasts state to all other clients and adds:

```json
{
  "relay_ms": 1760000000000,
  "client_id": "player_a",
  "name": "Player A",
  "actor": "ACTOR_player_jack"
}
```

## Recommended send rate

Start with 10-15 Hz.

Do not attempt 60 Hz in the first game test. It creates more load without solving interpolation.
