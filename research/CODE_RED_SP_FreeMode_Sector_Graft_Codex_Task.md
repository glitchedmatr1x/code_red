# Code RED Codex Task — SP FreeMode Sector Graft Pass 1

## User correction / priority

Do **not** focus on activating full MP modes right now.

Main objective:

```text
Load what FreeMode/MP contains into single-player piece by piece.
Main focus: sectors.
```

The next useful pass is about:

```text
MP sectors into SP
SP sectors out / swapped where needed
sector loading order
safe WSC sector controller/probe
```

Not:

```text
net.EnterOnline
TriggerMultiplayerLoad
StartGameWish
direct freemode.wsc launch
multiplayer_update_thread launch
```

Those launch paths are not the next target.

---

## Why this matters

We can now fully inspect/edit many MP WSC files and the XSC->WSC conversion lane is MagicRDR-compatible. That means MP scripts can be mined for sector names, action areas, spawn volumes, blips, and support calls.

The strongest new path is:

```text
Use MP scripts as content/source references.
Move their world pieces into SP.
```

If we can safely edit/create WSC carriers, we can build our own SP-side “FreeMode content loader” instead of trying to enter the real network mode.

---

## Base to preserve

Use the best known stable baseline unless another later one is explicitly proven better:

```text
A_disable_update_thread_refs / content loading passed
SHA1: 91304EBA24B3759AE206783EBE4CA42EA0F2A134
```

This branch reaches loading and avoids direct `multiplayer_update_thread`.

Do not use Pass 10 patched freemode as a base. It crashed even when only present.

---

## Pass name

```text
SP FreeMode Sector Graft Pass 1
```

---

## Main goals

### 1. Build a sector inventory

Scan these WSC files:

```text
release64/pressstart.wsc
release64/sp_idle.wsc
release64/main.wsc
release64/rdr2init.wsc

multiplayer/freemode/freemode.wsc
multiplayer/PR_Multiplayer.wsc
multiplayer/multiplayer_system_thread.wsc
multiplayer/multiplayer_update_thread.wsc
```

Find and classify:

```text
ENABLE_CHILD_SECTOR
DISABLE_CHILD_SECTOR
ENABLE_WORLD_SECTOR
DISABLE_WORLD_SECTOR
sector strings
action-area strings
spawn volume strings
ambient world strings
region/territory strings
```

Produce:

```text
reports/sp_freemode_sector_graft_pass1/sector_inventory_all.csv
reports/sp_freemode_sector_graft_pass1/mp_sector_candidates.csv
reports/sp_freemode_sector_graft_pass1/sp_sector_counterparts.csv
reports/sp_freemode_sector_graft_pass1/sector_overlap_map.csv
reports/sp_freemode_sector_graft_pass1/recommended_sector_test_order.md
```

The inventory should include:

```text
source_file
function/callsite if available
native/call kind if available
sector_name
enabled_or_disabled
likely_region
mp_or_sp
risk_level
notes
```

---

### 2. Build SP/MP sector counterpart map

Important idea:

```text
Some MP sectors may replace SP sectors, not just add to them.
```

Find relationships like:

```text
SP sector active -> MP counterpart disabled
MP sector active -> SP counterpart should unload
```

Specifically check known MP-ish strings previously seen:

```text
mp_tes_coop01ax
mp_tes_coop01bx
mp_tes_coop01cx
mp_tes_coop02x
mp_tes_base01x
mp_gap_mineLid01x
mp_fom_coop01x
mp_fom_burntDebris01x
mp_wld_base03x
mp_nos_coop01ax
mp_nos_coop01bx
mp_nos_coop01cx
mp_nos_coop01dx
mp_nos_coop01ex
mp_scr_coop01x
arm_flags01x
chu_flags01x
esc_flags01x
han_flags01x
hen_flags01x
mtp_flags01x
mp_arm_base01x
mp_cas_base01x
mp_pik_base01x
mp_tes_base01x
mp_tum_base01x
mp_arm_ffa01x
mp_chu_ffa01x
mp_esc_ffa01x
mp_hen_ffa01x
mp_lsh_ffa01x
mp_pik_ffa01x
mp_upr_ffa01x
mp_chu_platforms01x
mp_mtp_base01x
mp_fom_base01x
mp_fom_ffa01x
mp_wld_base01x
mp_chu_base01x
```

Also pull additional sector/action-area names from `freemode.wsc`, `PR_Multiplayer.wsc`, and `multiplayer_system_thread.wsc`.

---

### 3. Do not broadly flip sectors

Previous sector/native flip tests got stuck in loading. Do **not** enable all MP sectors at once.

Build tiny sector variants:

```text
A0_repack_control
A1_one_known_safe_sector
A2_frontier_small_set
A3_chuparosa_small_set
A4_armadillo_small_set
A5_one_base_sector_plus_unload_sp_counterpart
A6_one_action_area_sector_only
```

Each variant should change as little as possible.

---

