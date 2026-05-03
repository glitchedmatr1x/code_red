# Code RED SC-CL Source Cleanup Report

Generated UTC: `2026-05-03T15:58:18Z`
Result: **NEEDS CLEANUP**
Source: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src`
Apply mode: `False`
Quarantine: `D:\Games\Red Dead Redemption\Code_RED\SC-CL-master\llvm-14.0.0.src\_codered_quarantine_in_source_build_artifacts`

## Suspicious Files

- `lib/Target/Hexagon/HexagonDepDecoders.inc`
- `include/llvm/Config/config.h`
- `include/llvm/Config/llvm-config.h`
- `include/llvm/Support/VCSRevision.h`
- `cmake_install.cmake`

## Suspicious Directories

- `none`

## Warnings

- Suspicious in-source build artifacts found. Re-run with --apply to quarantine them.

## Next Steps

- Use CMake 3.x if current CMake reports CMP0051 OLD behavior errors.
- Then run: py -3 tools\codered_sccl_build_from_source.py --source "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master" --adopt
