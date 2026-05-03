Code RED WFT/RSC5 Edit Bridge - Pass 9 Menu Fix
=================================================

Purpose
-------
Pass 8 worked as a command-line tool, but double-clicking it could make the console open and close immediately. Pass 9 fixes that by adding a persistent menu launcher and logging.

Start here
----------
Double-click:

  RUN_WFT_TOOL_MENU.bat

The menu stays open and writes error details to:

  logs\wft_tool_last_run.log

What this tool can do
---------------------
- Scan an RPF for .wft files.
- Export one WFT from an RPF.
- Unpack a standalone WFT into:
  - original .wft
  - .rsc5_header.bin
  - .rsc5_payload.bin
  - .rsc5_meta.json
- Repack a same-size edited payload into a standalone WFT.
- Patch a copied RPF from an edited payload.
- Patch a copied RPF from a replacement standalone WFT.
- Run a sample self-test.

Drag/drop helper
----------------
You can drag a .wft file onto:

  DRAG_DROP_UNPACK_WFT.bat

It will unpack the WFT into the exports folder.

Important limits
----------------
This is still an edit bridge, not a full mesh editor.

It does not yet decode:
- vertices
- bones
- hierarchy
- materials
- collisions
- WFT model sections into GUI fields

Safe rule:
- same-size decompressed payload edits only by default
- copied RPF patching only
- no production archive is edited in place
- no WSC/gringo/script edits

External requirement
--------------------
The tool needs the zstd command-line utility available as zstd or zstd.exe.
If the menu says zstd available: False, install zstd or place zstd.exe somewhere in PATH / next to the tool.

Recommended workflow
--------------------
1. Run RUN_WFT_TOOL_MENU.bat.
2. Choose 1 to scan an RPF for WFT entries.
3. Choose 2 to export one WFT from the RPF.
4. Use external model/resource research tools for the payload while preserving size.
5. Choose 4 or 5 to repack/patch.
6. Read the generated JSON report before testing in game.

For GTA IV / ZModeler style editing
-----------------------------------
Use this bridge as the Code RED RSC5/RPF side of the workflow. If an external editor produces a standalone replacement WFT, use menu option 6 to patch a copied RPF with that replacement WFT.

Do not patch original production archives until a copied-archive test reopens and validates.
