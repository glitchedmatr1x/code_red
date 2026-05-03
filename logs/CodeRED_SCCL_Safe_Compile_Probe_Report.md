# Code RED SC-CL Safe Compile Probe Report

Generated UTC: `2026-05-03T14:41:43Z`
Result: **NEEDS ATTENTION**
SC-CL.exe: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe`
Source: `related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/src/main.c`
Output dir: `related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/vehicle_menu_probe_build`

## Output Files

- `none`

## Commands

### SC-CL help
- exit: `3221225781`
- timed_out: `False`
- command: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe -help`

### compile attempt 1
- exit: `3221225781`
- timed_out: `False`
- command: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe -target=RDR_#SC -platform=X360 -out-dir D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\output\vehicle_menu_probe_build -name=vehicle_menu_probe D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_script_compile_lab_v1\src\main.c`

### compile attempt 2
- exit: `3221225781`
- timed_out: `False`
- command: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe -target=RDR_SCO -platform=X360 -out-dir D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\output\vehicle_menu_probe_build -name=vehicle_menu_probe D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_script_compile_lab_v1\src\main.c`

### compile attempt 3
- exit: `3221225781`
- timed_out: `False`
- command: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe -target=RDR_#SC -out-dir D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\output\vehicle_menu_probe_build -name=vehicle_menu_probe D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_script_compile_lab_v1\src\main.c`

### compile attempt 4
- exit: `3221225781`
- timed_out: `False`
- command: `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe -target=RDR_SCO -out-dir D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\output\vehicle_menu_probe_build -name=vehicle_menu_probe D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_script_compile_lab_v1\src\main.c`


## Warnings

- SC-CL did not produce a verified output file from the probe source.

## Next Steps

- Open logs\CodeRED_SCCL_Safe_Compile_Probe_Output.txt and inspect the first compile error.
- If SC-CL opens a GUI or hangs, rerun with a shorter timeout: py -3 tools\codered_sccl_safe_compile_probe.py --timeout 20
- Do not install/promote any compiled output until this probe passes.
