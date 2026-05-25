# DLC Horse Deed Grant Cross-Examination
Status: read-only research pass. No files were patched or rebuilt.
## Files Examined
- `main_wsc`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\release64\main.wsc` size=75695 sha1=39a921e1b72da33feec6246e3cd9db53a157b9c4
- `main_z_wsc`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\release64\main_z.wsc` size=65314 sha1=21c83a7f7fda584dfb51bd917fd7df2b35ac8b4b
- `horse_deed_wsc`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\release64\scripting\gringo\itemscripts\horse_deed.wsc` size=6749 sha1=9f695db9b5bfda15b79d92523cd68650cd10a3f3
- `inventory_xml`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\init\inventory\inventory.xml` size=123723 sha1=2598ed2ee058009d5a7bb9727e1eab1f7005687d
- `dlc_inventory_xml`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\init\inventory\dlc_inventory.xml` size=41281 sha1=6415ee83a057d958c6bf0b308092ce9ebfcb6cb4
- `horse_deed_war_z_xml`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\dlc\zombiepack\gringos\horse_deed_war_z.xml` size=1105 sha1=6e7b5b5cd1c4e358891000d56ebf06940ad94d1a
- `horse_deed_death_z_xml`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\dlc\zombiepack\gringos\horse_deed_death_z.xml` size=1111 sha1=9fa78988429ef9e529b312f73cc02807a2abb95c
- `horse_deed_famine_z_xml`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\dlc\zombiepack\gringos\horse_deed_famine_z.xml` size=1114 sha1=cf40eb3728b60c01ed897336fd47280288d48264
- `horse_deed_pestilence_z_xml`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\dlc\zombiepack\gringos\horse_deed_pestilence_z.xml` size=1126 sha1=f7b546413b2544f303550944788f7ca29fd9cd4f
- `zombiepackgringos_txt`: `D:\Games\Red Dead Redemption\Code_RED\game\content_extracted\dlc\zombiepack\gringos\zombiepackgringos.txt` size=4868 sha1=0fad3c7ee1fbe29eae1d03675f045b9ddf8332d8

## High-Level Conclusion
- `horse_deed.wsc` looks generic enough to consume the ZombiePack deed XMLs because it contains `ActorEnum`, `ItemAttribs`, `own_new_horse`, `SettingPlayerHorse`, `NewPlayerHorse_Wipe`, `WasPlayerMount`, and `ItemSave`.
- The four ZombiePack deed items are clearly registered in `dlc_inventory.xml` and in `zombiepackgringos.txt` using their original `DLC/ZombiePack/gringos` paths.
- Neither decoded `main.wsc` nor `main_z.wsc` string scans found literal `HORSE_WAR_Z`, `HORSE_DEATH_Z`, `HORSE_FAMINE_Z`, or `HORSE_PESTILENCE_Z`. This pass did not prove a safe numeric `ADD_ITEM` constant for the four DLC deeds.
- `main_z.wsc` shows stronger ZombiePack setup evidence than normal `main.wsc`, including `ZombiePackGringos` and direct DLC gringo path strings near startup/deed initialization.
- Safest next proof remains one item only: `HORSE_WAR_Z`, preserving the original DLC gringo XML path/name.

## Inventory Structure
- `inventory.xml` root tag: `invManager`, item count: 248
- `dlc_inventory.xml` root tag: `invManagerDLC`, item count: 64

### DLC Four Horse Deed Items
- `HORSE_WAR_Z` type=`invGringoType` gringo=`$\content\DLC\ZombiePack\gringos\Horse_Deed_War_Z` icon=`misc_horse_deed_03` infinite=`true`
- `HORSE_DEATH_Z` type=`invGringoType` gringo=`$\content\DLC\ZombiePack\gringos\Horse_Deed_Death_Z` icon=`misc_horse_deed_03` infinite=`true`
- `HORSE_FAMINE_Z` type=`invGringoType` gringo=`$\content\DLC\ZombiePack\gringos\Horse_Deed_Famine_Z` icon=`misc_horse_deed_03` infinite=`true`
- `HORSE_PESTILENCE_Z` type=`invGringoType` gringo=`$\content\DLC\ZombiePack\gringos\Horse_Deed_Pestilence_Z` icon=`misc_horse_deed_03` infinite=`true`

### Normal Horse Deed Registration Sample
- `HORSE_WAR` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_War` max=`1` infinite=`true`
- `HORSE_AMERICAN` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_American` max=`5` infinite=`true`
- `HORSE_ARDENNAIS` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Ardennais` max=`5` infinite=`true`
- `HORSE_CLEVELAND` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Cleveland` max=`5` infinite=`true`
- `HORSE_DUTCH` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Dutch` max=`5` infinite=`true`
- `HORSE_HEDOR` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Hedor` max=`5` infinite=`true`
- `HORSE_HIGHLAND` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Highland` max=`5` infinite=`true`
- `HORSE_HUNGARIAN` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Hungarian` max=`5` infinite=`true`
- `HORSE_INFESTED` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Infested` max=`5` infinite=`true`
- `HORSE_JADED` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Jaded` max=`5` infinite=`true`
- `HORSE_KENTUCKY` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Kentucky` max=`5` infinite=`true`
- `HORSE_LUSITANO` type=`invGringoType` gringo=`$\content\scripting\gringo\UseItems\Horse_Deed_Lusitano` max=`5` infinite=`true`

