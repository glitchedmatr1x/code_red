# Code RED SC-CL Bitbucket Setup Report

Generated UTC: `2026-05-03T16:57:52Z`
Result: **NEEDS BUILD**
Bitbucket source: `https://bitbucket.org/scclteam/sc-cl.git`
Target dir: `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source`
git: `C:\Program Files\Git\cmd\git.EXE`
source_exists: `True`
llvm_source_root: `None`
SC-CL.exe: `None`
build_exit_code: `None`

## Actions

- Source folder already exists: D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source

## Warnings

- Source is staged, but llvm-14.0.0.src/CMakeLists.txt was not found. If build still fails, this may still be an incomplete source package.
- SC-CL.exe is not available yet. Build or obtain it before compile-output proof.

## Next Steps

- Clone manually if needed: git clone https://bitbucket.org/scclteam/sc-cl.git resources/SC-CL_bitbucket_source
- Probe/build: py -3 tools\codered_sccl_build_from_source.py --source "D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source" --adopt
- If SC-CL.exe is produced, run: py -3 tools\codered_sccl_easy_setup.py status --run-validator
- Then run: related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\run_build_then_compile_vehicle_menu_probe.bat
