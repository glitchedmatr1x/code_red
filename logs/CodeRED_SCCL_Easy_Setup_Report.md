# Code RED SC-CL Easy Setup Report

Generated UTC: `2026-05-03T12:17:42Z`
Result: **NEEDS SC-CL**

## Detected Tools

- SC-CL.exe: `None`
- cl.exe: `None`
- MSBuild: `C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe`
- vswhere: `C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe`
- Python: `C:\Users\glitc\AppData\Local\Programs\Python\Python312\python.exe`
- Windows host: `True`

## Actions

- Adopt skipped because a placeholder path was supplied.
- Script compile validation exit: 0

## Warnings

- The --sccl value is still a placeholder. Replace PATH_TO_SC-CL.exe with the real file path, or put SC-CL.exe in resources\SC-CL_DROP_HERE.
- SC-CL.exe is not staged yet. This blocks real compiled-script output, but not scan/read/edit/export queue preparation.

## Next Steps

- `Run: py -3 tools\codered_sccl_source_probe.py --source "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master"`
- `If the source probe says RDR-ready but no exe exists, build SC-CL or obtain the Windows SC-CL.exe.`
- `Place the real SC-CL.exe at: resources\SC-CL_DROP_HERE\SC-CL.exe`
- `Run: py -3 tools\codered_sccl_easy_setup.py adopt --sccl resources\SC-CL_DROP_HERE\SC-CL.exe --run-validator`

## Searched SC-CL Paths

- `D:\Games\Red Dead Redemption\Code_RED\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_DROP_HERE\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL-master\bin\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL-master\llvm-14.0.0.src\MinSizeRel\bin\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe`
- `D:\Games\Red Dead Redemption\Code_RED\related_apps\code_red_sccl_attempt_bundle_v1\code_red_script_compile_lab_v1\SC-CL.exe`