## DLC Gringo XMLs
- `horse_deed_war_z_xml` root=`ggoItemGringo` script=`content\scripting\gringo\ItemScripts\Horse_Deed` query_names=`ItemAttribs` UseName=`UseHorseDeedWarZ` ActorEnum=`RIDEABLE_ANIMAL_EVIL_Horse_War` myItemString=`Blood Pact - War` maintain=`true` largeScript=`false`
- `horse_deed_death_z_xml` root=`ggoItemGringo` script=`content\scripting\gringo\ItemScripts\Horse_Deed` query_names=`ItemAttribs` UseName=`UseHorseDeedDeathZ` ActorEnum=`RIDEABLE_ANIMAL_EVIL_Horse_Death` myItemString=`Blood Pact - Death` maintain=`true` largeScript=`false`
- `horse_deed_famine_z_xml` root=`ggoItemGringo` script=`content\scripting\gringo\ItemScripts\Horse_Deed` query_names=`ItemAttribs` UseName=`UseHorseDeedFamineZ` ActorEnum=`RIDEABLE_ANIMAL_EVIL_Horse_Famine` myItemString=`Blood Pact - Famine` maintain=`true` largeScript=`false`
- `horse_deed_pestilence_z_xml` root=`ggoItemGringo` script=`content\scripting\gringo\ItemScripts\Horse_Deed` query_names=`ItemAttribs` UseName=`UseHorseDeedPestilenceZ` ActorEnum=`RIDEABLE_ANIMAL_EVIL_Horse_Pestilence` myItemString=`Blood Pact - Pestilence` maintain=`true` largeScript=`false`

## ZombiePack Gringo Registration
- line 50: `$/content/dlc/zombiepack/gringos/horse_deed_death_z.xml`
- line 51: `$/content/dlc/zombiepack/gringos/horse_deed_famine_z.xml`
- line 52: `$/content/dlc/zombiepack/gringos/horse_deed_pestilence_z.xml`
- line 53: `$/content/dlc/zombiepack/gringos/horse_deed_war_z.xml`

