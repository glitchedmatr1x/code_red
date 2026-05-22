# Code RED WSC Tools

`codered_wsc` is the reusable decoded-script inspection lane for Red Dead Redemption `.wsc`, `.xsc`, and raw script blobs. The first milestone is deliberately conservative:

- open observed RSC85 type-2 WSC resources and word-swapped XSC wrappers
- resolve the AES key from an explicit key, a key file, or the known local `rdr.exe` offsets
- AES-decrypt and Zstandard-decompress RSC85 payloads
- emit string, function-enter, native-call, branch, constant, and actor-enum candidate reports
- scan decoded anchors with nearby byte context
- rebuild unchanged RSC85 resources
- apply reviewed same-size decoded edits from YAML recipes to new output files

It is not a C-like decompiler and it does not claim population-pool, branch, force-return, or string-table rebuild support before those structures are validated.

If an XSC normalizes to RSC85 but does not match the implemented Zstandard or zlib lanes under the supplied AES key, `inspect` still writes resource metadata and a decode-limit note. `disasm`, `scan`, `repack`, and `patch` stay blocked for that resource until the correct Xbox LZX or other decode bridge is wired in.

## Commands

Run from the Code RED repo root:

```bat
python -m codered_wsc inspect imports\grt_population.wsc --out reports\grt_population_inspect --rdr-exe "..\rdr.exe"
python -m codered_wsc disasm imports\long_update_thread.wsc --out reports\long_update_thread_disasm --rdr-exe "..\rdr.exe"
python -m codered_wsc scan imports\short_update_thread.wsc --terms enable,disable,sector,flee,vehicle,driver --out reports\short_update_scan --rdr-exe "..\rdr.exe"
python -m codered_wsc repack imports\grt_population.wsc --out build\wsc_roundtrip\grt_population.wsc --rdr-exe "..\rdr.exe"
python -m codered_wsc recipe recipes\codered_wsc_same_size_enum_example.yaml
python -m codered_wsc patch imports\grt_population.wsc --recipe recipes\codered_wsc_same_size_enum_example.yaml --out build\wsc_patch_test\grt_population.wsc --rdr-exe "..\rdr.exe"
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

## Local Samples

Keep game scripts under ignored local folders such as `imports\` or `samples\codered_wsc_local\`. Tests use synthetic resources so no game script payload is required in Git.
