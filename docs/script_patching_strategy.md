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

- `replace_enum_operand`
- `replace_bytes`
- `same_length_string_replace`

`replace_enum_operand` refuses values that cannot fit the selected one, two, or four byte operand width. It does not widen instructions or recalculate offsets.

## Deferred Work

These recipe types are named but intentionally blocked until Code RED proves their bytecode and table context:

- population actor pool replacement by pool name
- population vehicle pool replacement by pool name
- inferred boolean flip
- nop by decoded instruction boundary
- force function return
- branch flip or redirect
- length-changing string table rebuild

The planned population recipe in `recipes\grt_population_lawmen_drivers.yaml` is a support target and validation fixture. Running `python -m codered_wsc recipe` against it must report that it is not ready rather than patching blind actor windows.

## Next Implementation Lane

The next step is to map population group string references to exact actor and vehicle operand sequences in decoded scripts. Once a pool boundary is proven, pool replacement can generate a list of exact same-width enum edits and reuse the existing manifest and validation path.
