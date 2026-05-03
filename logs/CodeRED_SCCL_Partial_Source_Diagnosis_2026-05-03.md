# Code RED SC-CL Partial Source Diagnosis

Date: 2026-05-03

## User-side proof

The local SC-CL source folder was checked with:

```bat
py -3 tools\codered_sccl_build_from_source.py --source "D:\Games\Red Dead Redemption\Code_RED\SC-CL-master" --adopt
```

## Result

The source folder is RDR-capable by markers:

```text
Red Dead Redemption
RDR_SCO
RDR_#SC
XSC format
CSC format
SCO format
```

But `SC-CL.exe` was not produced.

## Important finding

The existing `LLVM.sln` should not be retried as-is. It is stale/generated and points at an old missing Code RED output path:

```text
...code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src
```

The root `CMakeLists.txt` is also not a complete standalone top-level build root. It uses LLVM/Clang macros such as `add_clang_executable`, which require a full LLVM/Clang source tree context.

## Meaning

The local `SC-CL-master` appears to be a correct RDR-capable SC-CL family source, but likely a partial/tool-only source tree unless it contains:

```text
SC-CL-master\llvm-14.0.0.src\CMakeLists.txt
```

## Next valid routes

1. Extract a full SC-CL source archive that includes `llvm-14.0.0.src` inside `SC-CL-master`.
2. Obtain a prebuilt `SC-CL.exe` from the same GTAResources/SC-CL RDR-capable family.
3. Put the executable here:

```text
resources\SC-CL_DROP_HERE\SC-CL.exe
```

4. Then run:

```bat
py -3 tools\codered_sccl_easy_setup.py adopt --sccl resources\SC-CL_DROP_HERE\SC-CL.exe --run-validator
```

## Do not do

- Do not retry the stale `LLVM.sln` as-is.
- Do not invent a standalone root `CMakeLists.txt` for the partial tool folder.
- Do not claim compiled `.wsc/.xsc/.sco` roundtrip until `SC-CL.exe` exists and compiled output verification passes.
