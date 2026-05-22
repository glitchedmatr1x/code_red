# Code RED WSC Format Notes

## Current Proven Lane

The files already patched in Code RED use an RSC85 resource wrapper:

- WSC header prefix: `52 53 43 85`
- observed script resource type: `2`
- XSC form may be the complete 32-bit word-swapped view with prefix `85 43 53 52`
- stored resource data after the 16-byte header is AES-256 ECB transformed for 16 passes over aligned data
- observed decoded payloads use Zstandard compression

`codered_wsc.resource` implements that path with explicit failures when a file is not an observed type-2 script or does not decode after decryption. It accepts raw script bytes for reporting but only writes changed payloads through the validated RSC85 writer.

An XSC can normalize to an RSC85 header and still require a different data path. The current inspector records `unsupported-or-key-mismatch` if AES decode does not produce Zstandard, zlib, or the simple Xbox LZX wrapper probe. That report is metadata, not disassembled bytecode.

## Bytecode Notes

The initial walker follows the opcode-width behavior used by the local Magic-RDR reference for function discovery:

- `Enter` is opcode `0x2D` and carries parameter count, local count, name length, and optional name text
- `Return` is opcode `0x2E`
- compact return opcodes occupy `0x7A` through `0x89`
- native calls use opcode `0x2C` with two operand bytes
- string, switch, and fixed-width operand families are walked by known width only

Unknown opcode widths are left as one raw byte in reports. That avoids inventing structure during milestone one, but it also means a disassembly can lose synchronization in scripts that use width rules not recorded yet.

## Actor Enum Hints

Reports mark likely actor integer windows for review:

- general `eActorEnum` range: `0` through `1294`
- law hints: `424` through `466`
- gang hints: `467` through `540`
- FBI hints: `595` through `598`
- vehicle hints around `1155` through `1202`

Raw two-byte candidates are intentionally noisy. Prefer instruction constants and exact reviewed offsets before applying a recipe.

## Population Pool Mapper

Population scripts observed in this workspace define pool names inline with `PushString`. Milestone two maps from each recognized `ped_*` or `animal_*` pool string to the next population pool string and inspects bounded immediate enum operands inside that block.

Low actor IDs use one-byte immediates. Larger law, hostile, and vehicle IDs in `grt_population.wsc` use the `0x41` two-byte operand carrier. The mapper records candidate width, enum category, confidence, and skipped entries. Recipes patch only candidates marked safe for the selected actor or vehicle pool.

## Analysis Packages

The bytecode walker now feeds general analysis modules:

- `analysis.functions` exposes `Enter`-pattern function candidates
- `analysis.strings` exposes printable string anchors and same-length patch candidates
- `analysis.constants` exposes fixed-width immediate constant candidates
- `analysis.native_calls` records decoded native-call operand bits without allowing call edits yet
- `analysis.control_flow` records branch/call target candidates without branch rewrites yet
- `analysis.tables` owns table families as they become proven; population pools are the first one

Each candidate report states its patchability level. A decoded branch, native, or raw enum hint can be useful evidence while still remaining read-only.
