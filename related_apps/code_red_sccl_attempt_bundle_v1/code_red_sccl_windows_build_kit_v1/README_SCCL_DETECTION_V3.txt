Code RED SC-CL Windows Build Kit V3
===================================

Purpose
-------
This folder is the Windows proof lane for the Code RED Script Workshop and Script Compile Lab.

It does not install scripts into the game. It validates that the source-first vehicle-menu probe can be staged for compile and, when SC-CL.exe is available, compiled in a controlled proof folder.

Required commands
-----------------
1. From the Code RED root:

   py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py self-test

2. Generate/refresh the compile proof plan:

   py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py compile-proof-plan

3. Validate the source and build kit:

   py -3 tools\codered_script_compile_validation.py

4. Run the Windows build/compile helper:

   related_apps\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\run_build_then_compile_vehicle_menu_probe.bat

SC-CL detection
---------------
The helper looks for SC-CL.exe in these places:

- environment variable SCCL_EXE
- Code RED root
- this build kit folder
- script compile lab folder
- resources\SC-CL-master\bin
- resources\SC-CL-master\llvm-14.0.0.src\MinSizeRel\bin

If SC-CL.exe is not found, the helper still writes proof logs and reports the missing compiler instead of guessing.

Safety
------
Compiled binary .wsc/.xsc/.sco roundtrip is still proof-gated. This kit only proves source staging and compile invocation readiness.
