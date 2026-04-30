Code RED — WSI Host Placement Resolver Pass

Install:
1. Copy tools/codered_wsi_host_placement_resolver.py into the Code_RED repo tools/ folder.
2. Copy logs/CodeRED_WSI_Host_Placement_Resolver_Pass_2026-04-30.md into the repo logs/ folder.
3. Keep the reports folder as proof/reference output.

Run with decoded Blackwater WSI:

python tools/codered_wsi_host_placement_resolver.py ^
  --wsi-decoded exports/blackwater_type134/0224_0x19839F99.wsi.decoded ^
  --default-priority-hosts ^
  --outdir exports/wsi_host_placement_resolver

Run from an archive, if codered_wsi_explorer.py is beside this tool:

python tools/codered_wsi_host_placement_resolver.py ^
  --wsi-archive blackwater.rpf ^
  --default-priority-hosts ^
  --outdir exports/wsi_host_placement_resolver

Important:
- This pass is read-only.
- Do not patch original RPF files.
- Do not bulk patch WSI, WGD, WVD, or WBD.
- Use copied archives only after exact field layout proof.

Best current candidate from the included Blackwater run:
- Host: i_gen_wagonBroken02x
- Record kind: drawable_instance_0xE0
- Record offset: 0x0011C7E0
- Position: [723.793213, 79.2099, 1419.701904]
