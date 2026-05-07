# Code RED Maintenance Notes

## Source of truth

Use this launcher from the repository root:

```bat
Code_RED.bat
```

The canonical Python entry point is `main.py`. `run_workbench.py` is only a compatibility shim. The larger `python_workbench.py` file is the full research/workbench backend and still contains the deeper RPF6, script/toolchain, source-validation, Magic-RDR, SC-CL, and archive-proof lanes.

## Protected behavior

- RPF archives must be treated as game archives, not ZIP files.
- ZIP support is only for package/transport inspection.
- `.wsc`, `.xsc`, `.sco`, and script-adjacent `.wsv` resources must remain routed to script/tooling workflows.
- Script read/compile code in `python_workbench.py` should not be edited during lightweight UI cleanup.
- Archive write-back and mutation should stay staged to copied archives unless a validated backend is attached.
- The full backend must continue exposing RPF6 audit/export, copied-archive proof, source validation, script tooling detection, Magic-RDR/SC-CL packaging, and safe copied-archive patch application.
- True compiled-script bytecode-to-source decompilation must not be claimed until a real decompiler is proven in this checkout.

## Script Workshop

Use this when the compiler/toolchain is present:

```bash
python tools/codered_script_workshop.py --source scripts --out logs/script_workshop
```

The workshop is compiler-aware but safe by default. It inventories source/script resources, detects likely SC-CL/Magic-RDR/compiler resources, and writes a compile plan. It only runs compile commands when both `--compile` and an explicit `--compiler-template` are provided, so Code RED does not guess the compiler syntax.

Example explicit compile template:

```bash
python tools/codered_script_workshop.py --source scripts --out build/scripts --compile --compiler-template '"{compiler}" "{source}" -o "{output}"'
```

## Anti-regression command

Run this before and after launcher, cleanup, archive, or script-lane changes:

```bash
python tools/codered_anti_regression.py
```

## Decompile / recompile hub

Run this after archive/script/tooling changes:

```bat
Run_CodeRED_Decompile_Recompile_Hub.bat --validate
```

Current proven lanes:

- RPF6 inventory and extraction.
- RPF patch-folder apply to a copied archive.
- Source/text script read/edit/export queues.
- SC-CL source compile proof through `script_compiling/sccl/`.

Blocked lane:

- Existing compiled `.wsc/.csc/.xsc/.sco` bytecode-to-source decompile.

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
5. Use `tools/codered_script_workshop.py` for compiler-aware planning and controlled script builds.
6. Use the full `python_workbench.py` lane for deeper script/toolchain work until those features are migrated into the stable shell.

## Current status

The stable shell now restores RPF-first archive inventory and the headless `--scan-archive` command. The full backend remains separate and protected by the anti-regression guard so cleanup work does not silently remove deeper reading, proof, and toolchain capabilities. The Script Workshop now provides a controlled path for compiler-aware script inventory, planning, and explicit build execution.
