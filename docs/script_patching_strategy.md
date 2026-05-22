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

## Ownership Model

Candidate reports include a stable-ish ID for the current decoded script pass:

- `CONST_000123`
- `STR_000045`
- `NATIVE_000142`
- `BRANCH_000088`
- `TABLE_000019`

The same row also records decoded offset, section, owner type/name, owner function range, nearby string/native/branch context, value type, operand width, confidence, safety reason, blocked reason, and unrelated-code risk. Decoded ownership is required for a normal patch. If compressed/encrypted storage makes the source file offset unknowable, `file_offset` stays blank rather than pretending raw RPF/resource offsets are editable.

Patchability means:

- `READ_ONLY`: decoded evidence is useful, but no edit primitive is safe yet.
- `SAME_SIZE_SAFE`: the owned bytes have a width-preserving primitive and manifest coverage.
- `CONTROL_FLOW_SAFE`: reserved for future proven branch/call rewrites.
- `REBUILD_REQUIRED`: requires table/string/code rebuilding before edits are safe.
- `UNSUPPORTED`: known lane is outside the implemented decoder or patcher.

Constants should be matched by candidate ID, exact decoded offset, or a bounded contextual match. A value/context query must specify `max_matches`:

```yaml
patches:
  - type: replace_constant
    match:
      value: 1
      owner_function_contains_terms: [sector, enable]
      nearby_string_contains: [sector]
    replacement: 0
    expected_width: 1
    max_matches: 3
    require_patchability: SAME_SIZE_SAFE
```

Raw decoded-byte replacements are unowned by default. `allow_unowned: true` is an explicit manual-review escape hatch, and it still cannot overlap protected string/native/function metadata in this milestone.

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
- XSC patching where the decode/repack path is not proven for that sample

Pool recipes still refuse an unmapped pool, unsafe candidate, or width expansion when the recipe requests fail-fast width checks.

## Next Implementation Lane

The next step after the pool lane is to extend opcode structure and function/reference recovery before branch patching. Population pools are the first known table family plugged into a broader decoded-script map.
