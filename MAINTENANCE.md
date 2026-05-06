# Code RED Maintenance Notes

## Source of truth

Use this launcher from the repository root:

```bash
python run_workbench.py
```

The stable launcher enters `code_red_main.py`. The larger `python_workbench.py` file is the full research/workbench backend and still contains the deeper RPF6, script/toolchain, source-validation, Magic-RDR, SC-CL, and archive-proof lanes.

## Protected behavior

- RPF archives must be treated as game archives, not ZIP files.
- ZIP support is only for package/transport inspection.
- `.wsc`, `.xsc`, and `.sco` must remain routed to the Scripts lane.
- Script read/compile code in `python_workbench.py` should not be edited during lightweight UI cleanup.
- Archive write-back and mutation should stay staged unless a validated backend is attached.
- The full backend must continue exposing RPF6 audit/export, copied-archive proof, source validation, script tooling detection, Magic-RDR/SC-CL packaging, and safe copied-archive patch application.

## Anti-regression command

Run this before and after launcher, cleanup, archive, or script-lane changes:

```bash
python tools/codered_anti_regression.py
```

The guard uses tiny synthetic RPF/ZIP files. It checks stable-shell routing and verifies that `python_workbench.py` still exposes the full backend symbols needed to keep Code RED beyond a basic Magic-RDR/Codex-style browser.

## Cleanup rules for future commits

Do not commit these to Git:

- raw `*.rpf` game archives
- split archive fragments such as `*.z01`, `*.z02`, and similar
- packaged release/test zips, rars, or 7z files
- local `imports/`, `game/`, `logs/`, `dist/`, and `build/` outputs
- generated scan reports and temporary patch copies

## Safe local workflow

1. Drop real game archives into a local ignored folder such as `imports/`.
2. Launch with `python run_workbench.py`.
3. Use read-only archive inventory on `.rpf` files.
4. Run `python tools/codered_anti_regression.py` before committing UI or launcher changes.
5. Use the full `python_workbench.py` lane for deeper script/toolchain work until those features are migrated into the stable shell.

## Current status

The stable shell now restores RPF-first archive inventory and the headless `--scan-archive` command. The full backend remains separate and protected by the anti-regression guard so cleanup work does not silently remove deeper reading, proof, and toolchain capabilities.
