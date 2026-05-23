# Code RED RDR1 Resource Lab v5 - Weapon Lasso Override

Adds a guarded batch override for WGD referenced weapon fragment strings.

## New commands

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat weapon-lasso-override --input imports\commongringos.wgd --out patches\commongringos_lasso_override.wgd --patch-root patches\wgd_lasso_override --internal-path commongringos.wgd
```

This replaces referenced substrings:

- `revolver_cattleman01x` -> `melee_lasso01x`
- `revolver_schofield01x` -> `melee_lasso01x`

The replacement is shorter, so v5 writes the new string and NUL-pads the rest of the old substring. This preserves payload layout, pointers, and arrays.

General batch command:

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat batch-override-refs --input imports\commongringos.wgd --map "old1=new1,old2=new2" --out patches\output.wgd --patch-root patches\my_patch --internal-path commongringos.wgd
```

The map can also be a JSON file containing either an object or a list of `{ "old": "...", "new": "..." }` entries.

## Guardrails

- Source file is not modified.
- Source RPF is not modified.
- Replacement substrings must be equal-length or shorter.
- Shorter replacements are NUL padded.
- No array growth, pointer relocation, or structural gringo rebuild is performed.
- Apply to RPF only through copied-archive patch flow.

## Tested against uploaded commongringos.wgd

- Targets modified: 11
- `revolver_cattleman01x` remaining referenced strings: 0
- `revolver_schofield01x` remaining referenced strings: 0
- `melee_lasso01x` referenced strings after patch: 12, including one original existing lasso reference
- Repacked RSC reopened and decompressed successfully
