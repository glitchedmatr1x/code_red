# Code RED Peer Clone Sync v0.2

Public test package for the simplest possible two-PC Code RED connection proof.

Read this first:

```text
READ_FIRST_PUBLIC_TEST.txt
```

## What this does

This package runs a tiny relay host and two test clients. It proves that two PCs can exchange local player state that a future in-game bridge can use to spawn and move clone actors.

## What this does not do yet

- It does not restore official multiplayer.
- It does not create a real lobby.
- It does not edit game archives.
- It does not need to be installed in the game folder.

## Fast local test

```bat
Run_SelfTest.bat
```

Expected:

```text
# Selftest result: PASS
player_a saw player_b: True
player_b saw player_a: True
```

## Two-PC test

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

Use Player A's LAN/VPN IP when prompted.

## Default port

```text
47666/tcp
```

## Next phase after this passes

Build the game bridge/plugin:

```text
read local player position/heading
send state to relay
receive remote state
spawn remote clone actor
move clone actor toward remote state
```
