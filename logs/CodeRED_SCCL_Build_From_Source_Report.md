# Code RED SC-CL Build From Source Report

Generated UTC: `2026-05-03T13:15:12Z`
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
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\projects\MenuBase\MenuBase.sln` — example/test solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\projects\testing\test.sln` — example/test solution, not SC-CL.exe

## CMake Source Diagnostics

- D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\CMakeLists.txt: appears to be a top-level CMake source root

## Attempts

### MSBuild Release x64
- cwd: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
- exit: `1`
- skipped: ``
- command: `C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln /m /p:Configuration=Release /p:Platform=x64`

stdout tail:
```text
MSBuild version 17.14.40+3e7442088 for .NET Framework
Build started 5/3/2026 6:15:16 AM.

     1>Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" on node 1 (default targets).
     1>D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln.metaproj : error MSB4126: The specified solution configuration "Release|x64" is invalid. Please specify a valid solution configuration using the Configuration and Platform properties (e.g. MSBuild.exe Solution.sln /p:Configuration=Debug /p:Platform="Any CPU") or leave those properties blank to use the default solution configuration. [D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln]
     1>Done Building Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" (default targets) -- FAILED.

Build FAILED.

       "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" (default target) (1) ->
       (ValidateSolutionConfiguration target) -> 
         D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln.metaproj : error MSB4126: The specified solution configuration "Release|x64" is invalid. Please specify a valid solution configuration using the Configuration and Platform properties (e.g. MSBuild.exe Solution.sln /p:Configuration=Debug /p:Platform="Any CPU") or leave those properties blank to use the default solution configuration. [D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln]

    0 Warning(s)
    1 Error(s)

Time Elapsed 00:00:00.04

```

### MSBuild Release Win32
- cwd: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
- exit: `1`
- skipped: ``
- command: `C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln /m /p:Configuration=Release /p:Platform=Win32`

stdout tail:
```text
MSBuild version 17.14.40+3e7442088 for .NET Framework
Build started 5/3/2026 6:15:18 AM.

     1>Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" on node 1 (default targets).
     1>D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln.metaproj : error MSB4126: The specified solution configuration "Release|Win32" is invalid. Please specify a valid solution configuration using the Configuration and Platform properties (e.g. MSBuild.exe Solution.sln /p:Configuration=Debug /p:Platform="Any CPU") or leave those properties blank to use the default solution configuration. [D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln]
     1>Done Building Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" (default targets) -- FAILED.

Build FAILED.

       "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" (default target) (1) ->
       (ValidateSolutionConfiguration target) -> 
         D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln.metaproj : error MSB4126: The specified solution configuration "Release|Win32" is invalid. Please specify a valid solution configuration using the Configuration and Platform properties (e.g. MSBuild.exe Solution.sln /p:Configuration=Debug /p:Platform="Any CPU") or leave those properties blank to use the default solution configuration. [D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln]

    0 Warning(s)
    1 Error(s)

Time Elapsed 00:00:00.04

```

### MSBuild Release Any CPU
- cwd: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
- exit: `1`
- skipped: ``
- command: `C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln /m /p:Configuration=Release /p:Platform=Any CPU`

stdout tail:
```text
MSBuild version 17.14.40+3e7442088 for .NET Framework
Build started 5/3/2026 6:15:20 AM.

     1>Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" on node 1 (default targets).
     1>ValidateSolutionConfiguration:
         Building solution configuration "Release|Any CPU".
     1>Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" (1) is building "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat\ClangFormat.csproj" (2) on node 1 (default targets).
     2>D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat\ClangFormat.csproj(249,11): error MSB4226: The imported project "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Microsoft\VisualStudio\v17.0\VSSDK\Microsoft.VsSDK.targets" was not found. Also, tried to find "VSSDK\Microsoft.VsSDK.targets" in the fallback search path(s) for $(VSToolsPath) - "C:\Program Files (x86)\MSBuild\Microsoft\VisualStudio\v17.0" . These search paths are defined in "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe.Config". Confirm that the path in the <Import> declaration is correct, and that the file exists on disk in one of the search paths.
     2>Done Building Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat\ClangFormat.csproj" (default targets) -- FAILED.
     1>Done Building Project "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" (default targets) -- FAILED.

Build FAILED.

       "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat.sln" (default target) (1) ->
       "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat\ClangFormat.csproj" (default target) (2) ->
         D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\tools\clang\tools\clang-format-vs\ClangFormat\ClangFormat.csproj(249,11): error MSB4226: The imported project "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Microsoft\VisualStudio\v17.0\VSSDK\Microsoft.VsSDK.targets" was not found. Also, tried to find "VSSDK\Microsoft.VsSDK.targets" in the fallback search path(s) for $(VSToolsPath) - "C:\Program Files (x86)\MSBuild\Microsoft\VisualStudio\v17.0" . These search paths are defined in "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe.Config". Confirm that the path in the <Import> declaration is correct, and that the file exists on disk in one of the search paths.

    0 Warning(s)
    1 Error(s)

Time Elapsed 00:00:00.12

```

### CMake configure clean source
- cwd: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
- exit: `1`
- skipped: ``
- command: `C:\Program Files\CMake\bin\cmake.EXE -S D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src -B D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\codered_llvm_build -A x64 -Thost=x64 -DLLVM_TARGETS_TO_BUILD=X86 -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DCMAKE_BUILD_TYPE=Release`

stdout tail:
```text
-- Configuring incomplete, errors occurred!

```

stderr tail:
```text
CMake Error at CMakeLists.txt:3 (cmake_minimum_required):
  Compatibility with CMake < 3.5 has been removed from CMake.

  Update the VERSION argument <min> value.  Or, use the <min>...<max> syntax
  to tell CMake that the project requires at least <min> but has been updated
  to work with policies introduced by <max> or earlier.

  Or, add -DCMAKE_POLICY_VERSION_MINIMUM=3.5 to try configuring anyway.



```


## Warnings

- Generated/example solutions were skipped. The previous LLVM.sln failure was stale and should not be retried as-is.
- SC-CL.exe was not produced. A full LLVM source root or a prebuilt SC-CL.exe is still needed.

## Next Steps

- Check whether SC-CL-master contains llvm-14.0.0.src. If it does not, this is probably a partial/tool-only source tree.
- If you have a full SC-CL source archive, extract it so llvm-14.0.0.src is inside SC-CL-master.
- If you only have the partial source, obtain a prebuilt SC-CL.exe matching the GTAResources/SC-CL RDR-capable family.
- After SC-CL.exe exists, run: py -3 tools\codered_sccl_easy_setup.py adopt --sccl resources\SC-CL_DROP_HERE\SC-CL.exe --run-validator
