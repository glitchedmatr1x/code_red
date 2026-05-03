# Code RED Script Workshop Windows Self-Test Proof

Date: 2026-05-03

## Command

```bat
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py self-test
```

## User-reported result

```json
{
  "ok": true,
  "errors": []
}
```

## Meaning

The standalone Script Workshop extension successfully passed its Windows-side self-test.

This proves the current safe scripting pipeline can initialize and validate the generated workflow outputs:

```text
scan -> read -> open/edit workspace -> export readable/decompiled -> import queue -> recompile queue -> proof helpers
```

## Still proof-gated

This does not yet prove full compiled binary script roundtrip for `.wsc`, `.xsc`, `.sco`, `.csc`, or `.ysc` files. The next proof target is the Windows compile proof helper, followed by controlled compiled-output verification.
