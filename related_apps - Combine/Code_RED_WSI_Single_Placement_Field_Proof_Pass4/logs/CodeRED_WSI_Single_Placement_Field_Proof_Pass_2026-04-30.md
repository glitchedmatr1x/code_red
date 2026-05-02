# Code RED — WSI Single-Placement Field Proof Pass

Date: 2026-04-30

## Purpose

Pass 3 resolved the best Blackwater candidate into an actual `drawable_instance_0xE0` placement record:

```text
i_gen_wagonBroken02x
record offset: 0x0011C7E0
record stride: 0xE0 / 224
name pointer relative field: +0xB8
```

This pass proves the exact record fields before any mutating vehicle experiment.

## Tool added

```text
tools/codered_wsi_single_placement_field_proof.py
```

The tool reads a decoded WSI payload and exports:

```text
single_placement_field_proof.json
single_placement_record.csv
record_bytes.hex.txt
single_placement_summary.txt
```

## Actual Blackwater proof result

Input:

```text
blackwater_type134/0224_0x19839F99.wsi.decoded
```

Target:

```text
record_offset: 0x0011C7E0
expected_host: i_gen_wagonBroken02x
```

Validation:

```text
expected_host_matched: true
record_vft_hex: 0x01913300
record_name: i_gen_wagonBroken02x
record_name_ptr_hex: 0x5022891B
record_name_offset_hex: 0x0022891B
record_sha1: 1bb6fdf8f9a60738085cce949988aea124e574c5
validation_passed: true
```

Transform proof:

```text
matrix_row0: [0.239398, -0.253135, -0.937343, nan]
matrix_row1: [0.109574, 0.966292, -0.232967, nan]
matrix_row2: [0.964719, -0.046936, 0.259066, nan]
position:    [723.793213, 79.2099, 1419.701904]
```

Bounding proof:

```text
bbox_min: [719.840637, 79.106247, 1418.24707, 3.450572]
bbox_max: [724.79303, 81.841583, 1422.198975, 1.367668]
```

## Conservative scope decision

This pass intentionally does not mutate WSI/WGD/WVD/WBD and does not ship a changed RPF.

Reason:

```text
The candidate field is now proven, but the exact first mutating field is not selected yet.
The safest next step is to choose whether the first experiment changes a host pointer, host string, hash lane, or a nearby gringo binding/annotation.
```

During local investigation, encrypted TOC rewrite automation was not included in this package because it is higher risk than this field proof and should be its own pass with a tiny synthetic archive test plus copied-RPF verification.

## Next pass recommendation

Pass 5 should be:

```text
WSI Single-Record Mutation Harness
```

It should support only one changed field at a time and require:

```text
- source archive copy only
- old bytes export
- new bytes export
- decoded payload reopen verification
- archive reopen verification
- proof JSON
- rollback notes
```

First safe mutation candidates to compare:

```text
1. name pointer field at +0xB8
2. instance hash field at +0xA0
3. drawable flags/state lane at +0xB0
4. nearby host/gringo annotation pointer if resolver finds the adjacent annotation owner
```

Do not test `Vehicle_Generator` directly until the mutation harness proves one harmless same-kind replacement first.
