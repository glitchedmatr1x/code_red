# Code RED — WSI Host Placement Resolver Pass

Date: 2026-04-30

## Purpose

This pass follows the WSI ↔ WGD gringo correlator result. Blackwater WSI did not expose a clean direct `Vehicle_Generator` placement. It exposed prop/drawable host strings and gringo annotation clues. This pass resolves the priority wagon/cart/hitch hosts back into actual WSI placement records before any patch experiment.

## Tool added

```text
tools/codered_wsi_host_placement_resolver.py
```

The tool is read-only. It does not patch WSI, WGD, WVD, or WBD.

## Key structure found

The Blackwater decoded WSI contains two useful host-placement lanes:

```text
props records
- likely stride: 0x30
- host name pointer: +0x00
- position guess: +0x10 as float3

drawable_instances / drawable_instances2 records
- likely stride: 0xE0 / 224
- host name pointer: +0xB8
- transform matrix: +0x40 through +0x70
- position row: +0x70
- bbox guess: +0x80 and +0x90
```

## Actual Blackwater run

Input:

```text
/mnt/data/codered_run/blackwater_type134/0224_0x19839F99.wsi.decoded
```

Priority hosts scanned:

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
i_gen_hitchingPost02x
i_gen_hitchingPost03x
```

Result:

```text
payload_count: 1
host_count: 11
sector_count: 218
candidate_rows: 34
safe_candidate_rows: 23
unresolved_hosts: 2
```

## Best current candidates

Top resolver-safe candidates are real placement records, not loose string-pool guesses:

```text
i_gen_wagonBroken02x
- record kind: drawable_instance_0xE0
- record offset: 0x0011C7E0
- array: drawable_instances index 9
- position: [723.793213, 79.2099, 1419.701904]
- score: 19

i_gen_wagonParked01x
- multiple drawable_instance_0xE0 records resolved
- strong high-confidence transform candidates

i_gen_wagonParts01x / 02x / 03x
- multiple drawable_instance_0xE0 records resolved
- good static clutter candidates

p_gen_cart03x / p_gen_cart01x
- props record candidates resolved
- likely 0x30 compact props records
```

## Outputs

```text
reports/blackwater_host_placement_resolver_outputs/blackwater_host_candidates.csv
reports/blackwater_host_placement_resolver_outputs/blackwater_host_candidates.json
reports/blackwater_host_placement_resolver_outputs/blackwater_safe_vehicle_test_candidates.csv
reports/blackwater_host_placement_resolver_outputs/host_reference_summary.csv
reports/blackwater_host_placement_resolver_outputs/unresolved_hosts.csv
reports/blackwater_host_placement_resolver_outputs/sector_context.csv
reports/blackwater_host_placement_resolver_outputs/blackwater_host_resolver_master.json
reports/blackwater_host_placement_resolver_outputs/single_placement_experiment_plan.md
```

## Interpretation

This pass confirms a better patch lane than the old raw `car01` prop replacement. The next experiment should target one resolved placement record in a copied RPF, not a vague string-pool item.

The best first target is currently `i_gen_wagonBroken02x` because it is static-looking clutter, vehicle-adjacent, resolved into a high-confidence drawable instance transform, and should be safer than station/interior/mission actors.

## Next pass

Pass 4 should be a field-proof / single-placement patch planner:

```text
1. Create a copied Blackwater RPF only.
2. Reopen and decode the selected WSI.
3. Export old bytes for record 0x0011C7E0.
4. Build a no-op patch proof first.
5. Only after proof, test a one-record replacement/binding lane toward the gringo vehicle system.
```

Do not bulk patch. Do not use raw `car01` again as a static model swap.
