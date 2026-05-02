Code RED Faction War Drop-In RPF Pass 03
========================================

This package gives you patched RPF copies instead of loose bridge fragments.

Install/Test:
1. Back up your original content.rpf and tune_d11generic.rpf.
2. Use DROP_IN_SAFE_FIRST first. Copy its content.rpf and tune_d11generic.rpf to the same mod/game location where your current test setup loads those files.
3. Ride through Armadillo, Ridgewood Farm, Twin Rocks, Fort Mercer, Thieves Landing, and nearby roads.
4. If SAFE boots, try DROP_IN_EXPERIMENTAL_MORE_WORLD_PRESSURE for stronger traffic/event pressure.

SAFE changes:
- Patches tune game_main.tr with inline Faction War AI behavior bridge.
- Patches content game_main.tr with inline Faction War AI behavior bridge.
- Raises level.pop pressure at faction-war hotspots using existing stock syntax.
- Loosens content ambient event placement distances using existing XML fields.

EXPERIMENTAL adds:
- Patches default.traffic with route profile records for roadblocks, outlaw trails, smuggler lanes, and raider corridors.
- Makes remote ambient event placement more permissive.

Security note: no EXE/DLL/LIB/BAT/CMD/PS1/.red binaries are included.

Patch details:

DROP_IN_SAFE_FIRST
- tune level.pop: payload 11180 -> 11130, slot 1346 -> 1335, relocated=False, codec=zstd-18
- content ambient: payload 7356 -> 7356, slot 929 -> 927, relocated=False, codec=zstd-18
- tune game_main.tr: payload 128689 -> 130393, slot 27878 -> 30217, relocated=True, codec=zstd-9
- content game_main.tr: payload 47117 -> 48428, slot 12520 -> 12806, relocated=True, codec=zstd-18

DROP_IN_EXPERIMENTAL_MORE_WORLD_PRESSURE
- tune level.pop: payload 11180 -> 11130, slot 1346 -> 1335, relocated=False, codec=zstd-18
- content ambient: payload 7356 -> 7356, slot 929 -> 928, relocated=False, codec=zstd-18
- tune default.traffic: payload 72 -> 700, slot 72 -> 700, relocated=True, codec=plain
- tune game_main.tr: payload 128689 -> 130393, slot 27878 -> 30217, relocated=True, codec=zstd-9
- content game_main.tr: payload 47117 -> 48428, slot 12520 -> 12806, relocated=True, codec=zstd-18