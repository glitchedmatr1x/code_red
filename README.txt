Code RED Make Ready Event Modded Files v1

This creates the three current event-test WSC files in:

  ready_modded_files\
    beat_crime_wagonthief.wsc
    event_roadside_ambush.wsc
    event_roadside_prisoners.wsc

Why this is a builder instead of prebuilt files:
- RDR1 WSC scripts are encrypted RSC85 resources.
- The patcher must use the AES key from your local rdr.exe to decode and repack them safely.
- Put clean/original files in .\imports first, or leave them in this folder if you are sure they are clean.

Run:
  install_ready_event_mod_deps.bat
  Run_CodeRED_Make_Ready_Event_Modded_Files.bat

It will try to auto-find rdr.exe at:
  ..\rdr.exe
  .\rdr.exe
  %RDR_GAME_DIR%

You can also set it manually:
  $env:CODERED_RDR_EXE="%RDR_GAME_DIR%"

Import one generated WSC at a time into content.rpf under the same filename.
Do not include short_update_thread.wsc in this event-spawn test pass.
