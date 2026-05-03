# Code RED Script Workshop

Standalone scripting extension for Code RED.

Workflow target:

```text
scan -> read -> open -> edit -> export decompiled/readable -> import queue -> recompile queue
```

## Launch

Windows:

```bat
related_apps\CodeRED_Script_Workshop\Run_CodeRED_Script_Workshop.bat
```

Linux/macOS:

```bash
bash related_apps/CodeRED_Script_Workshop/run_codered_script_workshop.sh
```

CLI scan:

```bash
python3 related_apps/CodeRED_Script_Workshop/CodeRED_Script_Workshop.py scan --refresh
```

Windows compile proof plan:

```bat
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py compile-proof-plan
```

## Safety

- Source/text files are copied into `workspace/edit/` and `workspace/import_queue/`.
- C/C++ source candidates are copied into `workspace/recompile_queue/`.
- Compiled `.wsc`, `.csc`, `.xsc`, `.sco`, and `.ysc` files are read and exported as raw/readable reports only.
- Binary bytecode roundtrip is locked until a real Windows compiler/decompiler proof passes.

## VS Code

Open the Code RED repo folder in VS Code and use the tasks under `Terminal -> Run Task`.
