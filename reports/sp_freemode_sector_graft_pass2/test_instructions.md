# SP FreeMode Sector Graft Pass 2 Test Instructions

Do not install all variants at once. Restore your original `game\content.rpf` between tests.

1. Test `A0_pass2_repack_control.rpf` first. Expected: normal single-player boot, no visible content change.
2. Test `A1_pass2_callsite_noop_control.rpf`. Expected: normal single-player boot, no visible content change.
3. Test `A2_tes_single_sector.rpf`. Expected: normal single-player boot; inspect TES/Tumbleweed area for changed streaming or sector visibility.
4. Test `A4_tes_small_set.rpf` only if A2 boots. Expected: broader TES-sector streaming attempt, still no MP mode launch.

Crash at A0/A1 means RPF/WSC repack is unsafe. Crash only at A2/A4 means the selected sector graft slot or TES target is the likely cause.