## WSC creation/editing plan

Since we can edit WSC better now, create a conservative SP-side sector probe instead of forcing MP mode.

### Preferred route

If Code RED now supports safe WSC authoring/repacking:

```text
Create a new tiny WSC carrier that only performs sector operations and logs.
```

Potential logical name:

```text
$/content/scripting/designerdefined/codered_sp_freemode_sector_probe
```

It should:

```text
wait until SP world is loaded
enable exactly one sector or one tiny sector set
optionally disable exactly one SP counterpart sector
print/log before and after each action if available
terminate or idle safely
```

### If full WSC creation is not reliable

Use a known-safe PC WSC as a carrier/template:

```text
small existing PC WSC
or previously safe hello_bootstrap.wsc carrier
```

Rules:

```text
Do not invent an unsupported WSC compiler claim.
Do not rely on a new WSC unless:
  - Code RED opens it
  - MagicRDR opens it
  - RPF readback matches
  - cloned RPF boots
```

If no reliable new WSC path exists, patch an existing safe SP script at a late safe point with one sector operation.

---

## Suggested WSC sector probe behavior

Pseudocode intent:

```c
main()
{
    PRINTSTRING("CodeRED SP FreeMode sector probe start\n");

    while (!STREAMING_IS_WORLD_LOADED())
    {
        WAIT(0);
    }

    WAIT(3000);

    PRINTSTRING("CodeRED enabling sector <name>\n");
    ENABLE_CHILD_SECTOR("<one_sector_name>");

    WAIT(1000);

    PRINTSTRING("CodeRED sector probe done\n");
    TERMINATE_THIS_SCRIPT();
}
```

If `ENABLE_WORLD_SECTOR` is more appropriate for some names, test separately.

Do not combine child and world sector calls in the same first probe.

---

## Where to launch the sector probe

Do not use MP boot.

Launch from stable single-player path.

Candidate SP launch points:

```text
sp_idle.wsc
main.wsc
rdr2init.wsc
pressstart.wsc after normal start/load
```

Best first target:

```text
sp_idle.wsc after world loaded
```

Reason:

```text
sp_idle already lives in the SP idle/runtime area and likely has safe waits/loading context.
```

Avoid:

```text
boot.sc.xml direct route
net.EnterOnline
TriggerMultiplayerLoad
```

---

## Variant strategy

### A0 — Repack control

Base RPF repacked with no content changes.

Purpose:

```text
Ensure builder/repack is not the crash source.
```

### A1 — Existing SP script late no-op log

Patch/insert a harmless no-op/log string if possible.

Purpose:

```text
Prove the WSC edit/launch point is actually reached and safe.
```

### A2 — Enable one MP sector only

One sector only, from the lowest-risk list.

Pick a sector already referenced in PC `pressstart.wsc` or `sp_idle.wsc`.

Purpose:

```text
Prove sector enable can happen in SP without loading MP mode.
```

### A3 — Enable one MP sector + unload one SP counterpart

Only if A2 boots.

Purpose:

```text
Test replacement behavior rather than stacking sectors.
```

### A4 — Region small set

Only 2-4 related sectors from same region.

Purpose:

```text
Test a visible MP area cluster.
```

### A5 — Sector + one blip/action-area marker

Only if sector itself is stable.

Purpose:

```text
Begin grafting gameplay/UI content.
```

---

## Reports required

```text
reports/sp_freemode_sector_graft_pass1/pass_report.md
reports/sp_freemode_sector_graft_pass1/sector_inventory_all.csv
reports/sp_freemode_sector_graft_pass1/sector_test_variants.csv
reports/sp_freemode_sector_graft_pass1/wsc_edit_validation.csv
reports/sp_freemode_sector_graft_pass1/rpf_readback.csv
reports/sp_freemode_sector_graft_pass1/magicrdr_compat.csv
```

For every variant:

```text
variant_name
base_sha1
changed_files
sector_enabled
sector_disabled
launch_point
expected behavior
risk
output_rpf_path
readback_status
MagicRDR status for changed WSC
```

---

## Do not do in this pass

Do not:

```text
launch freemode.wsc
launch multiplayer_update_thread.wsc
launch PR_Multiplayer.wsc
launch multiplayer_system_thread.wsc
call net.EnterOnline
call TriggerMultiplayerLoad
call StartGameWish
force avatar picker
force save bypass
patch broad freemode strings
enable all MP sectors
remove save prompts
edit live content.rpf
```

This is a sector/content graft pass, not an MP mode boot pass.

---

## Success criteria

A successful pass is:

```text
single-player boots
sector probe runs or safely applies one sector change
game does not crash
reports identify next sector groups to test
```

A great pass is:

```text
one MP sector or sector group visibly appears/loads inside SP
without entering MP
without networking/auth
without update_thread
```

---

## Short instruction

Treat FreeMode as a content library.

Find its sectors, map them to SP, and build a tiny SP-side WSC sector loader that enables one piece at a time.
