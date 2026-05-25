# Code RED Remote Menu Puppet Spawn Report

Status: implemented, build verified, runtime F9 test pending.

Hotkeys:
- `F9`: spawn one Code RED-owned puppet actor 4 meters in front of the player.
- `Backspace`: release the tracked puppet. This clears tasks and hides it if configured; it does not call a delete/despawn native.
- `F10`: move puppet back near the player, but blocked by default with `puppet_move_enabled=false`.

Config:

```ini
[puppet]
puppet_spawn_enabled=true
puppet_marker_mode=log
puppet_blip_enabled=false
puppet_name_label_enabled=false
puppet_actor_enum=111
puppet_marker_update_ms=5000
puppet_move_enabled=false
puppet_hide_on_release=true
```

Native path:
- `FIND_NAMED_LAYOUT("CodeRED_Remote_Menu_Layout")`
- `CREATE_LAYOUT("CodeRED_Remote_Menu_Layout")` if no layout is found
- `CREATE_ACTOR_IN_LAYOUT(layout, "codered_remote_puppet_NNN", puppet_actor_enum, position, heading)`
- `SET_ACTOR_HEADING` after spawn

Safety notes:
- This does not reuse Soul Stealer.
- This does not scan all actors.
- This stores only the single puppet handle created by Code RED.
- Older Code RED notes mark raw `CREATE_ACTOR_IN_LAYOUT` as crash-sensitive, so test this alone with overlay, actor scanning, and teleport writes still disabled.

Expected runtime proof lines:

```text
Puppet spawn attempt: layout=<id> name=codered_remote_puppet_001 enum=111 ...
Puppet spawned actor=<handle> enum=111 pos=<x>,<y>,<z> heading=<heading>
```
