# CodeRED Peer Companion Install

Copy these files beside `RDR.exe`:

- `CodeRED_PeerCompanion.asi`
- `CodeRED_Peer_App.py`
- `CodeRED_Link_Server.py`
- `data/codered/peer_companion.ini`

Do not install other trainers for the first test. This pass does not need
`content.rpf`, WSC, SCXML, GameSpy, or official multiplayer changes.

The ASI writes:

- `logs/codered_peer_companion.log`
- `data/codered/link/host_status.json`
- `data/codered/link/peer_command_last_consumed.json`

The peer app/server writes:

- `data/codered/link/peer_command_inbox.json`
- `data/codered/link/peer_log.txt`

Rollback is removing `CodeRED_PeerCompanion.asi` from the game root. The Python
files and `data/codered` files are inert without the ASI loaded.
