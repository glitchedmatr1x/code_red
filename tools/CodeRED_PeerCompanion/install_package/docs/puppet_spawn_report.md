# Puppet Spawn Report

Pass 1 implements one Code RED-owned companion actor.

Spawn path:

1. F8 or `spawn_companion` command requests a companion.
2. ASI validates the player actor.
3. ASI reads player position and heading.
4. ASI finds or creates layout `CodeREDPeerCompanion`.
5. ASI calls `CREATE_ACTOR_IN_LAYOUT` with `companion_actor_enum`.
6. ASI clears tasks and puts the actor in stand-still idle.

Default actor enum:

`369`

Safety gates:

- no spawn on startup
- no vehicle actor enum range for Pass 1
- no actor scanning
- no Soul Stealer possession
- no delete/kill target actor behavior
- Backspace and F9 both run companion cleanup

Peer commands are ignored until F11 enables peer-control mode.
