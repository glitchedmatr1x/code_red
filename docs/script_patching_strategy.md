# Script Patching Strategy

## Milestone One Safety Rules

Use compiled scripts as decoded binary artifacts:

1. Decode, inspect, and save a report first.
2. Treat readable strings as anchors only.
3. Patch exact decoded offsets only after the operand encoding is known.
4. Keep decoded byte length unchanged.
5. Repack to a new resource and require reopen/decompress validation.
6. Record the decoded diff, backup, manifest, and validation report.

The currently supported recipe patch types are:

- `replace_constant`
- `replace_enum_operand`
- `replace_bytes`
- `same_length_string_replace`
- `population_actor_pool_replace`
- `population_vehicle_pool_replace`

`replace_constant` and `replace_enum_operand` refuse values that cannot fit the selected one, two, or four byte operand width. They do not widen instructions or recalculate offsets.

## General Edit Direction

Population recipes prove table ownership and same-width enum edits. They do not define the long-term tool shape. General decoded-script editing is organized around:

- functions, strings, constants, native calls, control flow, and known tables as separate analysis surfaces
- patchability labels: `READ_ONLY`, `SAME_SIZE_SAFE`, `CONTROL_FLOW_SAFE`, `REBUILD_REQUIRED`, and `UNSUPPORTED`
- dry-run recipes and exact offset manifests for any patch type that graduates from report-only analysis

`map` is the general structure report. `candidates` is the report that states what the current tool can patch and what remains evidence only.

## Deferred Work

Population pool recipes are bounded by inline pool string blocks and emit skipped candidates. Actor recipes refuse vehicle and animal candidates; vehicle recipes require `ped_vehicle` and an explicit old-to-new vehicle enum mapping.

These recipe types are named but intentionally blocked until Code RED proves their bytecode and table context:

- inferred boolean flip
- nop by decoded instruction boundary
- nop or redirect by call target
- force function return
- branch flip, force, or redirect
- native argument replacement without mapped argument ownership
- length-changing string table rebuild

Pool recipes still refuse an unmapped pool, unsafe candidate, or width expansion when the recipe requests fail-fast width checks.

## Next Implementation Lane

The next step after the pool lane is to extend opcode structure and function/reference recovery before branch patching. Population pools are the first known table family plugged into a broader decoded-script map.
