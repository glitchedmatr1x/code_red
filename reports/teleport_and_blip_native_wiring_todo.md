# Teleport + Remote Blip Native Wiring TODO

## Teleport natives to locate/wire

Required or equivalent:

- get local player actor
- get actor position
- get actor heading
- set actor position
- set actor heading

Optional improvements:

- ground Z / safe coord resolver
- streaming/load area request before teleport
- soft fade before/after teleport
- vehicle/mount aware teleport

## Blip natives to locate/wire

Required or equivalent:

- create blip at coordinates
- update blip position
- remove blip

Helpful optional natives:

- set blip name/text
- set blip color
- set blip icon/sprite
- show/hide on minimap vs full map
- set route/scale/flashing

## Why blips matter

A moving remote blip is the lowest-risk pseudo-coop milestone:

remote player position -> Code RED Link packet -> local RDR blip update

No GameSpy, no MP session, no actor control needed.

## Safe test order

1. Create fixed coordinate blip near player.
2. Update blip every tick with a scripted circle/path.
3. Remove blip cleanly on unload.
4. Update blip from a local JSON/UDP remote player state.
5. Only after blip works, bind an NPC actor and soft-sync it to that remote state.
