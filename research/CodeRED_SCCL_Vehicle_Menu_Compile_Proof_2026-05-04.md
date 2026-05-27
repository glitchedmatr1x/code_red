# Code RED SC-CL Vehicle Menu Compile Proof — 2026-05-04

## Result

The active SC-CL vehicle menu probe reached a clean compile result:

```text
[CodeRED] SC-CL exit: 0
```

## Command sequence used

```powershell
powershell -ExecutionPolicy Bypass -File tools\Repair_CodeRED_SCCL_Project_Include.ps1
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```

## Header promotion proof

The repair script detected fake/proof headers and promoted real SC-CL headers from:

```text
D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\include
```

It backed up the older headers under:

```text
script_compiling\sccl\obsolete\headers_20260504_162107
```

## Validator proof

The validator passed with real-header checks:

```text
project_header_looks_real_sccl: True
project_header_is_not_fake_shim: True
lane_header_is_not_fake_shim: True
create_actor_uses_real_vector3_signature: True
source_uses_vector3_create_actor_call: True
source_does_not_use_loose_float_create_actor: True
source_does_not_use_unverified_Vector3_constructor: True
subtitle_call_uses_real_8_arg_shape: True
missing_symbols: []
RESULT: PASS
```

## Compile proof

SC-CL launched from the staged active output path:

```text
script_compiling\sccl\output\SC-CL.exe
```

The compiler started:

```text
Starting SC-CL ALPHA 0.7.3.5 running Clang 3.8.1
```

It warned about no compilation database, then compiled the active source:

```text
script_compiling\sccl\projects\vehicle_menu_probe\src\main.c
```

Final result:

```text
[CodeRED] SC-CL exit: 0
```

## Meaning

This proves the current active lane can:

- reject fake/proof headers
- promote real SC-CL headers
- validate the vehicle menu source against real signatures
- stage a working SC-CL runtime
- compile the active vehicle menu probe successfully

## Next checks

Before any install/import attempt:

1. list the compiled output files under `script_compiling\sccl\output\vehicle_menu_probe`
2. hash the produced `.xsc` / `.sco` output files
3. inspect output size/path naming
4. keep this as a proof artifact only until archive install/import is separately proven

Do not install the compiled script into the game yet.
