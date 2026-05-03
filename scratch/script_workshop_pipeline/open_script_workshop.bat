@echo off
setlocal
echo Opening Code RED Script Workshop folders...
if exist edit_workspace start "CodeRED Script Edit Workspace" edit_workspace
if exist decompiled_export start "CodeRED Decompiled Export" decompiled_export
if exist import_queue start "CodeRED Import Queue" import_queue
if exist SCRIPT_PIPELINE_GUIDE.md start "" SCRIPT_PIPELINE_GUIDE.md
endlocal
