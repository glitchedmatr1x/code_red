Code RED — WSI ↔ WGD Gringo Correlator Pass 2

Copy these files into the Code_RED repository root:

  tools/codered_wsi_gringo_correlator.py
  logs/CodeRED_Map_Layer_Correlator_Pass_2026-04-29.md
  logs/CodeRED_WSI_Gringo_Correlator_Pass_2026-04-30.md
  logs/CodeRED_WSI_Gringo_Correlator_Blackwater_Run_2026-04-30.md

Purpose:
  Read-only research/export tool to correlate WSI references with WGD gringo components before any vehicle-generator patching is attempted.

Fixes in this pass:
  - Ignores null/noisy hash values 0x00000000 and 0xFFFFFFFF.
  - Adds --max-hash-match-rows safety cap.
  - Adds WSI annotation host exports:
      wsi_gringo_annotation_hosts.csv
      wsi_annotation_candidate_hosts.csv

Example workflow:

  python tools/codered_gringo_wgd_export.py commongringos.wgd.decoded blackwater.wgd.decoded --outdir exports/gringo_wgd_export

  python tools/codered_wsi_gringo_correlator.py ^
    --wsi-archive blackwater.rpf ^
    --wgd-components exports/gringo_wgd_export/all_components.csv ^
    --outdir exports/wsi_gringo_correlation

If the WSI archive has unresolved debug names or you already decoded WSI manually, use:

  python tools/codered_wsi_gringo_correlator.py ^
    --wsi-decoded blackwater.wsi.decoded ^
    --wgd-components exports/gringo_wgd_export/all_components.csv ^
    --outdir exports/wsi_gringo_correlation

Key outputs:
  exports/wsi_gringo_correlation/wsi_sector_context.csv
  exports/wsi_gringo_correlation/wsi_keyword_string_hits.csv
  exports/wsi_gringo_correlation/wsi_hash_matches_to_wgd.csv
  exports/wsi_gringo_correlation/wgd_keyword_components.csv
  exports/wsi_gringo_correlation/wsi_wgd_correlations.csv
  exports/wsi_gringo_correlation/wsi_gringo_annotation_hosts.csv
  exports/wsi_gringo_correlation/wsi_annotation_candidate_hosts.csv
  exports/wsi_gringo_correlation/safe_candidate_gringo_hosts.csv
  exports/wsi_gringo_correlation/wsi_gringo_correlation_master.json

Blackwater result:
  No direct WSI -> Vehicle_Generator WGD match was proven by this pass.
  The useful result is the annotation host list, especially carts, parked wagons, wagon parts, hitching posts, and existing gringo-bearing prop hosts.

Next pass:
  Build the WSI Host Placement Resolver to turn host strings/hashes into actual WSI placement/transform records.

Rule:
  This pass does not patch anything. Patch only copied RPFs after a safe host and exact placement record are proven.
