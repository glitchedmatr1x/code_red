# Code RED Peer Clone Sync v0.2

Public test package for a two-PC Code RED clone-sync relay.

Read first from the repo root:

```text
READ_FIRST_CodeRED_Peer_Clone_Sync_v0_2_PUBLIC_TEST.txt
```

Or read the local package copy:

```text
READ_FIRST_PUBLIC_TEST.txt
```

This package only proves connection/state relay. The next phase is the in-game bridge that spawns and moves the remote clone actor.

## Quick local proof

```bat
Run_SelfTest.bat
```

Expected:

```text
# Selftest result: PASS
player_a saw player_b: True
player_b saw player_a: True
```

## Two-PC proof

Host PC:

```bat
Run_Doctor.bat
Run_Relay_Host.bat
Run_Mock_Client_A.bat
```

Client PC:

```bat
Run_Client_B_To_Host.bat
```

Use Player A's LAN/VPN IP when prompted. Do not use `127.0.0.1` unless both clients are on the same machine.
