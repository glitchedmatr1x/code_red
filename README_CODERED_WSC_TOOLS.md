# Code RED WSC Tools

`codered_wsc` is the reusable decoded-script inspection and safe-edit lane for Red Dead Redemption `.wsc`, `.xsc`, and raw script blobs. Population and vehicle patches are the first proof cases, not the architecture boundary. The tool keeps decoded script evidence separate from patchability so later mission, state, sector, AI, native-call, and function work can grow without broad blind binary edits.

The current milestone is deliberately conservative:

- open observed RSC85 type-2 WSC resources and word-swapped XSC wrappers
- resolve the AES key from an explicit key, a key file, or the known local `rdr.exe` offsets
- AES-decrypt and Zstandard-decompress RSC85 payloads
- emit string, function-enter, native-call, branch, constant, and actor-enum candidate reports
- map general decoded structures with patchability-labeled candidate reports
- scan decoded anchors with nearby byte context
- map bounded inline population pool blocks to same-width actor and vehicle enum operand candidates
- rebuild unchanged RSC85 resources
- apply reviewed same-size decoded edits, mapped population-pool recipes, and tightly gated control-flow probes to new output files

It is not a C-like decompiler. Control-flow support starts with candidate-targeted comparison-branch inversion only; native-call nops, function force-return, broad branch rewrites, and string-table rebuilds stay blocked until their VM effects are proven.

If an XSC normalizes to RSC85 but does not match the implemented Zstandard or zlib lanes under the supplied AES key, `inspect` still writes resource metadata and a decode-limit note. `disasm`, `scan`, `repack`, and `patch` stay blocked for that resource until the correct Xbox LZX or other decode bridge is wired in.

## Commands

Run from the Code RED repo root:

```bat
python -m codered_wsc inspect imports\grt_population.wsc --out reports\grt_population_inspect --rdr-exe "..\rdr.exe"
python -m codered_wsc disasm imports\long_update_thread.wsc --out reports\long_update_thread_disasm --rdr-exe "..\rdr.exe"
python -m codered_wsc scan imports\short_update_thread.wsc --terms enable,disable,sector,flee,vehicle,driver --out reports\short_update_scan --rdr-exe "..\rdr.exe"
python -m codered_wsc map imports\long_update_thread.wsc --out reports\long_update_thread_map --rdr-exe "..\rdr.exe"
python -m codered_wsc candidates imports\long_update_thread.wsc --kind constants --out reports\long_update_thread_constant_candidates --rdr-exe "..\rdr.exe"
python -m codered_wsc candidates imports\long_update_thread.wsc --kind native --rdr-exe "..\rdr.exe"
python -m codered_wsc candidates imports\long_update_thread.wsc --kind functions --rdr-exe "..\rdr.exe"
python -m codered_wsc control-flow imports\long_update_thread.wsc --terms vehicle,flee,driver,sector,enable --out reports\long_update_thread_control_flow --rdr-exe "..\rdr.exe"
python -m codered_wsc scan-pools imports\grt_population.wsc --out reports\grt_population_pools --rdr-exe "..\rdr.exe"
python -m codered_wsc repack imports\grt_population.wsc --out build\wsc_roundtrip\grt_population.wsc --rdr-exe "..\rdr.exe"
python -m codered_wsc recipe recipes\codered_wsc_same_size_enum_example.yaml
python -m codered_wsc patch imports\grt_population.wsc --recipe recipes\codered_wsc_same_size_enum_example.yaml --out build\wsc_patch_test\grt_population.wsc --rdr-exe "..\rdr.exe"
python -m codered_wsc patch imports\grt_population.wsc --recipe recipes\grt_population_lawmen_fbi_drivers.yaml --out build\wsc_patch_test\grt_population_lawmen_fbi_drivers.wsc --dry-run --rdr-exe "..\rdr.exe"
```

Use `--aes-key-file` or `--aes-key-hex` instead of `--rdr-exe` when operating on extracted samples away from a game install.

## Reports

`inspect` writes:

- `resource_info.json`
- `strings.txt` and `strings.csv`
- `native_table.csv`
- `statics.csv` and `globals.csv` placeholders
- `functions.csv`
- `code_sections.bin` and `decompressed.bin`
- `inspect_report.md`

`patch` never overwrites the input. Beside the requested patched file it writes a patch bundle with an original backup, decoded before/after bytes, binary diff CSV/text, manifest, patch report, and validation report.

`scan-pools` writes `population_pools.csv/json`, pool actor/vehicle candidate CSVs, bounded pool disassembly context, and a report. Pool patch recipes only use immediate enum operands marked safe by that mapper. A variable-size standalone WSC report tells you to use Magic RDR/RPF import rather than raw archive offset overwrite.

`map` writes a general decoded structure inventory for functions, strings, constants, native calls, branch/call candidates, and known table blocks. `candidates` accepts `branch`, `native`, `functions`, `constants`, `strings`, or `tables` and labels every row as `READ_ONLY`, `SAME_SIZE_SAFE`, `CONTROL_FLOW_SAFE`, `REBUILD_REQUIRED`, or `UNSUPPORTED`. Current safe rows are same-width constant operands, same-length printable strings, mapped population table enum operands, and branch candidates only when the opcode has a proven same-width invert pair. Native and function behavior candidates remain report-only.

`control-flow` writes `control_flow_candidates.csv/json`, `control_flow_ranked_functions.csv`, and `control_flow_context.md`. It groups branch, native, and function candidates by owner function and ranks nearby context terms without writing a script.

`map` also writes ownership review files:

- `functions_detailed.csv`, `function_context.json`, and `function_context.md`
- `string_references.csv` and `string_context.md`

Candidate rows carry `candidate_id`, decoded offset, section, owner type/name, owner function range, nearby strings/native calls/branches, value type, confidence, safety reason, and blocked reason. `file_offset` is blank when a decoded offset cannot be mapped through compressed/encrypted resource storage.

Use a reviewed constant candidate instead of guessing an offset:

```yaml
patches:
  - type: replace_constant
    match:
      candidate_id: CONST_000123
    replacement: 0
    expected_width: 1
    require_patchability: SAME_SIZE_SAFE
```

Matching by value or nearby context requires `max_matches`. Exact `candidate_id` or decoded-offset matches do not. Raw `replace_bytes` is blocked unless the recipe explicitly sets `allow_unowned: true`, and protected string/native/function metadata overlap is still validated before output writes.

Control-flow recipes are dry-run-first. They must target a branch, native, or function candidate by `candidate_id` or exact decoded offset. A real write is refused unless the reviewed recipe adds:

```yaml
acknowledge_control_flow_write: true
```

The first writable probe is `force_branch` with `mode: invert` for promoted comparison branches. `nop_instruction`, `nop_native_call`, `force_function_return`, and branch `always_true` / `always_false` remain wired but blocked with explicit reasons until no-op opcodes, stack effects, and return conventions are proven.

The package is split so new analysis and patch safety can land in focused modules:

- `codered_wsc.analysis`: core walker plus `functions`, `strings`, `constants`, `native_calls`, `control_flow`, and `tables`
- `codered_wsc.patching`: width-preserving `primitives`, recipe execution, and validation

## Local Samples

Keep game scripts under ignored local folders such as `imports\` or `samples\codered_wsc_local\`. Tests use synthetic resources so no game script payload is required in Git.
