Code RED - WSI Single-Placement Field Proof Pass 4

Install:
1. Copy tools/codered_wsi_single_placement_field_proof.py into your Code_RED/tools folder.
2. Keep the reports/logs with your pass notes.

Example run on the decoded Blackwater WSI:

python tools/codered_wsi_single_placement_field_proof.py ^
  exports/blackwater_type134/0224_0x19839F99.wsi.decoded ^
  --record-offset 0x0011C7E0 ^
  --expected-host i_gen_wagonBroken02x ^
  --outdir exports/wsi_single_placement_field_proof

This pass is intentionally read-only. It proves the target placement field before any copied-RPF mutation pass.

Primary proven target:
- host: i_gen_wagonBroken02x
- decoded WSI record offset: 0x0011C7E0
- record type: drawable_instance_0xE0 / VFT 0x01913300
- name pointer relative field: +0xB8
- position: [723.793213, 79.2099, 1419.701904]

Next pass:
Build the one-record mutation harness. Do not bulk patch WSI/WGD/WVD/WBD.
