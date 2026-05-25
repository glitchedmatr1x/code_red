# MP Bootstrap Pass 2 Test Steps

1. Back up the current test content.rpf.
2. Import the drop-in folder with Magic RDR, preserving paths:
   - `content/release64/scripting/designerdefined/long_update_thread.wsc`
   - `content/release64/scripting/designerdefined/codered_mp_bootstrap_minimal.wsc`
3. Reopen the RPF after import.
4. Export both imported WSC files back out.
5. Compare exported bytes against the drop-in files before launching.
6. Launch the game with the Pass 5/6 XML route active.
7. Enter the MP/Free Roam route and watch for a change from menu-only behavior to backend script activity.
8. If nothing changes, the next pass should patch a more frequently executed launch slot or add a real launch block once WSC growth/rebuild is proven.
