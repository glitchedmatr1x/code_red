# MP Converted Runtime Probe Pass 1

No live game files were modified. All outputs are cloned RPF variants.

- Base RPF: `D:\Games\Red Dead Redemption\Code_RED\build\mp_content_restore_pass5\content_mp_restore_pass5_access_trainer_sectors.rpf`
- Converted WSC tree: `D:\Games\Red Dead Redemption\Code_RED\build\mp_script_conversion_probe\import_ready_xsc_converted_wsc`

## Variants

### A_converted_wsc_tree_only
- Path: `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\A_converted_wsc_tree_only.rpf`
- SHA1: `24C859F7E9EE3E825C43558890C889763434C2A1`
- Layers: converted XENON->PC WSC tree only
- Entry count: `2079`
- Converted MP WSC count: `113`

### B_converted_plus_pressstart_D
- Path: `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\B_converted_plus_pressstart_D.rpf`
- SHA1: `24C859F7E9EE3E825C43558890C889763434C2A1`
- Layers: A only; pressstart_D_full_force unavailable
- Entry count: `2079`
- Converted MP WSC count: `113`

### C_converted_plus_core_D
- Path: `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\C_converted_plus_core_D.rpf`
- SHA1: `04066D38143A9537FA0B4967D67A1FC75E9A108E`
- Layers: B + main/main_z no_autosave->xmlsave WSC patches
- Entry count: `2079`
- Converted MP WSC count: `113`

### D_full_runtime_probe
- Path: `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\D_full_runtime_probe.rpf`
- SHA1: `04066D38143A9537FA0B4967D67A1FC75E9A108E`
- Layers: C only; no explicit savegame/savegame2/netstats bypass artifacts available
- Entry count: `2079`
- Converted MP WSC count: `113`

## Warnings

- pressstart_D_full_force artifact was not found; B/C/D record this as unavailable and do not synthesize a fake patch
- no explicit known-safe savegame/savegame2/netstats XML bypass candidates were found; D does not add an auth or PlayMpConf experiment

## Runtime Interpretation

- Crash on boot: bad import path/resource wrapper.
- Crash only after online/MP entry: converted MP script runtime issue or frontend successfully reached backend.
- No behavior change: frontend route still does not reach converted MP scripts.
- Changed prompt/loading/menu behavior: keep that variant as the next base and isolate the next gate.
