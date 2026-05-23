# Code RED update-thread sector/Morningstar side analysis

## Decode status
The WSC files in `update thread - enable sectors.zip` were decrypted with the known RSC85 AES route and decompressed as Zstandard locally. `multiplayer_update_thread.xsc` was not decoded in this side pass.

| Script | Decoded size | Strings | Morningstar hits | Blackwater/BLK hits | Zombie/DLC hits |
|---|---:|---:|---:|---:|---:|
| long_update_thread_z.wsc | 196608 | 2673 | 5 | 42 | 169 |
| medium_update_thread.wsc | 143360 | 2140 | 10 | 61 | 12 |
| medium_update_thread_z.wsc | 86016 | 1488 | 10 | 71 | 263 |
| short_update_thread.wsc | 102400 | 1456 | 0 | 1 | 9 |
| short_update_thread_z.wsc | 126976 | 1576 | 0 | 1 | 71 |
| long_update_thread.wsc | 225280 | 3163 | 5 | 10 | 5 |

## Key finding
`morningStar` and the `mor_morningStar*` interior sector names are present in `medium_update_thread.wsc` and `medium_update_thread_z.wsc`, not in the decoded `short_update_thread.wsc` strings from this upload. The zombie/DLC variant also contains many `dlc_blk_*` names.

## Morningstar/Blackwater string windows
### medium_update_thread.wsc
- `054536` `dixonCrossingAfter`
- `054560` `dixonCrossingBefore`
- `054585` `rsdROAD_thi_blk_road`
- `054613` `rsdROAD_thi_blk_roaddetachedCurve2`
- `054655` `rsdGPSTRAIL_curve124`
- `054683` `rsdGPSTRAIL_curve132`
- `054714` `dixonCrossingAfter`
- `054738` `dixonCrossingBefore`
- `054763` `rsdROAD_thi_blk_road`
- `054791` `rsdROAD_thi_blk_roaddetachedCurve2`
- `054833` `rsdGPSTRAIL_curve124`
- `054861` `rsdGPSTRAIL_curve132`
- `054892` `hen_barn02x`
- `054909` `hen_barn02props01x`
- `054933` `hen_barn01x`
- `054950` `hen_barn01props01x`
- `054980` `campoMiradaAfter`
- `055002` `campoMiradaBefore`
- `055034` `fronteraBridgeAfter`
- `055059` `fronteraBridgeBefore`
- `055088` `fronteraBridgeAfter`
- `055113` `fronteraBridgeBefore`
- `055142` `fod_gates01x`
- `055160` `fod_gates02x`
- `055178` `fod_gates02Doors01x`
- `055215` `masonBridgeAfter`
- `055237` `masonBridgeBefore`
- `055263` `masonBridgeAfter`
- `055285` `masonBridgeBefore`
- `055317` `lmf_troughAfter01x`
- `055341` `lmf_troughBefore01x`
- `055369` `lmf_troughAfter01x`
- `055393` `lmf_troughBefore01x`
- `055421` `morningStar`
- `055438` `blk_barge01Props01x`
- `055463` `blk_barge01x`
- `055481` `blk_theatre_int_Props01x`
- `055511` `blk_theatre_int_01x`
- `055536` `blk_bank01_int_Props02x`
- `055565` `blk_bank_int_02x`
- `055587` `blk_bank_int_shade_02x`
- `055615` `blk_cityHall01_int_Props01x`
- `055648` `blk_cityHall_int_01x`
- `055674` `blk_policeStation01_int_props02x`
- `055712` `blk_policeStation_int_02x`
- `055743` `blk_policeStation01_int_props01x`
- `055781` `blk_policeStation_int_01x`
- `055812` `blk_policeStation_int_shades01x`
- `055849` `blk_blacksmith_int_Props01x`
- `055882` `blk_blacksmith_int_01x`
- `055910` `blk_church_int_Props01x`
- `055939` `blk_church_int_01x`
- `055963` `blk_doctorsOffice_int_Props01x`
- `055999` `blk_doctorsOffice_int_01x`
- `056030` `blk_freightstation01_int_Props01x`
- `056069` `blk_freightstation_int_01x`
- `056101` `blk_generalStore_int_Props01x`
- `056136` `blk_generalStore_int_Props02x`
- `056171` `blk_generalStore_int_01x`
- `056201` `blk_tailor01_int_Props01x`
- `056232` `blk_tailor_int_01x`
- `056256` `blk_trainstation_int_Props01x`
- `056291` `blk_trainstation_int_01x`
- `056321` `blk_gunshop_int_Props01x`
- `056351` `blk_gunshop_int_01x`
- `056376` `blk_theatre_int_shade_01x`
- `056407` `blk_generalStore_int_shade_01x`
- `056443` `blk_tailor_int_shade_01x`
- `056473` `blk_doctorsOffice_int_shade_01x`
- `056510` `blk_forgeMill_int_shade_01x`
- `056543` `blk_sawMill_int_shade_01x`
- `056574` `blk_freightstation_int_shade_01x`
- `056612` `blk_blacksmith_int_shade_01x`
- `056646` `blk_cityHall_int_shade_01x`
- `056678` `blk_bank_int_shade_01x`
- `056706` `mor_morningStar_int_shade_01x`
- `056741` `blk_gunshop_int_shade_01x`
- `056772` `blk_saloon_int_Props01x`
- `056801` `blk_saloon_int_01x`
- `056825` `blk_hotel01_int_Props01x`
- `056855` `blk_hotel_int_01x`
- `056878` `blk_hotel_int_shade_01x`
- `056907` `blk_trainstation_int_Props01x`
- `056942` `blk_trainstation_int_01x`
- `056972` `mor_morningStar01_int_Props01x`
- `057008` `mor_morningStar_int_01x`
- `057037` `mor_morningStar_int_shade_01x`
- `057075` `rwf_barn01xprops01x`
- `057100` `rwf_barn01xprops02x`
- `057125` `rwf_livingRoom01props01x`
- `057155` `rwf_livingRoom01props02x`
- `057188` `beh_silo01x`
- `057205` `beh_silo02x`
- `057231` `beh_house02x`
- `057249` `beh_house02props01x`
- `057274` `beh_house01x`
- `057292` `beh_house01props01x`
- `057320` `beh_house02x`

