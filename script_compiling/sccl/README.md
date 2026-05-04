# Code RED SC-CL Lane

This is the active SC-CL compile lane.

Expected layout:

`	ext
script_compiling/sccl/
  output/SC-CL.exe                 optional local compiler location; not committed
  include/                         active headers
  projects/vehicle_menu_probe/     active proof source
  obsolete/                        preserved old compile attempts
`

Compile goal:

`at
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
`

If SC-CL.exe is somewhere else, set:

`at
set SCCL_EXE=C:\path\to\SC-CL.exe
`

Do not build the full Code RED menu through SC-CL until native signatures are verified one at a time.
