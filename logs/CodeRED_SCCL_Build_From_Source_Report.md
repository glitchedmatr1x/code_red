# Code RED SC-CL Build From Source Report

Generated UTC: `2026-05-03T16:58:04Z`
Result: **NEEDS BUILD**
Source: `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source`
SC-CL.exe: `None`
Adopted to: `None`

## RDR Readiness Markers

- `Red Dead Redemption`
- `RDR_SCO`
- `RDR_#SC`
- `XSC format`
- `CSC format`
- `SCO format`

## Build Systems

- MSBuild: `C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe`
- CMake: `C:\Program Files\CMake\bin\cmake.EXE`
- CMakeLists.txt: `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source\CMakeLists.txt`
- CMake source used: `None`
- Solutions:
  - `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source\bin\projects\MenuBase\MenuBase.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source\bin\projects\testing\test.sln`

## Skipped Solutions

- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source\bin\projects\MenuBase\MenuBase.sln` — example/test solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source\bin\projects\testing\test.sln` — example/test solution, not SC-CL.exe

## CMake Source Diagnostics

- D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source\CMakeLists.txt: CMakeLists.txt uses Clang/LLVM tool macros and is not a standalone top-level CMake root
- D:\Games\Red Dead Redemption\Code_RED\resources\SC-CL_bitbucket_source\llvm-14.0.0.src\CMakeLists.txt: missing. A Clang tool-style SC-CL source needs the full LLVM source root or a prebuilt exe.

## Attempts


## Warnings

- Generated/example/Visual Studio extension solutions were skipped; they are not SC-CL.exe build targets.
- No standalone top-level CMake source root was found. Need llvm-14.0.0.src/CMakeLists.txt or a prebuilt exe.
- SC-CL.exe was not produced. Review the CMake build output and the target list.

## Next Steps

- Open logs\CodeRED_SCCL_Build_From_Source_Output.txt and find the first CMake error after the policy fix.
- If configure succeeds but target SC-CL is unknown, build ALL_BUILD in Visual Studio from codered_llvm_build and then run the finalizer.
- After SC-CL.exe exists, run: py -3 tools\codered_sccl_finalize_build.py --validate --compile-helper