### medium_update_thread_z.wsc
- `060353` `rsdGPSTRAIL_curve124`
- `060381` `rsdGPSTRAIL_curve132`
- `060412` `dixonCrossingAfter`
- `060436` `dixonCrossingBefore`
- `060461` `rsdROAD_thi_blk_road`
- `060489` `rsdROAD_thi_blk_roaddetachedCurve2`
- `060531` `rsdGPSTRAIL_curve124`
- `060559` `rsdGPSTRAIL_curve132`
- `060593` `hen_barn01x`
- `060610` `hen_barn02props01x`
- `060634` `hen_barn02x`
- `060651` `hen_barn01props01x`
- `060678` `campoMiradaAfter`
- `060700` `campoMiradaBefore`
- `060732` `fronteraBridgeBefore`
- `060758` `fronteraBridgeAfter`
- `060786` `fronteraBridgeAfter`
- `060811` `fronteraBridgeBefore`
- `060840` `fod_gates01x`
- `060858` `fod_gates02x`
- `060876` `fod_gates02Doors01x`
- `060904` `coc_fence01bx`
- `060923` `coc_fence03bx`
- `060942` `dlc_coc_gates02x`
- `060964` `coc_fence01x`
- `060982` `coc_fence03x`
- `061000` `coc_gates01x`
- `061018` `coc_gates02x`
- `061045` `masonBridgeBefore`
- `061068` `masonBridgeAfter`
- `061093` `masonBridgeAfter`
- `061115` `masonBridgeBefore`
- `061147` `lmf_troughBefore01x`
- `061172` `lmf_troughAfter01x`
- `061199` `lmf_troughAfter01x`
- `061223` `lmf_troughBefore01x`
- `061251` `morningStar`
- `061268` `blk_barge01Props01x`
- `061293` `blk_barge01x`
- `061311` `blk_theatre_int_Props01x`
- `061341` `blk_theatre_int_01x`
- `061366` `dlc_blk_bank01_int_Props02x`
- `061399` `blk_bank01_int_Props02x`
- `061428` `blk_bank_int_02x`
- `061450` `blk_bank_int_shade_02x`
- `061478` `blk_cityHall01_int_Props01x`
- `061511` `blk_cityHall_int_01x`
- `061537` `blk_policeStation01_int_props02x`
- `061575` `blk_policeStation_int_02x`
- `061606` `blk_policeStation01_int_props01x`
- `061644` `blk_policeStation_int_01x`
- `061675` `blk_policeStation_int_shades01x`
- `061712` `blk_blacksmith_int_Props01x`
- `061745` `blk_blacksmith_int_01x`
- `061773` `blk_church_int_Props01x`
- `061802` `blk_church_int_01x`
- `061826` `blk_doctorsOffice_int_Props01x`
- `061862` `blk_doctorsOffice_int_01x`
- `061893` `blk_freightstation01_int_Props01x`
- `061932` `blk_freightstation_int_01x`
- `061964` `blk_generalStore_int_Props01x`
- `061999` `blk_generalStore_int_Props02x`
- `062034` `blk_generalStore_int_01x`
- `062064` `blk_tailor01_int_Props01x`
- `062095` `blk_tailor_int_01x`
- `062119` `blk_trainstation_int_Props01x`
- `062154` `blk_trainstation_int_01x`
- `062184` `blk_gunshop_int_Props01x`
- `062214` `blk_gunshop_int_01x`
- `062239` `blk_theatre_int_shade_01x`
- `062270` `blk_generalStore_int_shade_01x`
- `062306` `blk_tailor_int_shade_01x`
- `062336` `blk_doctorsOffice_int_shade_01x`
- `062373` `blk_forgeMill_int_shade_01x`
- `062406` `blk_sawMill_int_shade_01x`
- `062437` `blk_freightstation_int_shade_01x`
- `062475` `blk_blacksmith_int_shade_01x`
- `062509` `blk_cityHall_int_shade_01x`
- `062541` `blk_bank_int_shade_01x`
- `062569` `mor_morningStar_int_shade_01x`
- `062604` `blk_gunshop_int_shade_01x`
- `062635` `blk_saloon_int_Props01x`
- `062664` `blk_saloon_int_01x`
- `062688` `dlc_blk_hotel01Props01x`
- `062717` `blk_hotel01Props01x`
- `062742` `dlc_blk_tailor01_int_Props01x`
- `062777` `blk_tailor01_int_Props01x`
- `062808` `blk_hotel01_int_Props01x`
- `062838` `blk_hotel_int_01x`
- `062861` `blk_hotel_int_shade_01x`
- `062890` `blk_trainstation_int_Props01x`
- `062925` `blk_trainstation_int_01x`
- `062955` `mor_morningStar01_int_Props01x`
- `062991` `mor_morningStar_int_01x`
- `063020` `mor_morningStar_int_shade_01x`
- `063058` `rwf_barn01xprops01x`
- `063083` `rwf_livingRoom01props01x`
- `063113` `rwf_barn01xprops02x`
- `063138` `rwf_livingRoom01props02x`

## Pasted MagicRDR decompile sector switch
The pasted decompile contains 722 sector/curve calls and 156 unique sector/curve names. It confirms the cases use `Function_108(...)` gates, then set `Global_39324[iVar0] = 1`, then call `ENABLE_*`/`DISABLE_*` sector natives.

## Recommended immediate move
Use the local Code RED tool on `medium_update_thread.wsc` and `medium_update_thread_z.wsc` first, not `short_update_thread.wsc`, to generate candidate IDs around `morningStar`, `mor_morningStar_int_01x`, `mor_morningStar01_int_Props01x`, and `mor_morningStar_int_shade_01x`. A safe first patch should be a dry-run that either inverts the specific branch guarding the Morningstar case or swaps a same-length sector string in an existing `ENABLE_CHILD_SECTOR` call. Do not swap native names yet unless the native/call candidate is promoted to CONTROL_FLOW_SAFE by the tool.