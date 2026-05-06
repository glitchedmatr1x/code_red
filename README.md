# Code RED

Code RED is a read-first RDR resource workbench. The current safe launch path is:

```bash
python run_workbench.py
```

Optional direct launch with an archive or folder:

```bash
python run_workbench.py /path/to/content.rpf
```

Headless safety check:

```bash
python code_red_main.py --self-test
```

Headless archive inventory check:

```bash
python code_red_main.py --scan-archive /path/to/content.rpf
```

## Launch rules

- `run_workbench.py` is the source launcher.
- `code_red_main.py` is the conservative stable shell.
- `python_workbench.py` contains the larger research/workbench implementation and script/toolchain lanes.
- Do not launch project files, helper captures, generated reports, or archived test data as the app entry point.

## Archive rules

- RPF archives are first-class game archives and are scanned read-only.
- ZIP files are treated as package/transport archives only.
- Split ZIP fragments such as `.z01` through `.z09` are tracked as fragments, not game archives.
- Archive mutation/write-back stays staged unless a validated backend is attached.

## Script safety rules

- `.wsc`, `.xsc`, and `.sco` stay routed to the Scripts lane.
- The stable shell inventories script entries found inside RPF archives without compiling or mutating them.
- The heavier script read/compile tooling in `python_workbench.py` is intentionally left untouched by lightweight UI maintenance.

## Repository hygiene

Keep raw game data, generated reports, local imports, copied RPFs, build folders, logs, and packaged ZIP/RAR/7Z outputs out of Git. Use `imports/`, `game/`, `logs/`, and local drop folders at runtime, but do not commit their contents.
