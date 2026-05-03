# Code RED SC-CL Build From Source Report

Generated UTC: `2026-05-03T12:34:16Z`
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
- CMakeLists.txt: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\CMakeLists.txt`
- CMake source used: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src`
- Solutions:
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\LLVM.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\MenuBase\MenuBase.sln`
  - `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\testing\test.sln`

## Skipped Solutions

- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\LLVM.sln` — stale generated LLVM.sln/ZERO_CHECK points at an old Code RED output path
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\MenuBase\MenuBase.sln` — example/test solution, not SC-CL.exe
- `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\bin\projects\testing\test.sln` — example/test solution, not SC-CL.exe

## CMake Source Diagnostics

- D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\CMakeLists.txt: appears to be a top-level CMake source root

## Attempts

### CMake configure clean source
- cwd: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master`
- exit: `1`
- skipped: ``
- command: `C:\Program Files\CMake\bin\cmake.EXE -S D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src -B D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\codered_llvm_build -A x64 -Thost=x64 -DLLVM_TARGETS_TO_BUILD=X86 -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DCMAKE_BUILD_TYPE=Release`

stdout tail:
```text
r unistd.h - not found
-- Looking for valgrind/valgrind.h
-- Looking for valgrind/valgrind.h - not found
-- Looking for fenv.h
-- Looking for fenv.h - found
-- Looking for FE_ALL_EXCEPT
-- Looking for FE_ALL_EXCEPT - found
-- Looking for FE_INEXACT
-- Looking for FE_INEXACT - found
-- Looking for mach/mach.h
-- Looking for mach/mach.h - not found
-- Looking for histedit.h
-- Looking for histedit.h - not found
-- Looking for CrashReporterClient.h
-- Looking for CrashReporterClient.h - not found
-- Looking for pfm_initialize in pfm
-- Looking for pfm_initialize in pfm - not found
-- Could NOT find ZLIB (missing: ZLIB_LIBRARY ZLIB_INCLUDE_DIR) 
-- Could NOT find LibXml2 (missing: LIBXML2_LIBRARY LIBXML2_INCLUDE_DIR) 
-- Looking for xar_open in xar
-- Looking for xar_open in xar - not found
-- Looking for arc4random
-- Looking for arc4random - not found
-- Looking for backtrace
-- Looking for backtrace - not found
-- Could NOT find Backtrace (missing: Backtrace_LIBRARY Backtrace_INCLUDE_DIR) 
-- Performing Test C_SUPPORTS_WERROR_UNGUARDED_AVAILABILITY_NEW
-- Performing Test C_SUPPORTS_WERROR_UNGUARDED_AVAILABILITY_NEW - Failed
-- Looking for __register_frame
-- Looking for __register_frame - not found
-- Looking for __deregister_frame
-- Looking for __deregister_frame - not found
-- Looking for __unw_add_dynamic_fde
-- Looking for __unw_add_dynamic_fde - not found
-- Looking for _Unwind_Backtrace
-- Looking for _Unwind_Backtrace - not found
-- Looking for getpagesize
-- Looking for getpagesize - not found
-- Looking for sysconf
-- Looking for sysconf - not found
-- Looking for getrusage
-- Looking for getrusage - not found
-- Looking for setrlimit
-- Looking for setrlimit - not found
-- Looking for isatty
-- Looking for isatty - not found
-- Looking for futimens
-- Looking for futimens - not found
-- Looking for futimes
-- Looking for futimes - not found
-- Looking for sigaltstack
-- Looking for sigaltstack - not found
-- Looking for lseek64
-- Looking for lseek64 - not found
-- Looking for mallctl
-- Looking for mallctl - not found
-- Looking for mallinfo
-- Looking for mallinfo - not found
-- Looking for mallinfo2
-- Looking for mallinfo2 - not found
-- Looking for malloc_zone_statistics
-- Looking for malloc_zone_statistics - not found
-- Looking for getrlimit
-- Looking for getrlimit - not found
-- Looking for posix_spawn
-- Looking for posix_spawn - not found
-- Looking for pread
-- Looking for pread - not found
-- Looking for sbrk
-- Looking for sbrk - not found
-- Looking for strerror
-- Looking for strerror - found
-- Looking for strerror_r
-- Looking for strerror_r - not found
-- Looking for strerror_s
-- Looking for strerror_s - found
-- Looking for setenv
-- Looking for setenv - not found
-- Looking for _chsize_s
-- Looking for _chsize_s - found
-- Looking for _alloca
-- Looking for _alloca - not found
-- Looking for __alloca
-- Looking for __alloca - not found
-- Looking for __chkstk
-- Looking for __chkstk - found
-- Looking for __chkstk_ms
-- Looking for __chkstk_ms - not found
-- Looking for ___chkstk
-- Looking for ___chkstk - not found
-- Looking for ___chkstk_ms
-- Looking for ___chkstk_ms - not found
-- Looking for __ashldi3
-- Looking for __ashldi3 - not found
-- Looking for __ashrdi3
-- Looking for __ashrdi3 - not found
-- Looking for __divdi3
-- Looking for __divdi3 - not found
-- Looking for __fixdfdi
-- Looking for __fixdfdi - not found
-- Looking for __fixsfdi
-- Looking for __fixsfdi - not found
-- Looking for __floatdidf
-- Looking for __floatdidf - not found
-- Looking for __lshrdi3
-- Looking for __lshrdi3 - not found
-- Looking for __moddi3
-- Looking for __moddi3 - not found
-- Looking for __udivdi3
-- Looking for __udivdi3 - not found
-- Looking for __umoddi3
-- Looking for __umoddi3 - not found
-- Looking for __main
-- Looking for __main - not found
-- Looking for __cmpdi2
-- Looking for __cmpdi2 - not found
-- Performing Test HAVE_STRUCT_STAT_ST_MTIMESPEC_TV_NSEC
-- Performing Test HAVE_STRUCT_STAT_ST_MTIMESPEC_TV_NSEC - Failed
-- Performing Test HAVE_STRUCT_STAT_ST_MTIM_TV_NSEC
-- Performing Test HAVE_STRUCT_STAT_ST_MTIM_TV_NSEC - Failed
-- Looking for __GLIBC__
-- Looking for __GLIBC__ - not found
-- Looking for proc_pid_rusage
-- Looking for proc_pid_rusage - not found
-- Performing Test HAVE_STD_IS_TRIVIALLY_COPYABLE
-- Performing Test HAVE_STD_IS_TRIVIALLY_COPYABLE - Success
-- Performing Test LLVM_HAS_ATOMICS
-- Performing Test LLVM_HAS_ATOMICS - Success
-- Performing Test SUPPORTS_VARIADIC_MACROS_FLAG
-- Performing Test SUPPORTS_VARIADIC_MACROS_FLAG - Failed
-- Performing Test SUPPORTS_GNU_ZERO_VARIADIC_MACRO_ARGUMENTS_FLAG
-- Performing Test SUPPORTS_GNU_ZERO_VARIADIC_MACRO_ARGUMENTS_FLAG - Failed
-- Native target architecture is X86
-- Threads enabled.
-- Doxygen disabled.
-- Go bindings disabled.
-- Could NOT find OCaml (missing: OCAMLFIND OCAML_VERSION OCAML_STDLIB_PATH) 
-- OCaml bindings disabled.
-- Could NOT find Python module pygments
-- Could NOT find Python module pygments.lexers.c_cpp
-- Could NOT find Python module yaml
-- LLVM host triple: x86_64-pc-windows-msvc
-- LLVM default target triple: x86_64-pc-windows-msvc
-- Using Debug VC++ CRT: MDd
-- Using Release VC++ CRT: MD
-- Using MinSizeRel VC++ CRT: MD
-- Using RelWithDebInfo VC++ CRT: MD
-- Using Release VC++ CRT: MD
-- Looking for os_signpost_interval_begin
-- Looking for os_signpost_interval_begin - not found
-- Found Python3: C:/Users/glitc/AppData/Local/Programs/Python/Python312/python.exe (found suitable version "3.12.4", minimum required is "3.0") found components: Interpreter
-- Performing Test HAS_WERROR_GLOBAL_CTORS
-- Performing Test HAS_WERROR_GLOBAL_CTORS - Failed
-- Found Git: C:/Program Files/Git/cmd/git.exe (found version "2.52.0.windows.1")
-- LLVMHello ignored -- Loadable modules not supported on this platform.
-- Targeting X86
-- Looking for sys/resource.h
-- Looking for sys/resource.h - not found
-- Clang version: 14.0.0
-- Configuring incomplete, errors occurred!

```

