Code RED — WSI Single-Placement Mutation Harness Pass 5

This tool-only package contains the harness, logs, and proof JSON.
The experimental copied RPF is provided as a separate download:
  blackwater_nudge_z025_single_placement_test.rpf

What this does:
A controlled experimentation pass for the proven Blackwater placement:
  i_gen_wagonBroken02x at decoded WSI offset 0x0011C7E0

Included files:
  tools/codered_wsi_single_placement_mutation_harness.py
  logs/CodeRED_WSI_Single_Placement_Mutation_Harness_Pass_2026-04-30.md
  reports/blackwater_single_placement_mutation_outputs/*.json
  reports/VALIDATION.txt
  reports/PASS5_SUMMARY.json

Experimental RPF details:
The separate RPF download is a copied Blackwater RPF with only one tiny visual nudge:
  Z position +0.25 on i_gen_wagonBroken02x

Do not overwrite your original archive. Keep a backup.

Install into the repo:
  Copy tools/codered_wsi_single_placement_mutation_harness.py into Code_RED/tools/
  Copy logs/*.md into Code_RED/logs/

Run a no-op proof yourself:
  python tools/codered_wsi_single_placement_mutation_harness.py blackwater.rpf --no-debug --out blackwater_noop_test.rpf --mode noop

Run the same tiny nudge experiment yourself:
  python tools/codered_wsi_single_placement_mutation_harness.py blackwater.rpf --no-debug --out blackwater_nudge_z025_test.rpf --mode nudge-position --dz 0.25

Expected test:
Load the experimental copied RPF in the same place the normal Blackwater RPF is loaded from. Look for the broken wagon/cart host near the Blackwater coordinates. If it visually moves or lifts slightly, the WSI placement transform lane is confirmed.

Next after this:
If visible, the next pass can try a stronger nudge or one compatible host swap. Vehicle_Generator binding should wait until the placement lane is confirmed in-game.
