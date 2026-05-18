# Code RED RDR1 Resource Lab Self-Test

Version: `v4`

## Status

- zstandard_python: `False`
- zstd_cli: `/usr/bin/zstd`
- format count: `22`

## Search refs test

Input: `/mnt/data/commongringos.wgd`
Query: `stamp`
Matches: `2`
Payload source: `rsc-decompressed`
Payload size: `806912`

## Override string test

Old: `p_gen_stampPad01x`
New: `p_gen_stampPad01y`
Targets found: `1`
Targets modified: `1`
Output reopens: `True`
Verification payload source: `rsc-decompressed`
Source RPF mutation: blocked/not used

## Result

PASS: search-refs and override-string completed, the output RSC reopened, and the payload stayed the same size while changing only the selected C-string bytes.
