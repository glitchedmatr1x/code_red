# Code RED RDR1 Resource Lab Drop-in

This drop-in adds a conservative RDR1 resource lane to Code RED. It is designed around the Code RED rule that archives are read-first and that write-back should be staged to patch folders/copies.

## What this adds

- `tools/codered_rdr1_resource_lab.py`
- `Run_CodeRED_RDR1_Resource_Lab.bat`
- `install_optional_rdr1_resource_lab_deps.bat`
- `requirements_CodeRED_RDR1_Resource_Lab.txt`
- format status docs and self-test logs

## Scope

The lab supports broad **view/analyze** coverage for RDR1 RSC/RPF-adjacent resources and a guarded **same-size edit/stage** workflow for every listed type. It does not directly mutate source RPF archives.

### Strong view/analyze formats

`.wgd`, `.wtd`, `.wst`, `.sst`, `.strtbl`, `.wfd`, `.wvd`, `.wft`, `.wsi`, `.wcg`, `.wsg`, `.wsp`, `.wtb`, `.wat`, `.wcdt`, `.wedt`, `.wpfl`, `.wnm`, `.wsf`, `.wbd`, `.was`, `.fonttex`

### Edit policy

| Category | Current policy |
|---|---|
| Plain text resources | Direct text edit, then stage as patch folder |
| `.wtd`, `.wst`, `.sst`, `.strtbl`, `.wfd`, `.wvd` | Candidate semantic types; currently safe binary/string patch until validators are added |
| `.wgd` and other structured RSC resources | View/analyze first; payload same-size patch only; no array growth |
| RPF archives | Read/inventory/extract delegated to existing Code RED tools; patch folders are applied to copied archives using the existing patch backend |

## Install

Unzip this package into the root of Code RED so that the files land next to `Code_RED.bat`, `main.py`, and `tools/`.

Optional but recommended for compressed RSC resources:

```bat
install_optional_rdr1_resource_lab_deps.bat
```

The lab can also use `zstd.exe` if it is already on PATH.

## Common commands

Analyze an extracted resource:

```bat
Run_CodeRED_RDR1_Resource_Lab.bat analyze --input imports\commongringos.wgd --out logs\rdr1_resource_lab\commongringos
```

Unpack an RSC resource payload:

```bat
Run_CodeRED_RDR1_Resource_Lab.bat unpack-rsc --input imports\commongringos.wgd --out logs\rdr1_resource_lab\commongringos.payload.bin
```

Write an edit spec template:

```bat
Run_CodeRED_RDR1_Resource_Lab.bat template --input imports\commongringos.wgd --out imports\commongringos_edit_spec.json
```

Apply a guarded edit spec and stage it into a patch folder:

```bat
Run_CodeRED_RDR1_Resource_Lab.bat edit --spec imports\commongringos_edit_spec.json
```

Inventory an RPF using Code RED's existing RPF backend:

```bat
Run_CodeRED_RDR1_Resource_Lab.bat rpf-inventory --archive game\gringores.rpf --out logs\rdr1_resource_lab\gringores_inventory
```

Extract one entry from an RPF using Code RED's existing RPF backend:

```bat
Run_CodeRED_RDR1_Resource_Lab.bat rpf-extract --archive game\gringores.rpf --entry commongringos.wgd --out imports\gringores_extract
```

After a patch folder is staged, use Code RED's existing copied-archive patch lane:

```bat
py -3 tools\codered_rpf_utils_patch.py --archive game\gringores.rpf --patch-root patches\rdr1_resource_lab_patch --out game\patched\gringores.rpf
```

## Edit spec format

The template command creates JSON like this:

```json
{
  "source": "imports/commongringos.wgd",
  "output": "imports/commongringos.edited.wgd",
  "scope": "payload",
  "same_size": true,
  "internal_path": "PUT/RPF/INTERNAL/PATH/commongringos.wgd",
  "patch_root": "patches/rdr1_resource_lab_patch",
  "edits": [
    {
      "kind": "replace_string",
      "old": "OLD_TEXT",
      "new": "NEW_TEXT",
      "encoding": "ascii",
      "pad": "nul",
      "count": 1
    }
  ]
}
```

Supported edit kinds:

- `replace_string`
- `replace_bytes`
- `set_u8`
- `set_u16`
- `set_u32`
- `set_i32`
- `set_float32`

For compressed RSC files, `scope: "payload"` edits the decompressed payload and repacks the original RSC wrapper. For raw/unpacked payloads, use `scope: "file"`.

## Guardrails

- The original input file is never overwritten.
- Source RPFs are never mutated by this tool.
- Same-size edits are the default.
- Structural array/list growth is deliberately blocked until full per-format round-trip validators are added.
- Every edit writes an `.edit_report.json` with old/new hashes and staged path.

## Why this is not a blind full XML editor yet

The public RDR1 CodeX research modules expose valuable readers and analyzers for many resource types. Some XML import paths are intentionally disabled/commented out in those projects because not every resource is proven safe to reimport. This drop-in follows that same conservative rule: enable viewing broadly, then enable editing through staged same-size patches first, and only promote a format to semantic editing after round-trip tests pass.
