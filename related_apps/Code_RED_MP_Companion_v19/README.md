# Code RED Multiplayer Companion v19

This bundle is the standalone player-facing multiplayer companion export.

## What it does
- lets players choose `content.rpf` from anywhere, not just from a guessed game directory
- shows the requested world target and boot route explicitly
- creates host/join descriptors, invite codes, LAN discovery, chat/presence sync, trainer prep, and voice-ready prep
- backs up and patches `content.rpf` without opening the full Code RED workbench
- builds temporary **HotSwap** derivatives for `content.rpf` by default or any selected `.rpf` before launch
- installs a **Red Bridge** launcher pack into the game root when requested

## Red Bridge
Red Bridge is the game-directory bridge layer used by the launcher pack, runtime bridge, and future hook consumer path.

Included guidance now covers:
- `Red_Bridge_Guide.txt`
- `Code_RED_External_Recommendations.txt`
- `Code_RED_Dependency_Installer.py/.bat/.ps1`

## Important honesty note
The companion can now show and export the intended world target and boot route.
The currently recovered production route is still strongest around recovered LAN / Private / Public / Freemode taskmachine paths, but in-engine activation is still not fully proven.

## External dependency note
- **RedHook is not bundled** and remains third-party
- **ScriptHookRDR is also external**
- because hook stacks may conflict, test one strategy at a time instead of assuming both should run together

## Install
1. Copy this folder into the game directory, or anywhere convenient.
2. Run `mp_companion.py` with Python 3.11+.
3. Either detect `content.rpf` from a game directory or use **Choose content.rpf** to point at it from anywhere.
4. Create a backup before applying patches.
5. Choose a target `.rpf` for HotSwap if you want something other than `content.rpf`.
6. Use **Build HotSwap Copy** or **Activate HotSwap** to stage overrides safely.
7. Use **Validate Boot Route** and **Install Main-Dir Pack** when you are ready to stage the bridge into the game root.

GLITCHED MATRIX Prototype Lab made this possible.


## Ghost RPF
Built-in runtime authoring targets the known content.rpf menu/taskmachine/hud files and generates a temporary derivative before launch.


## v19 notes
- Auto disables conflicting hook files before launch when mixed hook stacks are detected.
- Restores parked hook files when the companion closes.
- Clarifies that Target RPF means the original game archive to clone and temporarily replace before launch.

- Ghost RPF swap now retries automatically when Windows reports Access Denied.
- Swap/restore messaging now makes it clear that the target RPF is the live game archive being temporarily replaced.