## WSC String Evidence
### main_wsc
- `Initializing deed array` at 0x45D: `Initializing deed array`
- `ActorEnum` at 0xC72F: `With ActorEnum: `
### main_z_wsc
- `Initializing deed array` at 0x2A4: `Initializing deed array!`
- `ZombiePackGringos` at 0x307: `ZombiePackGringos`
- `ZombiePackGringos` at 0xD40: `ZombiePackGringos`
- `ActorEnum` at 0xF6F3: `With ActorEnum: `
### horse_deed_wsc
- `ItemSave` at 0xE0: `ItemSave`
- `ItemSave` at 0x102: `ItemSave`
- `ActorEnum` at 0x2B2A: `ActorEnum`
- `own_new_horse` at 0x2BAE: `own_new_horse`
- `ItemSave` at 0x2BCE: `ItemSave`
- `ItemAttribs` at 0x2FEB: `ItemAttribs`
- `ActorEnum` at 0x31B4: `ActorEnum`
- `WasPlayerMount` at 0x325C: `WasPlayerMount`
- `SettingPlayerHorse` at 0x33E8: `SettingPlayerHorse`
- `NewPlayerHorse_Wipe` at 0x3408: `NewPlayerHorse_Wipe`

## Decompile-Aligned ADD_ITEM / Slot Contexts
Important caveat: the raw Code RED disassembly confirms native operand bytes and nearby VM constants. It does not embed native names. The `ADD_ITEM` and slot labels below are aligned with the external decompile context and repeated call shape, so they are candidates, not safe patch targets yet.

### main.wsc ADD_ITEM candidate native operand 04 48
Total contexts included in JSON for this group: 5

- Native at `0x3BB4` operand `04 48` owner `main` offset_range=`0x0..18632`
  -    `0x3BAC: Op80_u16 1A 0A` 
  -    `0x3BAF: JumpFalse 00 ED` 
  -    `0x3BB2: RawOp143 ` operand width not inferred
  -    `0x3BB3: RawOp139 ` operand width not inferred
  - >> `0x3BB4: Native 04 48` native_index_bits=0x4804
  -    `0x3BB7: RawOp144 ` operand width not inferred
  -    `0x3BB8: RawOp139 ` operand width not inferred

- Native at `0x3BB9` operand `04 48` owner `main` offset_range=`0x0..18632`
  -    `0x3BB3: RawOp139 ` operand width not inferred
  -    `0x3BB4: Native 04 48` native_index_bits=0x4804
  -    `0x3BB7: RawOp144 ` operand width not inferred
  -    `0x3BB8: RawOp139 ` operand width not inferred
  - >> `0x3BB9: Native 04 48` native_index_bits=0x4804
  -    `0x3BBC: PushS8 08` 
  -    `0x3BBE: RawOp139 ` operand width not inferred

- Native at `0x3BBF` operand `04 48` owner `main` offset_range=`0x0..18632`
  -    `0x3BB8: RawOp139 ` operand width not inferred
  -    `0x3BB9: Native 04 48` native_index_bits=0x4804
  -    `0x3BBC: PushS8 08` 
  -    `0x3BBE: RawOp139 ` operand width not inferred
  - >> `0x3BBF: Native 04 48` native_index_bits=0x4804
  -    `0x3BC2: PushS8 09` 
  -    `0x3BC4: RawOp139 ` operand width not inferred

- Native at `0x3BC5` operand `04 48` owner `main` offset_range=`0x0..18632`
  -    `0x3BBE: RawOp139 ` operand width not inferred
  -    `0x3BBF: Native 04 48` native_index_bits=0x4804
  -    `0x3BC2: PushS8 09` 
  -    `0x3BC4: RawOp139 ` operand width not inferred
  - >> `0x3BC5: Native 04 48` native_index_bits=0x4804
  -    `0x3BC8: PushS8 10` 
  -    `0x3BCA: RawOp139 ` operand width not inferred

- Native at `0x3BCB` operand `04 48` owner `main` offset_range=`0x0..18632`
  -    `0x3BC4: RawOp139 ` operand width not inferred
  -    `0x3BC5: Native 04 48` native_index_bits=0x4804
  -    `0x3BC8: PushS8 10` 
  -    `0x3BCA: RawOp139 ` operand width not inferred
  - >> `0x3BCB: Native 04 48` native_index_bits=0x4804
  -    `0x3BCE: Op109_u24 11 C0 00` 
  -    `0x3BD2: Op85_u16 6B C2` 

