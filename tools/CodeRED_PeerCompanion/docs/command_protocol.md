# Code RED Peer Companion Command Protocol

Pass 1 uses JSON command packets. The external app/server writes the newest
command to:

`data/codered/link/peer_command_inbox.json`

The ASI consumes commands only when peer-control mode is enabled with F11.

Example:

```json
{
  "version": 1,
  "command_id": "peer_1_123456789_abcd",
  "peer_id": "peer_1",
  "time_ms": 123456789,
  "command": "follow_player",
  "args": {}
}
```

Supported Pass 1 commands:

- `spawn_companion`
- `despawn_companion`
- `follow_player`
- `idle`
- `friendly`
- `neutral`
- `hostile`
- `guard_player`
- `stop_combat`
- `teleport_to_player`
- `set_invincible_true`
- `set_invincible_false`
- `give_basic_weapon`
- `clear_weapons`

Unknown commands are logged and ignored. Duplicate `command_id` values are
ignored.
