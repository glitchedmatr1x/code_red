# Code RED RDR1 Resource Lab v7

## Fix

v6 successfully staged the lasso WGD override, but Code RED's older copied-archive patch backend blocked RSC resource replacement with:

```text
Unsupported or unknown payload recompression codec in fallback path.
```

v7 avoids that fallback. The Resource Lab now repacks zstd RSC resources to the exact original byte length when possible, using a standards-compliant Zstandard skippable frame for padding. This lets the archive patch step overwrite the same byte span in a copied RPF without growing entries, relocating data, or changing RPF table-of-contents sizes.

## New behavior

- `weapon-lasso-override` now preserves the original `.wgd` file size.
- `batch-override-refs` / referenced-string overrides use exact-size RSC output for zstd resources.
- `patch-archive` now uses a narrow raw exact-size overwrite path for staged files.
- Source RPFs are still never modified directly.

## Expected flow

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat weapon-lasso-override --input imports\commongringos.wgd --out patches\commongringos_lasso_override.wgd --patch-root patches\wgd_lasso_override --internal-path root/gringores/commongringos.wgd
```

Then:

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat patch-archive --archive game\gringores.rpf --patch-root patches\wgd_lasso_override --out game\patched\gringores.rpf
```

## Self-test with uploaded commongringos.wgd

- Source size: `176347`
- Patched output size: `176347`
- Fit mode: `zstd-exact-with-skippable-padding`
- Zstd level used: `18`
- Skippable padding bytes: `1169`
- Removed old references: `revolver_cattleman01x`, `revolver_schofield01x`
- New `melee_lasso01x` referenced strings after decompression: `12`
