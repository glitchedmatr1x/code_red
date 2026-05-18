# Code RED RDR1 Resource Lab v3 Notes

## Fixes

- Fixed Python `zstandard` decompression for RDR1 RSC resources whose zstd frame does not advertise decompressed content size.
- RSC expected decompressed size is now derived from RSC85/RSC05 flags.
- `.wgd` analysis now emits `referenced_strings.csv`, which follows virtual/physical pointers to likely string targets.
- `wgd_probe.first_names` now prefers referenced strings, so it reports useful gringo/resource names instead of early incidental ASCII from binary data.

## Validation performed in this environment

- `commongringos.wgd` recognized as `RSC85` type `18`.
- Expected decompressed size derived from flags: `806912` bytes.
- Decompressed payload SHA1 matched the uploaded unpacked payload: `41f7c097c902fc9695dba5e527266de9261d5539`.
- No-op payload edit/repack round-tripped to an identical decompressed payload SHA1.

## Guardrails

- Source RPF mutation remains blocked by this tool.
- Patch output should be staged to a patch folder and then applied through Code RED's copied-archive patch backend.
- Structural growth/editing of RSC arrays is still blocked until full format round-trip validators exist.
