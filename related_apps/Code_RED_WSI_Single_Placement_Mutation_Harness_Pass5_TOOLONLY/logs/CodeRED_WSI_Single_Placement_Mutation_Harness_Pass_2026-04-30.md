# Code RED — WSI Single-Placement Mutation Harness Pass

Date: 2026-04-30

## Purpose

This pass turns the proven Blackwater placement record into a controlled copied-RPF experiment harness.

The previous field proof identified a specific drawable placement:

```text
Host: i_gen_wagonBroken02x
Decoded WSI record offset: 0x0011C7E0
Record type/VFT: 0x01913300
Record stride: 0xE0 / 224
Name pointer field: +0xB8
Position/matrix row3 field: +0x70
Position before: [723.793213, 79.2099, 1419.701904]
```

## What this pass adds

```text
tools/codered_wsi_single_placement_mutation_harness.py
```

The tool:

- refuses in-place edits
- copies the source RPF first
- validates the expected host name and drawable VFT before patching
- supports a no-op archive rewrite/reopen proof
- supports one visual-only `nudge-position` mutation
- appends the rebuilt RSC resource and updates the RPF TOC
- reopens the copied archive and validates the decoded payload after patching
- writes proof JSON with old/new record bytes, old/new position, archive SHA1s, and rollback notes

## Actual Blackwater runs completed

### No-op proof

```text
Mode: noop
Validation: passed
Host preserved: yes
Decoded payload matched after reopen: yes
Record SHA1 matched after reopen: yes
Original archive modified: no
```

### First visual-only experiment

```text
Mode: nudge-position
Target host: i_gen_wagonBroken02x
Position before: [723.793213, 79.2099, 1419.701904]
Position after:  [723.793213, 79.2099, 1419.951904]
Delta: Z +0.25
Validation: passed
Original archive modified: no
```

The included experimental RPF is only a tiny Z-position nudge on one copied Blackwater placement. This is intended as a field-coordinate proof, not the Vehicle_Generator experiment yet.

## Why this matters

If this nudge visibly moves or slightly lifts the broken wagon in-game, then the WSI placement transform lane is confirmed. After that, the next pass can safely test a larger visible nudge or host-binding experiment with a known rollback path.

## Next pass after user test

If the nudge is visible in-game:

1. Do a stronger position nudge or swap one non-critical wagon/cart host to another compatible existing wagon/cart host.
2. Only after visual patching is confirmed, attempt a one-record gringo/vehicle host binding experiment.

If the nudge is not visible:

1. Re-check whether this WSI layer is shadowed by another loaded Blackwater archive.
2. Search for the same host in adjacent WSI/RPF layers.
3. Verify sector streaming/LOD and whether the object is culled or replaced by another content layer.

## Safety rule

Do not bulk patch WSI/WGD/WVD/WBD. Continue one copied archive, one placement, one proof JSON at a time.
