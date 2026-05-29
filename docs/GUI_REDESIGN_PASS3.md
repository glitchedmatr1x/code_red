# Code RED GUI Redesign Pass 3

This pass replaces the public app front door with a focused Script Lab + RPF Browser workflow.

## Goals

- Remove the old button-wall launcher experience.
- Make WSC/XSC/CSC/SCO viewing and safe same-size edits the primary workflow.
- Make RPF/ZIP handling easy to inspect while keeping archive operations read-only in the GUI.
- Export a compact GPT Packet JSON so users and AI agents can continue a session without guessing.
- Keep the public repo clean: no raw game files, no extracted retail scripts, no private logs, and no compiled binaries.

## Main UI

Top-level actions are intentionally limited:

1. Open Script
2. Open RPF/ZIP
3. Open Folder
4. Inspect
5. Save Patch Copy
6. Export GPT Packet

The tabs are:

- Script Lab
- RPF Browser
- Recipe
- GPT Packet
- Log

## Script Lab

Script Lab can load `.wsc`, `.xsc`, `.csc`, and `.sco` files supplied by the user. If the Code RED WSC decoder has a valid key source, the decoded payload is shown. Otherwise, the app falls back to raw byte preview and string extraction.

Supported safe edit lane in this pass:

- same-length ASCII string replacement
- output is written to a user-selected patched copy
- original file is not overwritten
- decoded RSC85 repack is attempted only when the script successfully decoded

## RPF Browser

RPF Browser is read-only. It can inventory likely member names from RPF archives and fully list ZIP package members. It does not write back to RPF archives.

For actual RPF patch building, users should continue using copy-first tools such as `CodeRED_RPF_Patcher_Lite.py` or Code Red Syringe workflows.

## GPT Packet

The GPT Packet tab creates a concise JSON summary of loaded script/archive/workspace state. It is designed so users can paste it into GPT without uploading raw game files.

## Legacy Workbench

The previous large workbench implementation was preserved as:

```text
python_workbench_legacy_button_sprawl.py
```

It is not the default launcher anymore.
