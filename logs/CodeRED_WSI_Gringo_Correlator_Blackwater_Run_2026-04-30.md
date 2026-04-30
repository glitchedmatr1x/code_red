# Code RED — Blackwater WSI ↔ WGD Correlation Run

Date: 2026-04-30

## Inputs checked

Extracted from uploaded sources:

```text
redemption part1.zip -> territory_swall/blackwater.rpf
game 1.zip -> gringores.rpf
```

Decoded resources:

```text
blackwater.rpf resource_type 134 entry 224
root/0x3EC4B1F5/0x3EC4B1F5/0x19839F99
Decoded WSI size: 2,465,792 bytes

gringores/commongringos.wgd
Decoded WGD size: 806,912 bytes

gringores/blackwater.wgd
Decoded WGD size: 53,248 bytes
```

## WGD export result

```text
commongringos.wgd.decoded: 2524 components
blackwater.wgd.decoded: 780 components
combined: 3304 components
```

The vehicle gringo lane is still present in `commongringos.wgd`, especially:

```text
content\scripting\gringo\CommonScripts\Vehicle_Generator
content\scripting\gringo\CommonScripts\car_gringo
content\scripting\gringo\CommonScripts\PlayerCar
content\scripting\gringo\CommonScripts\CarCrank_gringo
content\scripting\gringo\GringoBrains\GringoBrainScripts\Gen_Vehicle_Brain
```

## Correlator result on Blackwater WSI

```text
WSI sector headers: 218
WSI keyword string hits: 271
WSI hash matches to WGD: 0
Direct WSI -> WGD correlations: 0 direct safe candidates
WSI annotation/host rows: 99
WSI annotation candidate hosts: 92
```

## Important fix made during this run

The first correlator version indexed null WGD hashes such as `0x00000000`. Blackwater WSI contains many zero dwords, so the hash matcher could explode into useless matches. This pass now ignores `0x00000000` and `0xFFFFFFFF`, and includes a hash-match safety cap.

## Main finding

Blackwater WSI does **not** expose a clean direct WSI string/hash reference to `Vehicle_Generator`, `PlayerCar`, or `car_gringo` through the current string/hash lanes.

Instead, Blackwater WSI exposes placed prop/string-pool hosts and gringo annotations such as:

```text
i_gen_hitchingPost02x/a_has_gringo_gringoannotation_has_gringo
i_gen_hitchingPost03x/a_has_gringo_gringoannotation_has_gringo
i_gen_bench15x/gringo_available__sitbenchchair_
gringo_whittleWood01x/has_a_gringo_attribute_assigned
gringo_pitchHay01x/has_a_gringo_attribute_assigned
i_gen_outhouse02x/has_gringo_assigned
```

Transport/static vehicle-family host strings were also found:

```text
p_gen_cart03x
p_gen_cart01x
i_gen_wagonParked01x
i_gen_wagonBroken02x
i_gen_wagonParts01x
i_gen_wagonParts02x
i_gen_wagonParts03x
p_gen_lumberCart01x
p_gen_lumberCart03x
i_gen_popcornCart01x
```

## Interpretation

The current result supports a two-layer model:

```text
WSI layer: placed props, host strings, gringo availability annotations, sector/drawable data
WGD layer: behavior dictionaries and gringo scripts such as Vehicle_Generator / PlayerCar
```

The missing bridge is probably **not** a simple direct string match. The next tool needs to resolve the WSI host strings/hashes to actual drawable or prop placement records and transforms, then compare those placement records to gringo dictionaries/attributes.

## Do next

Build the next pass as:

```text
WSI Host Placement Resolver
```

Targets:

```text
1. Take wsi_annotation_candidate_hosts.csv as input.
2. Search decoded WSI for each host hash and nearby pointer/record structures.
3. Export likely placement rows with offset, matrix/position candidates, sector, host string, host hash, and nearby annotation strings.
4. Prioritize transport and gringo-bearing hosts:
   - p_gen_cart03x
   - p_gen_cart01x
   - i_gen_wagonParked01x
   - i_gen_hitchingPost02x / 03x
5. Do not patch yet. Prove the host -> placement offset first.
```

## Avoid for now

```text
Do not retry p_gen_carblocked01x -> car01.
Do not patch Vehicle_Generator yet.
Do not bulk-patch WSI/WGD/WVD/WBD.
```
