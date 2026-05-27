# Code RED GitHub SC-CL Sorter Committed — 2026-05-04

## Purpose

The local SC-CL lane sort zip was not downloading for the user, so a GitHub-resident sorter script was committed instead.

## Added

```text
tools/Apply_CodeRED_SCCL_Lane_Sort_From_Repo.ps1
```

## How to run from a local Code_RED checkout

```powershell
powershell -ExecutionPolicy Bypass -File tools\Apply_CodeRED_SCCL_Lane_Sort_From_Repo.ps1
```

## What it does

- Creates `script_compiling/sccl/` as the active SC-CL lane.
- Copies the existing compile lab headers/source/scripts into the active lane.
- Copies existing SC-CL Windows build/compile helper scripts into the active lane.
- Moves old compile-lane folders into `script_compiling/sccl/obsolete/` when they exist.
- Writes README files and a sort manifest.
- Does not delete proof/source material.

## Why this approach

The connected GitHub API could create repo files, but direct GitHub cloning was unavailable in the sandbox. A repo-side script is safer than trying to upload a large patch artifact or delete old folders blindly.

## Next local validation

```bat
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```

If `SC-CL.exe` is not under `script_compiling\sccl\output\SC-CL.exe`, set:

```bat
set SCCL_EXE=C:\path\to\SC-CL.exe
```
