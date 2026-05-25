# MP Bootstrap Pass 2 Patch Report

Goal: route a normal PC update-thread script launch path to the CodeRED MP bootstrap WSC without bytecode growth.

## Strategy

- Strategy A, add a new launch block: blocked in this pass because general WSC bytecode growth/rebuild is not proven.
- Strategy B, same-length script path replacement: used.
- Strategy C, direct MP backend path replacement: not used in the default output.

## Patch

- Source update thread: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\release64\scripting\designerdefined\long_update_thread.wsc`
- Patched update thread: `D:\Games\Red Dead Redemption\Code_RED\build\mp_bootstrap_pass2\dropin\content\release64\scripting\designerdefined\long_update_thread.wsc`
- Original path: `$/content/scripting/DesignerDefined/Traffic/trafficDebugThread`
- Replacement path: `content/scripting/DesignerDefined/codered_mp_bootstrap_minimal`
- Replacement length: `62` bytes
- Reopen validation: `True`
- Same decoded size: `True`
- Same output size: `True`

## Drop-In Folder

- `D:\Games\Red Dead Redemption\Code_RED\build\mp_bootstrap_pass2\dropin`

## Runtime Boundary

The patch redirects the existing `trafficDebugThread` script path slot. It proves a same-size WSC route to the bootstrap; runtime execution still depends on the original update-thread branch that launches that slot.
