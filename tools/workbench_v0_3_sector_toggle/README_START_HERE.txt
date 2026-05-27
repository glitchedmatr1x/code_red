Code RED Mod Workbench v0.3 - Easy Start
=========================================

Use this for safe, repeatable Red Dead Redemption PC modding passes.

Start:
  1. Extract this folder.
  2. Double-click CodeRED_Workbench_Start.bat.
  3. Choose a menu option.

Main output folders:
  reports\   scan reports and CSV inventories
  patched\   patched copies to import with Magic RDR/RPF tools

New in v0.3:
  - Sector scan for WSC/RSC85 update threads.
  - Sector patch/toggle mode.
  - Finds sector entries like:
      ENABLE_WORLD_SECTOR("dlc05x")
      DISABLE_CHILD_SECTOR("esc_villaWall04x")
  - Can safely toggle:
      enabled <-> disabled
      child <-> world
      sector name replacement if the new name fits the old slot

Safe examples:
  Enable esc_villaWall04x:
    sector-patch medium_update_thread.wsc --sector esc_villaWall04x --set-state enabled --all

  Replace beh_grave01x with dlc02x as an enabled world sector:
    sector-patch medium_update_thread.wsc --sector beh_grave01x --replace-with dlc02x --set-type world --set-state enabled --all

Important WSC rule:
  This is not a WSC compiler.
  It does not add new functions or rewrite unknown branches/natives.
  It patches same-byte markers and same-slot strings, then repacks/reopens/validates.

Do not import directly over your only copy. Always back up the RPF first.
