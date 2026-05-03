# Code RED SC-CL Safe Compile Probe Report

Generated UTC: `2026-05-03T15:54:18Z`
Result: **NEEDS ATTENTION**
SC-CL.exe: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe`
Source: `related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/src/main.c`
Output dir: `related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/vehicle_menu_probe_build`

## Output Files

- `none`

## Commands

### SC-CL help
- exit: `3221225781`
- exit_hex: `0xC0000135`
- timed_out: `False`
- command: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe -help`


## Warnings

- SC-CL.exe cannot launch: 0xC0000135 / STATUS_DLL_NOT_FOUND. A required DLL/runtime is missing.

## Next Steps

- Run: py -3 tools\codered_sccl_dependency_probe.py
- Install/repair Microsoft Visual C++ Redistributable 2015-2022 x64 if runtime DLLs are missing.
- If SC-CL.exe came from a build folder, copy SC-CL.exe together with its adjacent LLVM/Clang DLLs into the build kit folder.
- After dependency probe passes, rerun: py -3 tools\codered_sccl_safe_compile_probe.py --timeout 30
