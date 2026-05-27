# Code RED SC-CL Build Helper Finalizer State

Date: 2026-05-03

## User-side report fragment

The latest `codered_sccl_build_from_source.py --adopt` report shows:

```text
RDR Readiness Markers:
- Red Dead Redemption
- RDR_SCO
- RDR_#SC
- XSC format
- CSC format
- SCO format

Build Systems:
- MSBuild present
- CMake present
- CMakeLists.txt: None
- CMake source used: None
- Solutions: none
- Attempts: none

Next Steps:
- Run: py -3 tools\codered_sccl_finalize_build.py --validate --compile-helper
```

## Interpretation

This is no longer the earlier stale-solution/CMake-policy/in-source-artifact failure state.

When the helper reports no build attempts and points directly to the finalizer, the next proof step is to run the finalizer. The finalizer searches for an existing built/staged `SC-CL.exe`, adopts it into the Code RED Windows build kit, mirrors it to the drop folder, runs validation, and optionally runs the vehicle-menu compile probe.

## Next command

```bat
py -3 tools\codered_sccl_finalize_build.py --validate --compile-helper
```

## If finalizer cannot find SC-CL.exe

Run with an explicit executable path:

```bat
py -3 tools\codered_sccl_finalize_build.py --sccl "FULL_PATH_TO_SC-CL.exe" --validate --compile-helper
```

Or copy the executable to:

```text
resources\SC-CL_DROP_HERE\SC-CL.exe
```

then rerun the finalizer.
