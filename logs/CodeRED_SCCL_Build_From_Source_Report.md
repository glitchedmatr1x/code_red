# Code RED SC-CL Build From Source Report

Generated UTC: `2026-05-03T14:04:27Z`
Result: **NEEDS BUILD**
Source: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
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
- CMakeLists.txt: `None`
- CMake source used: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src`
- Solutions:
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\LLVM.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\MenuBase\MenuBase.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\testing\test.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\clang-tidy-vs\ClangTidy.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\projects\MenuBase\MenuBase.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\projects\testing\test.sln`

## Skipped Solutions

- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\LLVM.sln` — stale generated LLVM.sln/ZERO_CHECK points at an old Code RED output path
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\MenuBase\MenuBase.sln` — example/test solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\testing\test.sln` — example/test solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln` — Visual Studio extension solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\clang-tidy-vs\ClangTidy.sln` — Visual Studio extension solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\projects\MenuBase\MenuBase.sln` — example/test solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\projects\testing\test.sln` — example/test solution, not SC-CL.exe

## CMake Source Diagnostics

- D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\CMakeLists.txt: appears to be a top-level CMake source root

## Attempts

### CMake configure clean LLVM source
- cwd: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
- exit: `1`
- skipped: ``
- command: `C:\Program Files\CMake\bin\cmake.EXE -S D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src -B D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\codered_llvm_build -A x64 -Thost=x64 -DLLVM_TARGETS_TO_BUILD=X86 -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5`

stdout tail:
```text
-- Selecting Windows SDK version 10.0.26100.0 to target Windows 10.0.19045.
-- Configuring incomplete, errors occurred!

```

stderr tail:
```text
CMake Deprecation Warning at CMakeLists.txt:3 (cmake_minimum_required):
  Compatibility with CMake < 3.10 will be removed from a future version of
  CMake.

  Update the VERSION argument <min> value.  Or, use the <min>...<max> syntax
  to tell CMake that the project requires at least <min> but has been updated
  to work with policies introduced by <max> or earlier.


CMake Error at CMakeLists.txt:14 (cmake_policy):
  Policy CMP0051 may not be set to OLD behavior because this version of CMake
  no longer supports it.  The policy was introduced in CMake version 3.1.0,
  and use of NEW behavior is now required.

  Please either update your CMakeLists.txt files to conform to the new
  behavior or use an older version of CMake that still supports the old
  behavior.  Run cmake --help-policy CMP0051 for more information.


CMake Error at CMakeLists.txt:257 (message):
  Apparently there is a previous in-source build,

  probably as the result of running `configure' and `make' on

  D:/Games/Red Dead Redemption/Code_RED/SC-CL-master/llvm-14.0.0.src.

  This may cause problems.  The suspicious files are:

  D:/Games/Red Dead
  Redemption/Code_RED/SC-CL-master/llvm-14.0.0.src/lib/Target/Hexagon/HexagonDepDecoders.inc



  Please clean the source directory.



```


## Warnings

- Generated/example/Visual Studio extension solutions were skipped; they are not SC-CL.exe build targets.
- SC-CL.exe was not produced. Review the CMake build output and the target list.

## Next Steps

- Open logs\CodeRED_SCCL_Build_From_Source_Output.txt and find the first CMake error after the policy fix.
- If configure succeeds but target SC-CL is unknown, build ALL_BUILD in Visual Studio from codered_llvm_build and then run the finalizer.
- After SC-CL.exe exists, run: py -3 tools\codered_sccl_finalize_build.py --validate --compile-helper