### main.wsc _SET_INVENTORY_NEXT_USE_SLOT candidate native operand 0A 49
Total contexts included in JSON for this group: 8

- Native at `0x3BDD` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3BD9: RawOp143 ` operand width not inferred
  -    `0x3BDA: RawOp148 ` operand width not inferred
  -    `0x3BDB: RawOp139 ` operand width not inferred
  -    `0x3BDC: RawOp140 ` operand width not inferred
  - >> `0x3BDD: Native 0A 49` native_index_bits=0x490A
  -    `0x3BE0: Op79_u16 D3 3C` 
  -    `0x3BE3: RawOp175 ` operand width not inferred

- Native at `0x3BE9` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3BE4: PushS8 08` 
  -    `0x3BE6: RawOp148 ` operand width not inferred
  -    `0x3BE7: RawOp139 ` operand width not inferred
  -    `0x3BE8: RawOp140 ` operand width not inferred
  - >> `0x3BE9: Native 0A 49` native_index_bits=0x490A
  -    `0x3BEC: Op79_u16 D3 3C` 
  -    `0x3BEF: RawOp175 ` operand width not inferred

- Native at `0x3BF4` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3BF0: RawOp144 ` operand width not inferred
  -    `0x3BF1: RawOp148 ` operand width not inferred
  -    `0x3BF2: RawOp139 ` operand width not inferred
  -    `0x3BF3: RawOp140 ` operand width not inferred
  - >> `0x3BF4: Native 0A 49` native_index_bits=0x490A
  -    `0x3BF7: Op79_u16 D3 3C` 
  -    `0x3BFA: RawOp175 ` operand width not inferred

- Native at `0x3C00` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3BFB: PushS8 09` 
  -    `0x3BFD: RawOp148 ` operand width not inferred
  -    `0x3BFE: RawOp139 ` operand width not inferred
  -    `0x3BFF: RawOp140 ` operand width not inferred
  - >> `0x3C00: Native 0A 49` native_index_bits=0x490A
  -    `0x3C03: Op79_u16 D3 3C` 
  -    `0x3C06: RawOp175 ` operand width not inferred

- Native at `0x3C0C` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3C07: PushS8 10` 
  -    `0x3C09: RawOp148 ` operand width not inferred
  -    `0x3C0A: RawOp139 ` operand width not inferred
  -    `0x3C0B: RawOp140 ` operand width not inferred
  - >> `0x3C0C: Native 0A 49` native_index_bits=0x490A
  -    `0x3C0F: Op79_u16 D3 3C` 
  -    `0x3C12: RawOp175 ` operand width not inferred

- Native at `0x3C18` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3C13: PushS8 16` 
  -    `0x3C15: RawOp148 ` operand width not inferred
  -    `0x3C16: RawOp139 ` operand width not inferred
  -    `0x3C17: RawOp140 ` operand width not inferred
  - >> `0x3C18: Native 0A 49` native_index_bits=0x490A
  -    `0x3C1B: Op79_u16 D3 3C` 
  -    `0x3C1E: RawOp175 ` operand width not inferred

