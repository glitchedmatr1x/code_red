# Code RED Navres Battle Set Analysis

## Source

- `navres.zip -> navres.rpf`
- RPF entries: 986
- File entries: 978
- Battle set manifest links: 29

## Important finding

`navres.rpf` contains a small zstd manifest that maps tune-side battle set refgroups to navres-side resources. This means the `root/tune/refGroups/battleSets/*.refgroup` files are not just random props; they have matching navigation resources.

For Faction War, this is useful because battle-set refgroups are prebuilt cover/debris/wagon/rock layouts that should be safer to reuse than totally custom prop clusters.

## Region battle-set coverage

- `cho` (Cholla Springs): 4 battle sets, 1 enemy variant
- `die` (Diez Coronas / Diegos Bluff): 2 battle sets, 0 enemy variants
- `gap` (Gaptooth Ridge): 3 battle sets, 1 enemy variant
- `gre` (Great Plains / Great Plains-like): 4 battle sets, 1 enemy variant
- `gri` (Gringo/Ridge/region prefix gri): 4 battle sets, 1 enemy variant
- `hen` (Hennigan's Stead): 4 battle sets, 1 enemy variant
- `per` (Perdido): 3 battle sets, 1 enemy variant
- `pun` (Punta Orgullo): 3 battle sets, 1 enemy variant
- `rio` (Rio Bravo/Rio region): 1 battle set, 0 enemy variants
- `treasureHunter01`: special battle-set entry

## Battle-set names from navres manifest

- `cho_battleSet01x` -> `$/navres/rsc_battlesets_#/cho_battleSet01x`
- `cho_battleSet02x` -> `$/navres/rsc_battlesets_#/cho_battleSet02x`
- `cho_battleSet03x` -> `$/navres/rsc_battlesets_#/cho_battleSet03x`
- `cho_battleSetEnemy01x` -> `$/navres/rsc_battlesets_#/cho_battleSetEnemy01x`
- `die_battleSet01x` -> `$/navres/rsc_battlesets_#/die_battleSet01x`
- `die_battleSet02x` -> `$/navres/rsc_battlesets_#/die_battleSet02x`
- `gap_battleSet01x` -> `$/navres/rsc_battlesets_#/gap_battleSet01x`
- `gap_battleSet02x` -> `$/navres/rsc_battlesets_#/gap_battleSet02x`
- `gap_battleSetEnemy01x` -> `$/navres/rsc_battlesets_#/gap_battleSetEnemy01x`
- `gre_battleSet01x` -> `$/navres/rsc_battlesets_#/gre_battleSet01x`
- `gre_battleSet02x` -> `$/navres/rsc_battlesets_#/gre_battleSet02x`
- `gre_battleSet03x` -> `$/navres/rsc_battlesets_#/gre_battleSet03x`
- `gre_battleSetEnemy01x` -> `$/navres/rsc_battlesets_#/gre_battleSetEnemy01x`
- `gri_battleSet01x` -> `$/navres/rsc_battlesets_#/gri_battleSet01x`
- `gri_battleSet02x` -> `$/navres/rsc_battlesets_#/gri_battleSet02x`
- `gri_battleSet03x` -> `$/navres/rsc_battlesets_#/gri_battleSet03x`
- `gri_battleSetEnemy01x` -> `$/navres/rsc_battlesets_#/gri_battleSetEnemy01x`
- `hen_battleSet01x` -> `$/navres/rsc_battlesets_#/hen_battleSet01x`
- `hen_battleSet02x` -> `$/navres/rsc_battlesets_#/hen_battleSet02x`
- `hen_battleSet03x` -> `$/navres/rsc_battlesets_#/hen_battleSet03x`
- `hen_battleSetEnemy01x` -> `$/navres/rsc_battlesets_#/hen_battleSetEnemy01x`
- `per_battleSet02x` -> `$/navres/rsc_battlesets_#/per_battleSet02x`
- `per_battleSet03x` -> `$/navres/rsc_battlesets_#/per_battleSet03x`
- `per_battleSetEnemy01x` -> `$/navres/rsc_battlesets_#/per_battleSetEnemy01x`
- `pun_battleSet01x` -> `$/navres/rsc_battlesets_#/pun_battleSet01x`
- `pun_battleSet03x` -> `$/navres/rsc_battlesets_#/pun_battleSet03x`
- `pun_battleSetEnemy01x` -> `$/navres/rsc_battlesets_#/pun_battleSetEnemy01x`
- `rio_battleSet03x` -> `$/navres/rsc_battlesets_#/rio_battleSet03x`
- `treasureHunter01` -> `$/navres/rsc_battlesets_#/treasureHunter01`

## Prop composition

Top prop references across linked tune battle sets:

- `p_bat_debrisPile02x`: 63
- `p_bat_brokenParts03x`: 40
- `p_bat_crate01x`: 24
- `p_bat_crate03x`: 24
- `p_bat_crate02x`: 22
- `p_bat_crate07x`: 22
- `p_bat_flourSack01x`: 19
- `p_gen_boiler01x`: 18
- `p_bat_crate06x`: 17
- `p_bat_crate05x`: 16
- `p_bat_rockHennigans01x`: 16
- `p_bat_brokenParts02x`: 13
- `p_gen_can06x`: 11
- `p_bat_crate08x`: 11
- `p_bat_barrel04x`: 11
- `p_bat_brokenBarrel02x`: 11
- `p_bat_tree02x`: 11
- `p_bat_rockChollaSprings01x`: 10
- `p_bat_wagon06x`: 10
- `p_gen_lantern04x`: 10
- `p_bat_table01x`: 9
- `p_gen_molotovCrate01x`: 9
- `p_bat_barrelSide01x`: 9
- `p_bat_wagon05x`: 9
- `p_bat_rockChollaSprings02x`: 8

## Faction War use

Recommended use in Pass 16:

1. Keep Pass 15/15.30 as the faction-war baseline.
2. Add the Max Render/Spawns tune support layer separately.
3. Reuse battle-set refgroups as battle-set/camp/road event staging props by region.
4. Prefer `*Enemy01x` variants for enemy faction staging pressure and standard `01x/02x/03x` variants for general cover/camp clutter.
5. Do not invent prop clusters first; use these existing battle sets because navres already knows them.
6. Pair each region battle set with matching faction/law population/event logic after content-side faction templates are identified.

## Highest-value regions for next tests

- `cho_*`: Cholla Springs/outlaw roadside pressure.
- `gap_*`: Gaptooth Ridge, strong debris/wagon/crate battle layouts.
- `hen_*`: Hennigan trails and ranch outskirts.
- `per_*`, `pun_*`, `rio_*`: Mexico/regional faction pressure.
- `treasureHunter01`: likely special encounter staging candidate.

## Nav prop type set

`navres.rpf` also contains a decompressed XML prop type set with 1,995 prop type entries. These define static navigation inclusion, obstacle behavior, and bounding boxes for props like barrels, crates, wagon wheels, tables, bedrolls, and battle-set props.

The extracted battle-interest prop summary found 165 relevant prop rows. Notably, 20 `p_bat_*` battle props are known to this nav prop type set, including broken parts, wagons, barrels, crates, tables, flour sacks, crate stacks, Gaptooth rocks, and wagon burn props.

This is useful for deciding which props are safe to place persistently without breaking navigation.

## No-regression note

This should be added as a support/staging layer. It should not replace the Pass 15 event, law, population, traffic, or actor-cap checks.
