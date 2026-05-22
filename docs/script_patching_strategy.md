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
- `force_branch` for candidate-targeted same-width comparison-branch inversion

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
- `CONTROL_FLOW_SAFE`: owned control-flow bytes with a known opcode, instruction width, width-preserving replacement, and no protected-section overlap.
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

## Controlled Control Flow

Control-flow editing is dangerous because branch conditions, stack consumption, call arguments, return values, and jump layout all affect VM state beyond the patched bytes. A decoded target is not enough. A control-flow primitive must keep ownership, instruction width, semantics, and replacement bytes proven.

`control-flow` is the review report for this lane:

```bat
python -m codered_wsc control-flow imports\long_update_thread.wsc --terms sector,enable,disable,vehicle,flee --out reports\long_update_thread_control_flow --rdr-exe "..\rdr.exe"
```

Recipes must target a `candidate_id` or exact decoded offset. The patch command emits a dry-run bundle and refuses a real control-flow write until the recipe explicitly records review:

```yaml
acknowledge_control_flow_write: true
patches:
  - type: force_branch
    candidate_id: BRANCH_000088
    mode: invert
    require_patchability: CONTROL_FLOW_SAFE
```

Milestone four only promotes comparison branches that have a known same-width invert opcode pair. `always_true` and `always_false` are still blocked because their stack behavior is not proven. Blocked probes use these actionable reason codes:

- `UNKNOWN_OPCODE`
- `UNKNOWN_INSTRUCTION_WIDTH`
- `UNKNOWN_BRANCH_SEMANTICS`
- `NO_PROVEN_NOP_OPCODE`
- `UNKNOWN_STACK_EFFECT`
- `UNKNOWN_RETURN_CONVENTION`
- `LAYOUT_REBUILD_REQUIRED`
- `PROTECTED_SECTION_OVERLAP`

## Deferred Work

Population pool recipes are bounded by inline pool string blocks and emit skipped candidates. Actor recipes refuse vehicle and animal candidates; vehicle recipes require `ped_vehicle` and an explicit old-to-new vehicle enum mapping.

These recipe types are named or wired but intentionally blocked until Code RED proves their bytecode and table context:

- inferred boolean flip
- nop by decoded instruction boundary
- nop or redirect by call target
- force function return
- branch force or redirect outside the bounded comparison invert probe
- native argument replacement without mapped argument ownership
- length-changing string table rebuild
- XSC patching where the decode/repack path is not proven for that sample

Pool recipes still refuse an unmapped pool, unsafe candidate, or width expansion when the recipe requests fail-fast width checks.

## Next Implementation Lane

Control-flow reports should be run on update-thread scripts before any new primitive is promoted. The next expansion needs VM stack and return-convention proof for a narrow call, return, or conditional family, not broad branch automation.
