# Code RED WSC Binary Edit Workspace

- Name: `binary_long_update_thread`
- Source RPF: `D:\Games\Red Dead Redemption\game\content.rpf`
- Archive path: `root/content/release64/scripting/designerdefined/long_update_thread.wsc`
- Original WSC: `D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\binary_long_update_thread\original\content\release64\scripting\designerdefined\long_update_thread.wsc`
- Edited WSC: `D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\binary_long_update_thread\edited\long_update_thread.wsc`

This workspace edits a copy of the original WSC. It does not generate `src/main.c` and does not replace the script with a blank source-built payload.

Useful commands:

```bat
python tools\codered_wsc_edit_workflow.py strings --workspace "D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\binary_long_update_thread"
python tools\codered_wsc_edit_workflow.py replace-string --workspace "D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\binary_long_update_thread" --find OLD --replace NEW
python tools\codered_wsc_edit_workflow.py patch-bytes --workspace "D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\binary_long_update_thread" --offset 0x20 --expected-hex AA --hex BB
python tools\codered_wsc_edit_workflow.py pack --workspace "D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\binary_long_update_thread" --write
```

Expanded string replacement is refused unless a future container rebuilder is implemented.
