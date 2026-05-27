# Code RED Game Root Cleanup - 2026-05-06

Moved the misplaced Peer Clone Sync public test package out of the game root and into:

$dest = D:\Games\Red Dead Redemption\Code_RED\related_apps\CodeRED_Peer_Clone_Sync_v0_2

This preserves useful code and runtime logs while removing regressed launchers/docs from beside `RDR.exe`.

Kept runtime files needed beside `RDR.exe`:

- `CodeRED_AI_Menu.asi`
- `CodeRED_AI_Menu.ini`
- `data/codered/`
- `scratch/`
- `ScriptHookRDR.dll`
- `dinput8.dll`

Manifest:

$manifest = D:\Games\Red Dead Redemption\Code_RED\logs\CodeRED_GameRoot_Cleanup_2026-05-06.json
