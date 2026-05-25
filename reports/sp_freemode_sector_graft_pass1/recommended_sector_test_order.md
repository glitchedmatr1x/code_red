# Recommended Sector Test Order

Do not enter multiplayer and do not launch MP scripts. Test one cloned RPF at a time.

## First Choices

1. `mp_tes_coop01ax` from `release64/pressstart.wsc` risk=`low` region=`tes`
2. `mp_tes_coop01bx` from `release64/pressstart.wsc` risk=`low` region=`tes`
3. `mp_tes_coop01cx` from `release64/pressstart.wsc` risk=`low` region=`tes`
4. `mp_tes_coop02x` from `release64/pressstart.wsc` risk=`low` region=`tes`
5. `mp_tes_base01x` from `release64/pressstart.wsc` risk=`low` region=`tes`
6. `mp_gap_mineLid01x` from `release64/pressstart.wsc` risk=`low` region=`gap`
7. `mp_fom_coop01x` from `release64/pressstart.wsc` risk=`low` region=`fom`
8. `mp_fom_burntDebris01x` from `release64/pressstart.wsc` risk=`low` region=`fom`
9. `mp_wld_base03x` from `release64/pressstart.wsc` risk=`low` region=`wld`
10. `mp_nos_coop01ax` from `release64/pressstart.wsc` risk=`low` region=`nos`
11. `mp_nos_coop01bx` from `release64/pressstart.wsc` risk=`low` region=`nos`
12. `mp_nos_coop01cx` from `release64/pressstart.wsc` risk=`low` region=`nos`

## Variant Intent

- A0: repack control only, no content changes.
- A1: SP WSC no-op/log probe only if a safe authoring slot is available.
- A2: enable exactly one MP sector, recommended first candidate above.
- A3: enable one MP sector and disable one reviewed SP counterpart.
- A4: enable 2-4 same-region MP sectors only after A2/A3 are stable.
- A5: marker/action-area only after sector visibility is proven.
