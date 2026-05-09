# Code RED MP RakNet PoC

Minimal RakNet-based multiplayer skeleton for Code RED / RDR experiments.

This is intentionally small and separate from the current ScriptHook ASIs:

- `codered-mp-server`: standalone RakNet server skeleton.
- `codered-mp-client`: standalone client-side network stack harness.
- `codered_mp_client_stack`: reusable client-side stack for a later ASI bridge.
- `codered_mp_protocol`: shared packet IDs and BitStream helpers.

It is not official RDR multiplayer, does not edit RPF archives, and does not hook
the game yet. The shape follows the SA-MP-style RakNet 2.52 flow:

```text
RakNetworkFactory::GetRakServerInterface()
-> Start(maxPlayers, ..., port, bindAddress)
-> Receive() packet loop
-> ID_NEW_INCOMING_CONNECTION / ID_DISCONNECTION_NOTIFICATION
-> user packets with ID_USER_PACKET_ENUM
```

## Build

The CMake project expects the local RakNet tree from the SA-MP rebuild:

```bash
toolbox run --container devbuild cmake -S related_apps/CodeRED_MP_RakNet_PoC -B related_apps/CodeRED_MP_RakNet_PoC/build
toolbox run --container devbuild cmake --build related_apps/CodeRED_MP_RakNet_PoC/build
```

Override the RakNet path if needed:

```bash
CODE_RED_RAKNET_ROOT=/path/to/raknet-knogle cmake -S related_apps/CodeRED_MP_RakNet_PoC -B related_apps/CodeRED_MP_RakNet_PoC/build
```

## Smoke Test

Terminal A:

```bash
./related_apps/CodeRED_MP_RakNet_PoC/build/codered-mp-server --port 7777
```

Terminal B:

```bash
./related_apps/CodeRED_MP_RakNet_PoC/build/codered-mp-client --host 127.0.0.1 --port 7777 --name marston
```

The client sends a join request, periodic player state, and chat. The server
assigns a small player id and broadcasts snapshots.

## Script Execution Stub

The server owns a tiny `ScriptHostStub` with callbacks:

- `OnGameModeInit`
- `OnPlayerConnect`
- `OnPlayerDisconnect`
- `OnPlayerUpdate`
- `OnPlayerText`

That is the intended seam for a later Pawn/AMX loader. No Pawn VM is embedded in
this first skeleton.
