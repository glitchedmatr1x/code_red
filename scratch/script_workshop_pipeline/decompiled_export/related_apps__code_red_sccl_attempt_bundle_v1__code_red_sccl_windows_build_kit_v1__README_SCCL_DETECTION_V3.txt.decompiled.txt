# Code RED Decompiled Source Export
# Source: related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/README_SCCL_DETECTION_V3.txt
# SHA1: 7393ee3c6ebf3397bd37329f5c616edc10dfe523
# Export type: source/text copy

Code RED vehicle menu probe compile fix v3

This version removes the brittle "put the zip next to the extracted folder" rule.

Easiest options:

OPTION A - simplest:
1. Open this folder:
   Code_RED\data\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1
2. Put SC-CL-master.zip directly in this same folder.
3. Open x64 Native Tools Command Prompt for VS 2022.
4. Run:
   run_build_then_compile_vehicle_menu_probe.bat

OPTION B - explicit path, no moving files:
1. Open x64 Native Tools Command Prompt for VS 2022.
2. cd into this folder:
   Code_RED\data\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1
3. Run:
   run_build_then_compile_vehicle_menu_probe.bat "C:\full\path\to\SC-CL-master.zip"

OPTION C - extracted SC-CL folder:
1. Extract SC-CL-master.zip anywhere.
2. Run:
   run_build_then_compile_vehicle_menu_probe.bat "C:\full\path\to\SC-CL-master"

OPTION D - already-built compiler:
1. If you already have SC-CL.exe, run:
   set SCCL_EXE=C:\full\path\to\SC-CL.exe
   compile_vehicle_menu_probe_windows.bat

The v3 detector searches:
- the build kit folder
- the SC-CL bundle folder
- Code_RED/data
- Code_RED
- the extracted package root
- the current command prompt folder
- Desktop and Downloads

Logs:
- output\build_sccl_windows.log
- output\compile_vehicle_menu_probe.log

Goal remains:
1. Build/detect SC-CL.exe.
2. Compile src\main.c.
3. Produce the vehicle menu probe output in output\vehicle_menu_probe_build.
