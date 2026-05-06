# Code RED Maintenance Notes

## Source of truth

Use this launcher from the repository root:

```bash
python run_workbench.py
```

The current stable launcher enters the conservative `code_red_main.py` shell. The larger `python_workbench.py` file still contains the deeper research/workbench implementation, including script/toolchain lanes.

## Protected behavior

- RPF archives must be treated as game archives, not ZIP files.
- ZIP support is only for package/transport inspection.
- `.wsc`, `.xsc`, and `.sco` must remain routed to the Scripts lane.
- Script read/compile code in `python_workbench.py` should not be edited during lightweight UI cleanup.
- Archive write-back and mutation should stay staged unless a validated backend is attached.

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
4. Run the self-test before committing UI or launcher changes.
5. Use the full `python_workbench.py` lane for deeper script/toolchain work until those features are migrated into the stable shell.

## Current regression note

The root shell previously exposed `.rpf` in the Archives lane but only wired member scanning through ZIP. The next code pass should restore an RPF-first reader in the stable shell while preserving script lane routing and avoiding any changes to compile-back logic.
