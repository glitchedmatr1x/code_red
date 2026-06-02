# Code RED SCO/RPF Probe

Safe investigation tools for Red Dead Redemption PC `.sco`/script-like binaries and `content.rpf` entries.

This folder contains no game files. It is for inspection, no-change rebuild tests, and same-size byte/string patch experiments only.

## Commands

```powershell
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py scan-sco input.sco --out reports\sco\input_scan.json
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py strings-sco input.sco --out reports\sco\input_strings.txt
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py compare-sco original.sco candidate.sco --out reports\sco\compare.json
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py patch-sco-strings input.sco --patch patches.json --out patched\input.sco
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py scan-rpf game\content.rpf --out reports\rpf_report.json
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py scan-rpf game\content.rpf --classify-entries --out reports\rpf_classified.json
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py bulk-scan-rpf-scripts game\content.rpf --out build\codered_real_probe\script_candidate_hunt
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py extract-rpf-entry game\content.rpf root/content/release64/init/rdr2init.sco --out scratch\rdr2init.sco
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py extract-candidate game\content.rpf 885 --out scratch\entry_885.bin
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py replace-rpf-entry game\content.rpf root/content/release64/init/rdr2init.sco patched\rdr2init.sco --out build\content_probe.rpf
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py nochange-replace-rpf-index game\content.rpf 885 scratch\entry_885.bin --out build\entry_885_nochange.rpf
```

`bulk-scan-rpf-scripts` is for hash-only archives. It extracts candidate entries by numeric index into temporary space, scans raw and decoded strings, ranks likely script resources by keyword groups, and writes:

- `script_candidate_inventory.json`
- `script_candidate_inventory.csv`
- `script_candidate_strings.csv`
- `script_candidate_keyword_hits.csv`
- `top_candidates.md`

It does not keep extracted entry payloads.

## Patch JSON

Same-size replacement:

```json
{
  "patches": [
    {
      "old": "FBI04",
      "new": "CRB04",
      "encoding": "utf-8",
      "max_replacements": 1
    }
  ]
}
```

Shorter replacement with explicit NUL padding:

```powershell
py -3 Code_RED\tools\codered_sco_probe\codered_sco_probe.py patch-sco-strings input.sco --patch patches.json --out patched.sco --allow-padding
```

Longer replacements are refused. The tool never changes file length.

## rdr2init.sco investigation flow

1. Extract the entry from a copied or test `content.rpf`.
2. Run `scan-sco` and `strings-sco`.
3. Run a no-change compare against a copied file.
4. Try one same-size string patch only.
5. Use `replace-rpf-entry` to build a copied RPF.
6. Re-scan the copied RPF and compare the extracted replacement bytes.

Do not replace the live `game\content.rpf` until a copied archive has been parsed, reopened, and read back cleanly.

## Safety

- The input RPF is never overwritten by `replace-rpf-entry`.
- Every string patch writes a manifest with changed offsets and before/after hashes.
- Readable strings are evidence anchors, not proof of behavior.
- Inserted logic, changed control flow, or length-changing strings require a real compiler/reassembler path and are out of scope here.