stderr tail:
```text
CMake Deprecation Warning at CMakeLists.txt:8 (cmake_policy):
  The OLD behavior for policy CMP0116 will be removed from a future version
  of CMake.

  The cmake-policies(7) manual explains that the OLD behaviors of all
  policies are deprecated and that a policy should be set to OLD only under
  specific short-term circumstances.  Projects should be ported to the NEW
  behavior and not rely on setting a policy to OLD.


CMake Warning (dev) at C:/Program Files/CMake/share/cmake-4.3/Modules/CMakeDetermineASMCompiler.cmake:234 (message):
  Policy CMP194 is not set: MSVC is not an assembler for language ASM.  Run
  "cmake --help-policy CMP194" for policy details.  Use the cmake_policy
  command to set the policy and suppress this warning.
Call Stack (most recent call first):
  CMakeLists.txt:49 (project)
This warning is for project developers.  Use -Wno-dev to suppress it.

CMake Warning (dev) at tools/clang/CMakeLists.txt:309 (find_package):
  Policy CMP0146 is not set: The FindCUDA module is removed.  Run "cmake
  --help-policy CMP0146" for policy details.  Use the cmake_policy command to
  set the policy and suppress this warning.

This warning is for project developers.  Use -Wno-dev to suppress it.

CMake Warning (dev) at tools/clang/lib/Tooling/CMakeLists.txt:55 (add_custom_command):
  COMMENT requires exactly one argument, but multiple values or COMMENT
  keywords have been given.

  Policy CMP0175 is not set: add_custom_command() rejects invalid arguments.
  Run "cmake --help-policy CMP0175" for policy details.  Use the cmake_policy
  command to set the policy and suppress this warning.
This warning is for project developers.  Use -Wno-dev to suppress it.

CMake Warning (dev) at tools/clang/lib/Tooling/CMakeLists.txt:76 (add_custom_command):
  COMMENT requires exactly one argument, but multiple values or COMMENT
  keywords have been given.

  Policy CMP0175 is not set: add_custom_command() rejects invalid arguments.
  Run "cmake --help-policy CMP0175" for policy details.  Use the cmake_policy
  command to set the policy and suppress this warning.
This warning is for project developers.  Use -Wno-dev to suppress it.

CMake Error at tools/clang/tools/extra/SC-CL/CMakeLists.txt:1 (cmake_minimum_required):
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