- Native at `0x3C24` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3C1F: PushS8 15` 
  -    `0x3C21: RawOp148 ` operand width not inferred
  -    `0x3C22: RawOp139 ` operand width not inferred
  -    `0x3C23: RawOp140 ` operand width not inferred
  - >> `0x3C24: Native 0A 49` native_index_bits=0x490A
  -    `0x3C27: RawOp142 ` operand width not inferred
  -    `0x3C28: Op83_u16 A7 0A` 

- Native at `0x3CD7` operand `0A 49` owner `main` offset_range=`0x0..18632`
  -    `0x3CD3: RawOp143 ` operand width not inferred
  -    `0x3CD4: RawOp148 ` operand width not inferred
  -    `0x3CD5: RawOp139 ` operand width not inferred
  -    `0x3CD6: RawOp140 ` operand width not inferred
  - >> `0x3CD7: Native 0A 49` native_index_bits=0x490A
  -    `0x3CDA: Op79_u16 D3 3C` 
  -    `0x3CDD: RawOp175 ` operand width not inferred

### main_z.wsc ADD_ITEM candidate native operand 04 89
Total contexts included in JSON for this group: 19

- Native at `0x439D` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4395: Native 10 88` native_index_bits=0x8810
  -    `0x4398: Jump 01 31` 
  -    `0x439B: RawOp143 ` operand width not inferred
  -    `0x439C: RawOp140 ` operand width not inferred
  - >> `0x439D: Native 04 89` native_index_bits=0x8904
  -    `0x43A0: RawOp143 ` operand width not inferred
  -    `0x43A1: Call2 44 D9` 

- Native at `0x43AB` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x43A4: Drop ` operand width not inferred
  -    `0x43A5: Jump 01 24` 
  -    `0x43A8: PushS8 19` 
  -    `0x43AA: RawOp140 ` operand width not inferred
  - >> `0x43AB: Native 04 89` native_index_bits=0x8904
  -    `0x43AE: RawOp143 ` operand width not inferred
  -    `0x43AF: Call2 44 D9` 

- Native at `0x43B8` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x43B2: Drop ` operand width not inferred
  -    `0x43B3: Jump 01 16` 
  -    `0x43B6: RawOp146 ` operand width not inferred
  -    `0x43B7: RawOp140 ` operand width not inferred
  - >> `0x43B8: Native 04 89` native_index_bits=0x8904
  -    `0x43BB: RawOp143 ` operand width not inferred
  -    `0x43BC: Call2 44 D9` 

- Native at `0x43C6` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x43BF: Drop ` operand width not inferred
  -    `0x43C0: Jump 01 09` 
  -    `0x43C3: PushS8 0B` 
  -    `0x43C5: RawOp140 ` operand width not inferred
  - >> `0x43C6: Native 04 89` native_index_bits=0x8904
  -    `0x43C9: RawOp143 ` operand width not inferred
  -    `0x43CA: Call2 44 D9` 

- Native at `0x43D4` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x43CD: Drop ` operand width not inferred
  -    `0x43CE: Jump 00 FB` 
  -    `0x43D1: PushS8 0D` 
  -    `0x43D3: RawOp140 ` operand width not inferred
  - >> `0x43D4: Native 04 89` native_index_bits=0x8904
  -    `0x43D7: RawOp143 ` operand width not inferred
  -    `0x43D8: Call2 44 D9` 

- Native at `0x43E2` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x43DB: Drop ` operand width not inferred
  -    `0x43DC: Jump 00 ED` 
  -    `0x43DF: PushS8 10` 
  -    `0x43E1: RawOp140 ` operand width not inferred
  - >> `0x43E2: Native 04 89` native_index_bits=0x8904
  -    `0x43E5: RawOp143 ` operand width not inferred
  -    `0x43E6: Call2 44 D9` 

- Native at `0x43F0` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x43E9: Drop ` operand width not inferred
  -    `0x43EA: Jump 00 DF` 
  -    `0x43ED: PushS8 11` 
  -    `0x43EF: RawOp140 ` operand width not inferred
  - >> `0x43F0: Native 04 89` native_index_bits=0x8904
  -    `0x43F3: RawOp143 ` operand width not inferred
  -    `0x43F4: Call2 44 D9` 

