# Code RED WSC Bounds Probe

Rollback-safe WSC bounds patch tool for RDR1 scripts.

Known-good workflow:
- RSC85 type-2 script
- AES key from `rdr.exe`
- Zstandard decode/repack
- `u16be` bounds patch

## Important v5 note
Decoded WSC vehicle values are binary operands, not ASCII text like `,1188,`.
The tool does not patch text digit chains. It patches exact selected low/high values in the chosen binary integer format.

v5 adds:
- `--preview-only` to list candidate replacement contexts without writing a WSC
- `--max-replacements` to block broad accidental changes
- `--context-mode prev-byte` only for research when a proven bytecode context is known
- `.preview_hits.csv` for reviewing offsets and surrounding bytes

Default recommended mode is `--context-mode none` with a low `--max-replacements`, because the earlier hardcoded `0x41` context guard was too strict for non-WagonThief scripts.
