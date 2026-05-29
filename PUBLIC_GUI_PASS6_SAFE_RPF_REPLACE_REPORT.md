# Code RED Public GUI Pass 6 - Safe RPF Replacement

Pass 6 stabilizes the Xbox ISO / XDVDFS lane for RPF replacement.

## Added

- `prepare-exact` command to create exact-size padded replacement files.
- `replace-copy-safe` command to write exact or smaller-padded replacements into a copied ISO and verify the written region.
- `export-overlay` command for larger replacements that must not be sector-written into the ISO.
- Replacement planning now reports:
  - original file size
  - allocated bytes
  - replacement size
  - exact-size status
  - smaller-with-padding status
  - oversize refusal status
  - bytes to pad
  - rebuild/overlay recommendation
- GUI buttons in the ISO/XDVDFS tab:
  - Plan RPF Replace
  - Stage Exact/Padded
  - Export Overlay
- Documentation: `docs/XISO_SAFE_RPF_REPLACEMENT.md`

## Safety Policy

- Original ISOs are never modified in place.
- Larger replacements are refused for ISO write-back.
- Smaller replacements are padded back to the original XDVDFS file size.
- Copy-write output is verified by hashing the written region.

## Validation

Synthetic XDVDFS self-test passed:

- index synthetic ISO
- extract `layer_0.rpf`
- replace with a smaller staged file
- verify padded write-back into copied ISO
- confirm oversized replacement is refused

No game files are included in this public package.
