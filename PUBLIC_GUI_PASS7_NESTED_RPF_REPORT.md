# Code RED Public GUI Pass 7 — Nested RPF Patches Inside ISO

Pass 7 adds a guarded direct-ISO nested patch lane for Xbox/Xenia research.

## Added

- `nested-find` command for finding bytes/text inside an ISO-contained file such as `layer_0.rpf`.
- `nested-plan-patch` command for planning a same-size patch inside an ISO-contained RPF/file.
- `nested-patch-copy` command for writing that patch to a copied output ISO only.
- GUI buttons in the ISO/XDVDFS tab:
  - Find Text Inside
  - Nested Patch Copy
- Documentation in `docs/XISO_XDVDFS_TOOL.md`.

## Safety behavior

- Original ISO is never modified in-place.
- Old bytes must match exactly before writing.
- New bytes must be the same byte length as old bytes.
- Patch is written into a copied output ISO.
- New bytes are verified after writing.
- Larger inner-file imports are refused by design.

## Best use cases

- Same-length XML/UI route edits.
- Same-length script path swaps.
- Same-length string probes.
- Exact byte constant experiments.

## Not supported in this pass

- RPF table rebuilding.
- Adding new files inside an RPF.
- Growing files inside an RPF.
- Expanding or relayouting XDVDFS.
- Direct original ISO mutation.
