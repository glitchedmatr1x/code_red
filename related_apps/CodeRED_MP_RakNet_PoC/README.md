# Code RED MP SLikeNet PoC

Minimal SLikeNet-based multiplayer skeleton for Code RED / RDR experiments.

This is intentionally small and separate from the current ScriptHook ASIs:

- `codered-mp-server`: standalone SLikeNet server skeleton.
- `codered-mp-client`: standalone client-side network stack harness.
- `codered_mp_client_stack`: reusable client-side stack for a later ASI bridge.
- `codered_mp_protocol`: shared packet IDs and BitStream helpers.

It is not official RDR multiplayer, does not edit RPF archives, and does not hook
the game simulation yet. The network layer uses SLikeNet directly:

```text
SLNet::RakPeerInterface::GetInstance()
-> Startup(maxPlayers, socketDescriptors, ...)
-> SetMaximumIncomingConnections(maxPlayers)
-> Receive() packet loop
-> ID_NEW_INCOMING_CONNECTION / ID_DISCONNECTION_NOTIFICATION
-> user packets with ID_USER_PACKET_ENUM
```

## Build

The CMake project vendors SLikeNet as a submodule under
`third_party/slikenet`. The embedded build intentionally excludes SLikeNet's
optional OpenSSL crypto sources so the PoC stays self-contained.

The server also embeds the open.mp/CompuPhase Pawn AMX runtime. By default the
CMake project uses the local open.mp checkout at
`/home/chairman/Projects/omp-ipv6/open.mp/lib/pawn`; override
`CODE_RED_PAWN_ROOT` if that tree moves.

```bash
git submodule update --init related_apps/CodeRED_MP_RakNet_PoC/third_party/slikenet
cmake -S related_apps/CodeRED_MP_RakNet_PoC -B related_apps/CodeRED_MP_RakNet_PoC/build
cmake --build related_apps/CodeRED_MP_RakNet_PoC/build
```

For a Windows client executable usable from the Wine-loaded ASI menu:

```bash
cmake -S related_apps/CodeRED_MP_RakNet_PoC -B related_apps/CodeRED_MP_RakNet_PoC/build-win64 -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++
cmake --build related_apps/CodeRED_MP_RakNet_PoC/build-win64
```

## Pawn Gamemode

The PoC now has an open.mp-style Pawn layout:

- `qawno/include/codered_mp.inc`
- `gamemodes/codered_hello.pwn`
- `scripts/build_pawn.sh`

Build the AMX with:

```bash
cd related_apps/CodeRED_MP_RakNet_PoC
./scripts/build_pawn.sh
```

The basic include exposes:

- `print`
- `SetGameModeText`
- `SendClientNativeCall`
- `OnGameModeInit`
- `OnGameModeExit`
- `OnPlayerConnect`
- `OnPlayerDisconnect`
- `OnPlayerText`

## Smoke Test

Terminal A:

```bash
cd related_apps/CodeRED_MP_RakNet_PoC
./build/codered-mp-server --port 7777 --gamemode gamemodes/codered_hello.amx
```

Terminal B:

```bash
./related_apps/CodeRED_MP_RakNet_PoC/build/codered-mp-client --host 127.0.0.1 --port 7777 --name marston
```

The client sends a join request, periodic player state, and chat. The server
assigns a small player id, runs Pawn `OnPlayerConnect`, and the Pawn script
sends `client_hello_world: Hello from Code RED Pawn gamemode` through
`SendClientNativeCall`.

## ASI Menu Hook

The existing ScriptHookRDR AI menu has a `Connect MP Localhost` action. It
starts `codered-mp-client.exe --host 127.0.0.1 --port 7777 --name rdr_asi` from
the game directory, writes `scratch/codered_mp_connect_request.json`, and passes
`--status scratch/codered_mp_client_status.json` so the menu can show
`connected`, `joined`, and `native_call` status updates instead of only the
process-start result.
