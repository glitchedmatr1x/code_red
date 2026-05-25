# Code RED MP Freeroam Pass 3 Build Report

## Output

- Drop-in package: `D:\Games\Red Dead Redemption\Code_RED\build\mp_freeroam_pass3\dropin_import_ready`
- RPF output: not written in this pass.

## Why this is a drop-in package

The current RPF overlay path is proven for full MP raw file adds and for replacing
existing resource entries.  Adding the new `codered_mp_bootstrap_minimal.wsc` as a
brand-new WSC resource entry is still risky because new WSC entries may not inherit
the correct resource-entry flags.  This pass therefore produces the allowed
import-ready folder instead of a cloned RPF.

## Included Pieces

- Full Pass 4 restored MP directory under `content/release64/multiplayer/`.
- Full Pass 4 restored MP directory under `content/release/multiplayer/`.
- Pass 5 combined XML route for `pausemenuscene.sc.xml` and `networking.sc.xml`.
- Pass 4 variant 02 LAN menu XML route for `net/lanmenu.sc.xml`.
- Pass 2 patched `long_update_thread.wsc`.
- Pass 1 generated `codered_mp_bootstrap_minimal.wsc`.

## Counts

- Total files staged: `261`
- By component: `{'mp_restore': 256, 'wsc_bootstrap': 2, 'xml_route': 3}`
- MP extension counts: `{'release64:(no_ext)': 27, 'release64:.csc': 45, 'release64:.xsc': 56, 'release:(no_ext)': 27, 'release:.csc': 45, 'release:.xsc': 56}`

## Safety

- Original `game/content.rpf` was not modified.
- No public-server spoofing or public matchmaking patch is included.
- No default auth bypass is included.
- No optional sector/catacombs patch is included because Pass 5 did not validate a safe sector edit.
- This build does not depend on a nonexistent `multiplayer_update_thread.wsc`; it imports raw donor `.csc`/`.xsc` variants and starts from the normal PC `long_update_thread.wsc` hook.
