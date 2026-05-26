# Code RED Link Puppet Sync Design

## Architecture

```text
RDR single-player world
  -> CodeRED_Remote_Menu.asi reads player position/heading
  -> local_player_state.json
  -> CodeRED_Link_TestClient.py or future relay
  -> remote_player_state.json
  -> CodeRED_Remote_Menu.asi updates one local puppet actor
```

This is pseudo-coop representation, not official multiplayer. Each player remains in their own single-player world.

For LAN testing, run `CodeRED_Link_LANRelay.py` on each PC. The relay is outside the game and only exchanges the same JSON state objects.

## Current Implementation

- `F9` spawns one puppet actor near the local player.
- The ASI stores only that puppet handle.
- The ASI reads `remote_player_state.json` once per second.
- If the remote state is valid and fresh, the ASI moves the puppet toward the remote position.
- If the puppet is farther than `snap_distance`, it snaps to the remote position.
- If the puppet is within `snap_distance`, it lerps by `lerp_percent`.
- If the remote state is stale for more than `stale_ms`, the puppet stops updating.

## Config

```ini
[link]
link_enabled=true
write_local_state=true
read_remote_state=true
puppet_sync_enabled=true
write_interval_ms=1000
read_interval_ms=1000
stale_ms=10000
snap_distance=12
lerp_percent=35
```

## Marker Status

Default marker mode is log-only:

```ini
[puppet]
puppet_marker_mode=log
puppet_blip_enabled=false
puppet_name_label_enabled=false
```

Blip and overhead labels are still gated because they need separate crash-safe validation.

## Known Limits

- Puppet movement uses teleport-style native updates for the owned puppet. It does not yet use AI follow/pathing.
- No animation mirroring yet.
- No chat or actions yet.
- UDP is external-relay-only; no sockets run inside the ASI yet.
- No actor deletion native is used. `Backspace` releases/hides the tracked puppet.
