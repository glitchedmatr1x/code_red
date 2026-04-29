# Code RED Faction War — No-SC Menu-Free Pass 01

This folder is based on `CodeRedFactionWarV26_ReadyProject`, but the branch goal has changed:

- no SC-CL lane
- no trainer/debug menu
- no overlay-first workflow
- keep the faction-war simulation as an ambient world layer
- prepare the same design for Code RED's editable tune/content resource workflow

Start with `README_NO_SC_MENU_FREE.md`.

## Project files

- `CodeRedFactionWar_NoSC_MenuFree.sln`
- `CodeRedFactionWar_NoSC_MenuFree.vcxproj`
- `Source/CodeRedFactionWar/code_red_factionwar_plugin_v26.cpp`
- `WorldResourceBridge/`

## Runtime files created by this branch

- `CodeRedFactionWar_NoSC_MenuFree.save`
- `CodeRedFactionWar_NoSC_MenuFree.log`
- `CodeRedFactionWar_NoSC_MenuFree_factions.ini`
- `CodeRedFactionWar_NoSC_MenuFree_diagnostics.txt`
- `CodeRedFactionWar_NoSC_MenuFree_bulletin.txt`

## Note

The Visual Studio project remains a RedHook `.red` project because the original v26 runtime was built that way. The no-EXE/no-compiler direction is represented by `WorldResourceBridge/`, which is ready for the next Code RED RPF tune/content merge pass.
