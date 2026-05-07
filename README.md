# Code RED

Code RED is a read-first RDR resource workbench. The current safe launch path is:

```bat
Code_RED.bat
```

Python fallback:

```bat
py -3 main.py
```

Decompile / recompile capability check:

```bat
Run_CodeRED_Decompile_Recompile_Hub.bat --validate
```

RPF edit lab / inventory entry point:

```bat
Run_CodeRED_RPF_Edit_Lab.bat
```

## Launch rules

- `Code_RED.bat` is the Windows source launcher.
- `main.py` is the canonical Python app entry point.
- `run_workbench.py` is compatibility only.
- `code_red_main.py` is the conservative stable shell/fallback.
- `python_workbench.py` contains the larger research/workbench implementation and script/toolchain lanes.
- Do not launch project files, helper captures, generated reports, or archived test data as the app entry point.

## Archive rules

- RPF archives are first-class game archives and are scanned read-only.
- ZIP files are treated as package/transport archives only.
- Split ZIP fragments such as `.z01` through `.z09` are tracked as fragments, not game archives.
- Archive mutation/write-back stays staged to copied archives unless a validated backend is attached.
- Use `tools/codered_rpf_utils.py` for RPF inventory/extract and `tools/codered_rpf_utils_patch.py` for patch-folder apply to copied archives.

## Script safety rules

- `.wsc`, `.xsc`, and `.sco` stay routed to the Scripts lane.
- The stable shell inventories script entries found inside RPF archives without compiling or mutating them.
- Source compile is routed through `script_compiling/sccl/`.
- Existing compiled `.wsc/.csc/.xsc/.sco` bytecode-to-source decompile is not proven yet; Code RED exports readable/pseudo-decompile reports until a real decompiler is available.

## Repository hygiene

Keep raw game data, generated reports, local imports, copied RPFs, build folders, logs, and packaged ZIP/RAR/7Z outputs out of Git. Use `imports/`, `game/`, `logs/`, and local drop folders at runtime, but do not commit their contents.
