# Code RED — Start Here

## What to launch

Use this order:

1. `Code_RED.bat` — best Windows entry point if you copy this launcher kit into the Code_RED folder.
2. `run_workbench.py` — preferred Python source entry point.
3. `python_workbench.py` — app implementation/fallback if the runner is missing.
4. `Code_RED.exe` / `Code RED.exe` — preferred packaged entry point if an EXE build exists.

Avoid launching these directly unless you are developing/building the app:

- `Program.cs`
- `RDR1MergeWorkbench.csproj`
- `UI/MainForm.cs`
- `_capture_*.py`
- files under `docs/`, `sample_workspace/`, or `test_inputs/`

## Current public GUI

The default Python GUI is now focused around two primary workflows:

- **Script Lab** for WSC/XSC/CSC/SCO viewing, inspection, recipe building, and same-size patched-copy output.
- **RPF Browser** for read-only RPF/ZIP inventory and report generation.

The old multi-button workbench was preserved as `python_workbench_legacy_button_sprawl.py` for reference, but it is no longer the default front door.

## Current feature truth

Code RED currently appears to be a conservative research/workbench tool, not a complete RPF injector/editor. It can inspect and route archive children into format-aware lanes, generate reports, preview/edit some extracted content, and produce reintegration/replacement plans. Some operations intentionally stop at plan files instead of mutating unknown binary containers.

## Research and log map

Start with `docs/research_index/README.md` when looking for notes, milestones, readmes, handoffs, RPF research, MP UI findings, native bridge work, or script/decompile status. It is a generated organization layer; original `logs/` tool outputs stay in place so existing tools do not lose their fixed report paths.

## Missing / not yet safe to claim

These features should be considered missing or staged until a later pass proves them:

- automatic write-back into `.rpf` archives
- true direct binary injection into `.wtd/.wtx/.wsf/.xtd/.xtx/.xsf`
- full embedded texture dictionary parsing
- full `.wft/.wfd/.wvd` mesh/fragment structural editing
- source-level script compile-back
- full vehicle/tune GUI integration, unless a separate Code RED Tuner folder exists

## Recommended folder cleanup

A clean user-facing package should have this shape:

```text
Code_RED/
  Code_RED.bat
  run_workbench.py
  python_workbench.py
  README_START_HERE.md
  data/
    natives.json
  docs/
  sample_workspace/
  test_inputs/
  UI/                 # source only
  Services/           # source only
  Models/             # source only
  RDR1MergeWorkbench.csproj  # source/build only
```

For a packaged Windows build, the root should instead contain one obvious `Code_RED.exe` plus a README, with source files moved into a `source/` folder or omitted.


## Xbox / Xenia Layer Resolver

Code RED includes a read-only Xbox layer resolver for Disc/base, layer_0, update, and DLC/content research.

Run the GUI:

```bat
python python_workbench.py
```

Then open the **Xbox Layers** tab and add layers in priority order. The resolver shows which layer owns the effective file path before you edit scripts or RPF contents.

CLI:

```bat
python tools\codered_xbox_layer_resolver.py --layer base=<base_extract> --layer layer0=<layer_0_extract> --out reports\xbox_layer_resolver
```

See `docs/XBOX_LAYER_RESOLVER.md`.

## New in Public GUI Pass 5

- Added `ISO/XDVDFS` GUI tab.
- Added `tools/codered_xiso_tool.py` for Xbox ISO indexing/extraction/replacement planning.
- Added `docs/XISO_XDVDFS_TOOL.md`.
- Original ISOs are never modified in-place.

## New in Public GUI Pass 6

- Added safe RPF replacement planning.
- Added exact-size staging with padding for smaller replacement RPFs.
- Added verified copied-ISO write-back for exact or smaller-padded replacements.
- Added overlay export for oversized RPF replacements.
- Added `docs/XISO_SAFE_RPF_REPLACEMENT.md`.
