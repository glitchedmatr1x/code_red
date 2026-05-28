# Code Red Syringe v0.3 Lite

This version removes the bad workflow.

It does **not** move Magic-RDR.
It does **not** open Magic-RDR and try to inject while you watch.
It does **not** claim injection when nothing changed.

## What it does

By default, Syringe builds a verified patch package from a changed-files folder or zip:

- `manifest.csv`
- `commands.txt`
- `patch_files/...`
- `directory_imports/...`

The target `.rpf` is only inspected for type/name. It is not modified in package-only mode.

## Easiest test

Double-click:

```text
Run_Self_Test.bat
```

Or run:

```bat
py -3 code_red_syringe.py --self-test
```

## Easiest package build

Put one target `.rpf` beside the app, then drag a changed-files zip onto:

```text
Build_Patch_Package.bat
```

Or run:

```bat
py -3 code_red_syringe.py --replacements FW_TUNE_PASS5_LEVELS_REFGROUPS_CHANGED_FILES_ONLY.zip --rpf tune_d11generic.rpf
```

Outputs are created in:

```text
__syringe_output__
```

## Advanced headless writer mode

Only use this if you have a real command-line/headless RPF writer. Do not use it for a visible GUI editor.

1. Run:

```bat
py -3 code_red_syringe.py --init-config
```

2. Edit `CodeRedSyringe.config.json`:

```json
"writer": {
  "enabled": true,
  "executable": "D:/Path/To/HeadlessRpfWriter.exe",
  "command_template": "{writer} -replace {rpf} {internal_dir} {import_dir} -current"
}
```

3. Run with `--apply`.

Syringe backs up the RPF and verifies the archive bytes changed before reporting injected files.
