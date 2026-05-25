# Code RED Soul Stealer Reconstruction Pass 4

## Scope

Pass 4 adds two requested extensions before Windows ASI/native integration:

1. Teleport options for the Soul Stealer runtime.
2. Radar/map blip scaffolding for a future remote-controlled NPC / Code RED Link puppet.

This pass still does not touch live `content.rpf`, does not port the old PS3 trainer, and does not require WSC patching.

## New source modules

- `TeleportManager.h/.cpp`
  - save player position into slots
  - teleport player to saved slot
  - teleport player to actor
  - teleport actor to player
  - teleport arbitrary actor to position/heading

- `RemotePuppetBlip.h/.cpp`
  - create/update/remove a coordinate blip for a remote player state
  - bridge methods are abstract until Codex wires real RDR blip natives

- `RemotePuppetController.h/.cpp`
  - owns a remote blip
  - can bind one controlled actor as the remote puppet
  - can soft-sync or snap that actor to remote coordinates
  - can teleport the puppet actor back near the local player

## NativeBridge additions

The bridge now asks Codex/local integration to provide:

```cpp
createCoordBlip(Vec3 pos, const std::string& label, int icon, int color)
updateCoordBlip(BlipHandle blip, Vec3 pos, float heading)
setBlipLabel(BlipHandle blip, const std::string& label)
removeBlip(BlipHandle blip)
```

These are intentionally abstract because the exact RDR PC native names/hashes still need local ScriptHook/Code RED wiring.

## Hotkeys reserved

- F5: save teleport slot 0
- F6: teleport player to slot 0
- F7: teleport controlled remote puppet actor to player
- F8: toggle Soul Stealer armed mode
- E: capture target
- Backspace: cancel possession
- F9: debug dump
- F10: reload request

## Mock validation

Compiled and ran:

- `soul_stealer_mock_test`
- `soul_stealer_runtime_test`
- `soul_stealer_pass4_test`

All tests passed in the sandbox.