- Native at `0x43FE` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x43F7: Drop ` operand width not inferred
  -    `0x43F8: Jump 00 D1` 
  -    `0x43FB: PushS8 12` 
  -    `0x43FD: RawOp140 ` operand width not inferred
  - >> `0x43FE: Native 04 89` native_index_bits=0x8904
  -    `0x4401: RawOp143 ` operand width not inferred
  -    `0x4402: Call2 44 D9` 

- Native at `0x440C` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4405: Drop ` operand width not inferred
  -    `0x4406: Jump 00 C3` 
  -    `0x4409: PushS8 18` 
  -    `0x440B: RawOp140 ` operand width not inferred
  - >> `0x440C: Native 04 89` native_index_bits=0x8904
  -    `0x440F: RawOp143 ` operand width not inferred
  -    `0x4410: Call2 44 D9` 

- Native at `0x441A` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4413: Drop ` operand width not inferred
  -    `0x4414: Jump 00 B5` 
  -    `0x4417: PushS8 1A` 
  -    `0x4419: RawOp140 ` operand width not inferred
  - >> `0x441A: Native 04 89` native_index_bits=0x8904
  -    `0x441D: RawOp143 ` operand width not inferred
  -    `0x441E: Call2 44 D9` 

- Native at `0x4428` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4421: Drop ` operand width not inferred
  -    `0x4422: Jump 00 A7` 
  -    `0x4425: PushS8 16` 
  -    `0x4427: RawOp140 ` operand width not inferred
  - >> `0x4428: Native 04 89` native_index_bits=0x8904
  -    `0x442B: RawOp143 ` operand width not inferred
  -    `0x442C: Call2 44 D9` 

- Native at `0x4436` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x442F: Drop ` operand width not inferred
  -    `0x4430: Jump 00 99` 
  -    `0x4433: PushS8 1C` 
  -    `0x4435: RawOp140 ` operand width not inferred
  - >> `0x4436: Native 04 89` native_index_bits=0x8904
  -    `0x4439: RawOp143 ` operand width not inferred
  -    `0x443A: Call2 44 D9` 

- Native at `0x4444` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x443D: Drop ` operand width not inferred
  -    `0x443E: Jump 00 8B` 
  -    `0x4441: PushS8 23` 
  -    `0x4443: RawOp140 ` operand width not inferred
  - >> `0x4444: Native 04 89` native_index_bits=0x8904
  -    `0x4447: RawOp143 ` operand width not inferred
  -    `0x4448: Call2 44 D9` 

- Native at `0x4452` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x444B: Drop ` operand width not inferred
  -    `0x444C: Jump 00 7D` 
  -    `0x444F: PushS8 24` 
  -    `0x4451: RawOp140 ` operand width not inferred
  - >> `0x4452: Native 04 89` native_index_bits=0x8904
  -    `0x4455: RawOp143 ` operand width not inferred
  -    `0x4456: Call2 44 D9` 

- Native at `0x4460` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4459: Drop ` operand width not inferred
  -    `0x445A: Jump 00 6F` 
  -    `0x445D: PushS8 25` 
  -    `0x445F: RawOp140 ` operand width not inferred
  - >> `0x4460: Native 04 89` native_index_bits=0x8904
  -    `0x4463: RawOp143 ` operand width not inferred
  -    `0x4464: Call2 44 D9` 

- Native at `0x446E` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4467: Drop ` operand width not inferred
  -    `0x4468: Jump 00 61` 
  -    `0x446B: PushS8 26` 
  -    `0x446D: RawOp140 ` operand width not inferred
  - >> `0x446E: Native 04 89` native_index_bits=0x8904
  -    `0x4471: RawOp143 ` operand width not inferred
  -    `0x4472: Call2 44 D9` 

- Native at `0x447C` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4475: Drop ` operand width not inferred
  -    `0x4476: Jump 00 53` 
  -    `0x4479: PushS8 27` 
  -    `0x447B: RawOp140 ` operand width not inferred
  - >> `0x447C: Native 04 89` native_index_bits=0x8904
  -    `0x447F: RawOp143 ` operand width not inferred
  -    `0x4480: Call2 44 D9` 

