# Code RED RDR1 Resource Lab v4 - Override Workflow

This pass adds a practical mod/override path for RDR1 resources, especially `.wgd` gringo dictionaries.

## New commands

### Search referenced strings

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat search-refs --input imports\commongringos.wgd --query revolver --out logs\rdr1_resource_lab\commongringos_search
```

This searches real strings reached through virtual/physical RSC pointers, not random ASCII noise.

### Override a referenced string

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat override-string --input imports\commongringos.wgd --old p_gen_stampPad01x --new p_gen_stampPad01y --out patches\commongringos_override.wgd --patch-root patches\wgd_override --internal-path commongringos.wgd
```

Rules:

- The old string must exist as a referenced C-string or raw C-string.
- The new string must be the same encoded length or shorter.
- Shorter replacements are padded with NUL bytes.
- The tool repacks the RSC wrapper after editing the decompressed payload.
- The source RPF is never edited directly.

### Apply staged patch folder to copied RPF

```powershell
.\Run_CodeRED_RDR1_Resource_Lab.bat patch-archive --archive game\gringores.rpf --patch-root patches\wgd_override --out game\patched\gringores.rpf
```

This delegates to Code RED's existing copied-archive patch backend.

## Current safety level

This is enough for controlled string/model reference swaps where the replacement name fits in the existing string slot. It is not yet a structural editor: it will not add gringos, grow arrays, relocate blocks, or rebuild new pointer tables.
