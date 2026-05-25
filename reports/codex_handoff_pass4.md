# Codex Handoff: Soul Stealer Pass 4

## Goal

Wire the Pass 4 source package into the local Code RED ScriptHook/ASI project.

## New features needing native hookup

### Teleports

Wire:

- `INativeBridge::getActorPos`
- `INativeBridge::getActorHeading`
- `INativeBridge::setActorPos`
- `INativeBridge::setActorHeading`

Then test F5/F6 slot behavior.

### Remote blip

Wire:

- `INativeBridge::createCoordBlip`
- `INativeBridge::updateCoordBlip`
- `INativeBridge::setBlipLabel`
- `INativeBridge::removeBlip`

Start with a fixed coordinate blip. Do not attempt UDP/networking until the local blip appears and updates.

### Remote puppet actor

Once blip works:

- bind a selected/possessed actor as the remote puppet
- feed `RemotePuppetController::updateRemoteState(...)`
- test `snapActorToRemote()` first
- test `softSyncActorToRemote()` after snap works

## Do not do yet

- Do not port the old PS3 trainer CSC.
- Do not touch live `content.rpf`.
- Do not add GameSpy/MP dependencies.
- Do not enable online behavior.

## First runtime test path

1. Compile ASI.
2. Launch offline single-player.
3. Verify F8/F9 Soul Stealer still works.
4. Press F5 to save teleport slot 0.
5. Move, press F6 to restore position.
6. Create a fixed test blip from ASI init or debug hotkey.
7. Update the blip position in a slow circle.
8. Remove blip on unload.
