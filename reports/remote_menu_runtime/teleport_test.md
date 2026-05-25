# Code RED Remote Menu Teleport Targeted Smoke Test

Generated: 2026-05-23T23:08:09

## Input Attempt
```text
app_activate=True
sent_keys=F5, F6, F6
```

## Event Viewer Check
```text
(no matching Application Error/Windows Error Reporting event found during teleport-only smoke window)
```

## codered_remote_menu.log Tail
```text
[2026-05-23 23:05:31] ASI attached: Code RED Remote Menu
[2026-05-23 23:05:31] Registration worker started
[2026-05-23 23:05:31] Config loaded: probe_only=1 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:05:31] ScriptHookRDR.dll found
[2026-05-23 23:05:31] Registration succeeded; Remote Menu hotkeys active after startup_delay_ms=30000
[2026-05-23 23:06:01] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:06:01] Config loaded: probe_only=1 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:06:03] Menu opened
[2026-05-23 23:06:11] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:06:17] Soul Stealer armed: press E near an NPC
[2026-05-23 23:06:21] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:06:26] Menu closed
[2026-05-23 23:06:27] Menu opened
[2026-05-23 23:06:28] Saved teleport slot 0: 370.42, 0.00, 103.40 heading=170.90
[2026-05-23 23:06:28] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:29] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:30] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:31] Soul Stealer armed: press E near an NPC
[2026-05-23 23:06:31] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=370.42,0.00,103.40 status=stub_only
[2026-05-23 23:06:32] Soul Stealer ProbeOnly captured actor=3256 distance=1.45 pos=363.50,0.00,103.40
[2026-05-23 23:06:32] Ghost blip stub: name=Remote Player source=captured_actor pos=363.77,0.00,103.51 status=stub_only
[2026-05-23 23:06:33] Soul Stealer cancelled
[2026-05-23 23:06:33] Ghost blip stub: name=Remote Player source=captured_actor pos=363.46,0.00,103.71 status=stub_only
[2026-05-23 23:06:34] Ghost blip stub: name=Remote Player source=captured_actor pos=362.63,0.00,103.94 status=stub_only
[2026-05-23 23:06:35] Ghost blip stub: name=Remote Player source=captured_actor pos=361.50,0.00,104.21 status=stub_only
[2026-05-23 23:06:36] Ghost blip stub: name=Remote Player source=captured_actor pos=360.46,0.00,104.57 status=stub_only
[2026-05-23 23:06:37] Ghost blip stub: name=Remote Player source=captured_actor pos=359.48,0.00,105.01 status=stub_only
[2026-05-23 23:06:38] Ghost blip stub: name=Remote Player source=captured_actor pos=358.19,0.00,105.49 status=stub_only
[2026-05-23 23:06:39] Ghost blip stub: name=Remote Player source=captured_actor pos=356.55,0.00,106.18 status=stub_only
[2026-05-23 23:06:40] Ghost blip stub: name=Remote Player source=captured_actor pos=354.20,0.00,106.93 status=stub_only
[2026-05-23 23:06:41] Soul Stealer armed: press E near an NPC
[2026-05-23 23:06:41] Ghost blip stub: name=Remote Player source=captured_actor pos=351.89,0.00,107.67 status=stub_only
[2026-05-23 23:06:42] Ghost blip stub: name=Remote Player source=captured_actor pos=350.56,0.00,107.99 status=stub_only
[2026-05-23 23:07:05] ASI attached: Code RED Remote Menu
[2026-05-23 23:07:05] Registration worker started
[2026-05-23 23:07:05] Config loaded: probe_only=1 max_capture_distance=35.0 fallback=0 real_blip=0 interval=1000 startup_delay_ms=30000 name=Remote Player
[2026-05-23 23:07:05] ScriptHookRDR.dll found
[2026-05-23 23:07:05] Registration succeeded; Remote Menu hotkeys active after startup_delay_ms=30000
[2026-05-23 23:07:35] Ghost blip stub: name=Remote Player status=stub_only reason=no_captured_actor_or_saved_slot
[2026-05-23 23:07:36] Saved teleport slot 0: 358.77, 0.00, 103.48 heading=-151.24
[2026-05-23 23:07:36] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,103.48 status=stub_only
[2026-05-23 23:07:37] Teleported player to slot 0: 358.77, 0.00, 103.48 heading=-151.24
[2026-05-23 23:07:37] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,103.48 status=stub_only
[2026-05-23 23:07:38] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,103.48 status=stub_only
[2026-05-23 23:07:39] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,103.48 status=stub_only
[2026-05-23 23:07:40] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,103.48 status=stub_only
[2026-05-23 23:07:41] Saved teleport slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:07:41] Teleported player to slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:07:41] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:42] Menu opened
[2026-05-23 23:07:42] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:43] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:44] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:45] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:46] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:47] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:48] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:50] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:51] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:51] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:52] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:53] Menu closed
[2026-05-23 23:07:53] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:54] Menu opened
[2026-05-23 23:07:55] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:55] Teleported player to slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:07:55] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:57] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:57] Teleported player to slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:07:57] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:58] Saved teleport slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:07:59] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:07:59] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:00] Saved teleport slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:08:00] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:01] Saved teleport slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:08:01] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:02] Teleported player to slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:08:02] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:03] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:04] Teleported player to slot 0: 358.77, 0.00, 0.00 heading=-151.24
[2026-05-23 23:08:04] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:05] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:06] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:08] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
[2026-05-23 23:08:08] Ghost blip stub: name=Remote Player source=teleport_slot0 pos=358.77,0.00,0.00 status=stub_only
```