- Native at `0x448A` operand `04 89` owner `Function_19` offset_range=`0x4233..17625`
  -    `0x4483: Drop ` operand width not inferred
  -    `0x4484: Jump 00 45` 
  -    `0x4487: PushS8 17` 
  -    `0x4489: RawOp140 ` operand width not inferred
  - >> `0x448A: Native 04 89` native_index_bits=0x8904
  -    `0x448D: RawOp143 ` operand width not inferred
  -    `0x448E: Call2 44 D9` 

- Native at `0x2B898` operand `04 89` owner `Function_455` offset_range=`0x2B281..178401`
  -    `0x2B891: RawOp138 ` operand width not inferred
  -    `0x2B892: JumpNE 00 06` 
  -    `0x2B895: Op56_u8 02` 
  -    `0x2B897: RawOp139 ` operand width not inferred
  - >> `0x2B898: Native 04 89` native_index_bits=0x8904
  -    `0x2B89B: Op56_u8 24` 
  -    `0x2B89D: RawOp6 ` operand width not inferred

## Answers To Core Questions
- `a_main_z_grants_dlc_deed_items_by_add_item_constants`: not_proven. main_z has a larger decompile-aligned ADD_ITEM candidate switch/function, but the four DLC horse deed names were not found in main_z strings and no HORSE_*_Z numeric item constants were proven from bytecode in this pass.
- `b_main_z_initializes_dlc_inventory_or_gringo_registries`: supported. main_z raw strings include ZombiePackGringos and direct DLC/ZombiePack gringo path strings near the deed-array initialization area.
- `c_main_z_unlocks_dlc_deed_flags`: possible but not proven. Function_19 contains unlock_help strings and repeated native calls, but ownership of DLC horse deed unlock flags is not proven.
- `d_normal_main_already_calls_dlc_init_but_not_specific_deed_grants`: partially supported. normal main has deed-array initialization but no literal HORSE_*_Z strings; DLC-specific gringo path evidence is stronger in main_z and XML registration.
- `e_horse_deed_generic`: strongly supported by strings: horse_deed.wsc contains ActorEnum, ItemAttribs, own_new_horse, SettingPlayerHorse, NewPlayerHorse_Wipe, WasPlayerMount, and ItemSave, while each DLC horse deed XML points to the same Horse_Deed script and passes a different ActorEnum.
- `f_dlc_gringo_xml_original_path_needed`: supported as safest assumption. dlc_inventory.xml GringoTypeName values and zombiepackgringos.txt both register the original DLC/ZombiePack/gringos/horse_deed_*_z.xml paths; moving/renaming is not the first safe strategy.

## Decompile Boolean / Numeric-ID Warning
The raw candidate contexts use compact VM operands such as RawOp139/140/143, PushS8, Call2, and Native operand bytes. This pass does not prove that MagicRDR boolean-looking ADD_ITEM arguments are trustworthy numeric item IDs. Treat boolean rendering as display ambiguity until native argument reconstruction is improved.

## Safest One-Item Proof Candidate
- Candidate: `HORSE_WAR_Z`
- Reason: It is the first DLC deed entry, has a normal non-Z cousin HORSE_WAR in inventory.xml, preserves the original DLC gringo path, and uses the generic Horse_Deed script with ActorEnum=RIDEABLE_ANIMAL_EVIL_Horse_War.
- Later strategy: XML/register one deed first while preserving GringoTypeName=$\content\DLC\ZombiePack\gringos\Horse_Deed_War_Z. Do not patch main.wsc ADD_ITEM constants until an exact DLC item constant/name mapping is proven.

## Do Not Patch Yet
- Do not replace `main.wsc` with `main_z.wsc`.
- Do not move ZombiePack gringo XMLs.
- Do not edit `horse_deed.wsc` in the next proof unless runtime evidence contradicts the generic-script finding.
- Do not patch `ADD_ITEM` constants until the item ID/name mapping is proven from bytecode, native argument reconstruction, or a verified inventory CRC/name mapping.
