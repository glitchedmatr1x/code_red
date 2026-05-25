# Code RED MP Freeroam Pass 3 Test Steps

1. Back up the current game `content.rpf`.
2. Import the package at:
   `D:\Games\Red Dead Redemption\Code_RED\build\mp_freeroam_pass3\dropin_import_ready`
3. Reopen the target RPF in Magic RDR before launching.
4. Export and byte-compare spot checks:
   - `root/content/release64/scripting/designerdefined/long_update_thread.wsc`
   - `root/content/release64/scripting/designerdefined/codered_mp_bootstrap_minimal.wsc`
   - `root/content/ui/pausemenu/pausemenuscene.sc.xml`
   - `root/content/ui/pausemenu/networking.sc.xml`
   - `root/content/ui/pausemenu/net/lanmenu.sc.xml`
   - one restored `freemode`/`pr_multiplayer` MP script from `release64/multiplayer`
5. Launch the game.
6. Open the pause/menu route and select the Code RED Free Roam / LAN / MP option.
7. Record whether:
   - backend scripts start,
   - loading starts,
   - Free Roam world state appears,
   - crash/hang behavior changes,
   - missing script/resource behavior changes.
8. Interpret first failure:
   - no change: normal thread hook did not fire,
   - crash on script start: bootstrap fired but MP backend script format/path/resource is wrong,
   - loading begins then hangs: backend partially starts and next blocker is session/game state,
   - world loads: keep iterating from this build.
9. Restore the original `content.rpf` after testing if needed.
