# MP Converted Runtime Probe Pass 1 Test Matrix

Use one cloned RPF at a time. Restore the known-good content.rpf between tests.

| Variant | Path | Layers | Primary signal | Failure meaning |
|---|---|---|---|---|
| A_converted_wsc_tree_only | `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\A_converted_wsc_tree_only.rpf` | converted XENON->PC WSC tree only | game boots with no menu regression | bad converted resource import if boot crash |
| B_converted_plus_pressstart_D | `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\B_converted_plus_pressstart_D.rpf` | A only; pressstart_D_full_force unavailable | press start or initial online/menu route changes | pressstart layer if B differs from A; otherwise same as A |
| C_converted_plus_core_D | `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\C_converted_plus_core_D.rpf` | B + main/main_z no_autosave->xmlsave WSC patches | core save/profile gate behavior changes | main/main_z patch if C differs from B |
| D_full_runtime_probe | `D:\Games\Red Dead Redemption\Code_RED\build\mp_converted_runtime_probe_pass1\D_full_runtime_probe.rpf` | C only; no explicit savegame/savegame2/netstats bypass artifacts available | net.EnterOnline/loading/freemode route advances past prior prompt | converted backend runtime if crash only after MP entry |
