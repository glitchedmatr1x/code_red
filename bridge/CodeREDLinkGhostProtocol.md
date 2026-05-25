# Code RED Link Ghost/Puppet Protocol Draft

This is the future pseudo-coop lane that sits on top of Soul Stealer actor control.

## First milestone: Ghost Blip

Each external client sends a small state packet:

```json
{
  "playerId": "p2",
  "displayName": "Remote Player",
  "timestampMs": 123456789,
  "position": { "x": 100.0, "y": 200.0, "z": 30.0 },
  "heading": 180.0,
  "speed": 3.5,
  "flags": { "running": true, "aiming": false, "shooting": false, "mounted": false, "inVehicle": false },
  "chat": ""
}
```

The ASI/plugin uses `RemotePuppetBlip` to create/update one in-game blip named after the remote player.

## Second milestone: Puppet NPC

When the local player has a bound puppet actor:

- update remote blip every packet
- soft-sync puppet actor toward remote position
- snap puppet only if distance error is too large
- use heading to orient the puppet

## Third milestone: Text chat

Chat can start outside the game as a small client window. Later the ASI can call an on-screen message native when available.

## Native requirements

Minimum blip support:

- create coordinate blip
- update coordinate blip
- remove blip
- optional set name/icon/color

Minimum puppet support:

- set actor position
- set actor heading
- clear tasks / prevent AI from fighting sync
