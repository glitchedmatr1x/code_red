# Code RED Link Protocol

Phase 1 uses a local file bridge only. No sockets, GameSpy, official multiplayer backend, RPF edits, or WSC edits are involved.

## Paths

Runtime files live beside `RDR.exe`:

```text
data/codered/link/local_player_state.json
data/codered/link/remote_player_state.json
```

## Local Player State

Written by `CodeRED_Remote_Menu.asi` every `write_interval_ms`.

```json
{
  "version": 1,
  "player_id": "local",
  "name": "Player",
  "timestamp_ms": 123456789,
  "world": "rdr_sp",
  "x": 0.0,
  "y": 0.0,
  "z": 0.0,
  "heading": 0.0,
  "speed": 0.0,
  "state": "idle",
  "valid": true
}
```

## Remote Player State

Written by `CodeRED_Link_TestClient.py` or a future relay app. Read by the ASI every `read_interval_ms`.

```json
{
  "version": 1,
  "player_id": "remote_1",
  "name": "Remote Player",
  "timestamp_ms": 123456789,
  "world": "rdr_sp",
  "x": 0.0,
  "y": 0.0,
  "z": 0.0,
  "heading": 0.0,
  "speed": 0.0,
  "state": "idle",
  "valid": true
}
```

## Timing

- File bridge defaults to 1 Hz reads/writes for this first pass.
- `timestamp_ms` uses Unix epoch milliseconds.
- Remote state older than `stale_ms` is treated as disconnected.
- UDP is handled by the external `CodeRED_Link_LANRelay.py` helper. The ASI still only reads and writes local JSON files.

## UDP Relay Packet

`CodeRED_Link_LANRelay.py` wraps one state object in a small JSON UDP packet:

```json
{
  "protocol": "codered_link",
  "protocol_version": 1,
  "sender_id": "local",
  "sent_timestamp_ms": 123456789,
  "state": {
    "version": 1,
    "player_id": "local",
    "name": "Player",
    "timestamp_ms": 123456789,
    "world": "rdr_sp",
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "heading": 0.0,
    "speed": 0.0,
    "state": "idle",
    "valid": true
  }
}
```

The relay refreshes `timestamp_ms` when writing `remote_player_state.json`, so ASI stale detection reflects relay receive time.

## Safety

- The ASI reads the real player only.
- The ASI only moves the Code RED-owned puppet handle spawned with `F9`.
- Soul Stealer and world actor scanning remain disabled.
- Blip/label markers remain config-gated.
