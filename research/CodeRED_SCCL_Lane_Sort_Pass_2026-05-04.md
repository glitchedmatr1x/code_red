# Code RED SC-CL Lane Sort Pass â€” 2026-05-04

## Scope

Only the SC-CL / script-compiling lane was sorted.

## Active lane

`	ext
script_compiling/sccl/
`

## Preserved obsolete folders

`	ext
script_compiling/sccl/obsolete/code_red_sccl_attempt_bundle_v1
script_compiling/sccl/obsolete/compiled_vehicle_menu_probe
`

## Why

The old compile files were scattered under elated_apps, making it unclear which compiler path, headers, CMake files, and proof source should be used.

## Rule

Do not delete proof material. Move wrong-code or old-code compile attempts into obsolete/ until verified.

## Next validation

`at
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
`

If the compiler is not under script_compiling\sccl\output\SC-CL.exe, set SCCL_EXE first.
