Code RED UI Settings Menu Patch v1
==================================

Purpose
-------
This patch tests the idea of reusing an existing game menu instead of injecting a script menu.
It recycles the offline LAN row in the pause/networking menu into a harmless Settings-style Code RED proof dialog.

What to test
------------
1. Back up your original game content.rpf first.
2. Copy patched_content/content.rpf over the game/content.rpf you are testing.
3. Launch the game.
4. Enter the pause menu and open the multiplayer/networking area where the offline LAN/private/public rows normally appear.
5. Look for a row that appears as Settings, or the former LAN row if the string does not update.
6. Press Accept on that row.
7. Expected result: a simple Settings/blank dialog opens and can be closed with OK or Back.

Expected first proof
--------------------
- The recycled row appears in the normal pause/networking menu.
- Pressing Accept opens CodeRed_SettingsBox.
- OK/Back exits cleanly.
- The game does not lock up.

Important
---------
This patch does not spawn vehicles yet and does not change tune values yet.
It is only the first proof that we can turn a redundant built-in menu row into our own menu lane.

If it fails
-----------
Restore your original content.rpf.
If the game boots but nothing changes, the target menu may be hidden by platform/sign-in conditions; the next target should be the start-screen Settings prompt or the boot preset dialog.
If the game crashes on boot, restore content.rpf and use the loose_patch_root files with a proper RPF editor instead of the prebuilt relocated archive.

Loose files
-----------
loose_patch_root contains the two edited XML files in their internal archive paths. These are included so you can import/replace them with Code RED/MagicRDR instead of using the prebuilt patched archive.
