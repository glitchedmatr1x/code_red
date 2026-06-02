# Code RED RPF Experiment Runner

`codered_rpf_experiment.py` runs a repeatable safety pipeline for one RPF entry.

It never overwrites the source RPF. Copied archives are written under the output folder you choose, normally under `build/experiments` or `build/codered_real_probe`.

## Basic Usage

```powershell
py -3 tools\codered_sco_probe\codered_rpf_experiment.py `
  --rpf "D:\Games\Red Dead Redemption\content.rpf" `
  --entry "content/release64/init/rdr2init.sco" `
  --out build\experiments\rdr2init_sco_probe
```

With an optional same-size patch:

```powershell
py -3 tools\codered_sco_probe\codered_rpf_experiment.py `
  --rpf "D:\Games\Red Dead Redemption\content.rpf" `
  --entry "content/release64/init/rdr2init.sco" `
  --out build\experiments\rdr2init_sco_probe_patch `
  --patch tools\codered_sco_probe\patch_examples\rdr2init_safe_probe.example.json
```

## Outputs

Each run writes:

- `experiment_manifest.json`
- `experiment_report.md`
- `scan/source_rpf_scan.json`
- `scan/extracted_file_scan.json`
- `scan/extracted_strings.txt`
- `reports/nochange_compare.json`
- `reports/nochange_rpf_replace_manifest.json`
- optional patched compare and patched RPF manifest files

## Interpreting Changed Offsets

Changed offsets are byte offsets in the extracted entry, not global RPF offsets.

Each changed offset record includes `offset`, `offset_hex`, `old_hex`, `new_hex`, `old_text`, `new_text`, and byte lengths.

If a patch changes more offsets than expected, treat the build as unsafe and do not install it.

## Why No-Change Rebuild Comes First

A no-change rebuild proves the archive replacement path before a gameplay patch is involved.

If the no-change replacement cannot be extracted, reinserted, and validated, a patched replacement is not meaningful. Fix the RPF path first.

## WSC-Only, SCO-Only, And WSC+SCO Testing

`rdr2init.wsc` and `rdr2init.sco` may be separate runtime layers.

Test in this order:

1. WSC-only no-change.
2. SCO-only no-change.
3. WSC-only same-size patch.
4. SCO-only same-size patch.
5. Matched WSC+SCO patch only if the separate tests are stable.

This avoids mixing two possible crash sources in one build.

## Why `rdr2init.sco` Is Riskier Than String Scanning

String scanning only proves that bytes exist in the file.

Changing `rdr2init.sco` can alter script behavior, registry paths, or loader assumptions. Even same-size string edits can break runtime lookup if the string is part of a hash, state machine, or native-call argument. Treat every patched SCO as experimental until the no-change rebuild and a single small patch both test cleanly.
