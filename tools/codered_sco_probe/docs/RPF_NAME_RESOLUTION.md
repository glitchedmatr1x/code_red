# RPF Name Resolution Notes

Some Red Dead Redemption PC RPFs do not expose full readable paths through the current parser. Entries may appear as hash-only paths, numeric indexes, or partially resolved names.

## Why Code RED Needs Index And Hash Extraction

If a target like `content/release64/init/rdr2init.sco` is not resolved by name, the archive may still contain the payload under a hashed path. Code RED must therefore support:

- full backend entry dumps
- raw byte string search across the whole archive
- per-entry magic/type classification
- extraction by numeric backend index

These steps let us find candidate entries without guessing gameplay patches.

## Using MagicRDR As A Name Dictionary

If MagicRDR can extract named files from the same archive, scan that extracted folder with:

```powershell
py -3 tools\codered_sco_probe\codered_sco_probe.py scan-extracted-folder extracted_root --out build\codered_real_probe\folder_report.json
```

The extracted folder can provide readable filenames and relative paths that are missing from Code RED's current RPF parse.

## Safe Patch Gate

No SCO/WSC patch should proceed until the target entry can be:

1. identified by path, hash path, or index
2. extracted
3. scanned
4. replaced unchanged into a copied RPF
5. read back and verified

If no-change replacement fails, patched replacement is not meaningful yet.

## Useful Commands

Dump every backend-visible entry:

```powershell
py -3 tools\codered_sco_probe\codered_sco_probe.py scan-rpf game\content.rpf --dump-all-entries --out build\codered_real_probe\rpf_inventory\all_entries.json
```

Search raw archive bytes:

```powershell
py -3 tools\codered_sco_probe\codered_sco_probe.py scan-rpf game\content.rpf --raw-string-search rdr2init --raw-string-search playercar --out build\codered_real_probe\rpf_inventory\raw_strings.json
```

Classify all entries:

```powershell
py -3 tools\codered_sco_probe\codered_sco_probe.py scan-rpf game\content.rpf --classify-entries --out build\codered_real_probe\rpf_inventory\classified_entries.json
```

Extract by index:

```powershell
py -3 tools\codered_sco_probe\codered_sco_probe.py extract-rpf-entry-index game\content.rpf 123 --out build\codered_real_probe\entry_123.bin
```
