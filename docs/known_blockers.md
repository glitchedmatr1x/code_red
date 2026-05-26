# Code RED Remote Menu Known Blockers

- Real possession is not enabled yet. `SwapPlayerToActor`, player-control transfer, model swap, and camera ownership natives still need verified hashes and calling conventions.
- Real blip creation is stubbed. This build logs and displays the intended `Remote Player` position rather than creating a map icon.
- Actor capture is disabled by default because the first ProbeOnly run reached a live actor and then the user's runtime crashed. Re-enable only with `actor_scan_enabled=true` after a safer scanner is implemented.
- Teleport write is disabled by default because the first smoke test showed unsafe coordinate behavior. `F5` read/log can stay on, but `F6` is blocked unless `teleport_write_enabled=true`.
- Overlay drawing is disabled by default because the menu/cursor interfered with gameplay. The ASI now runs log-only unless `overlay_enabled=true`.
- Puppet spawn is available behind `puppet_spawn_enabled=true`, but it uses the same `CREATE_ACTOR_IN_LAYOUT` family that older Code RED menu notes marked crash-sensitive. Test it alone, with Soul Stealer and overlay still disabled.
- Puppet markers default to log-only. Real blip and overhead label modes stay disabled because those native paths are not yet proven crash-safe in this ASI.
- `Backspace` hides/releases the tracked puppet and removes any tracked blip if one was created. No actor delete/despawn native is called yet.
- This pass intentionally excludes world/child sector toggles.
