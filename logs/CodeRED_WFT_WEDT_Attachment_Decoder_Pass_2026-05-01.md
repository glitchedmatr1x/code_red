# CodeRED WFT/WEDT Attachment Decoder Pass — Findings

Date: 2026-05-01

## What was built

- `tools/codered_wft_wedt_attachment_decoder.py`
- Read-only RPF6/RSC scanner for WFT/WFD/WEDT resources.
- Tune scanner for `smictofragmap*.txt` actor/fragment attachment maps.
- Weapon tune comparison for dual-pistol, pistol, and long-gun IK/muzzle data.
- ScriptHook runtime experiment plan for left-hand prop + simulated fire.

## Inputs tested

- `fragments2.rpf` extracted from `fragments2.zip`
- `tune_d11generic.rpf` extracted from `game 1.zip` / uploaded tune archive

## Model resource proof

`fragments2.rpf` was decoded successfully:

- model resources: 148
- `.wedt`: 35
- `.wfd`: 72
- `.wft`: 41
- resource type 11: 35
- resource type 1: 72
- resource type 138: 41
- fragment bundles grouped: 42
- transform candidates exported: 934
- errors: 0

Updated type read from named resources:

| Extension | Resource type | Root VFT seen | Working meaning |
|---|---:|---|---|
| `.wedt` | 11 | `0x00D0E590` | edit-data candidate |
| `.wfd` | 1 | `0x00DDC0A0` | fragment/drawable candidate |
| `.wft` | 138 | `0x00DDB8E4` | fragment texture/model candidate |

## Attachment map proof

`tune_d11generic.rpf` contains direct attachment-adjacent map data:

- `smictofragmap.txt`
- `smictofragmap_rm.txt`

Filtered attachment rows exported:

- attachment rows: 891
- player hand rows: 104
- gunbelt rows: 777
- unique player hand SMICs: `smic_player_default_hand_1`, `smic_player_default_hand_1_rm`

This is stronger than guessing from IK data. It gives us actor/model-to-fragment component names that can be used to drive ScriptHook locator experiments.

## Dual gun / VR-style weapon finding

`base_dualpistol.weap` is not a strong native animation source by itself:

- `ACTFileName`: `donothing`
- `ACTRoot`: `DoNothing`
- `AnimSet`: `<none>`
- `IKOffset`: `0 0 0`
- `IKOffsetHold`: `0 0 0`
- `MuzzleOffset`: `0 0.029999999 -0.1`
- `CanShootFromCamera`: `1`

`base_pistol.weap` is similar: it also uses `donothing` / `<none>`. Long guns carry the useful IK/ACT reference data:

- `base_rifle.weap`
- `base_repeater.weap`
- `base_shotgun.weap`
- `base_sniperrifle.weap`
- `base_bow.weap`

These use `Rifle_1892Win`/`rifle_1892Win` ACT/AnimSet data and nonzero IK offsets. So the likely route is not “just enable dual pistol animation.” The better route is:

```text
native right-hand weapon
+ attached left-hand pistol prop
+ ScriptHook left-fire raycast / damage simulation
+ WFT/WEDT locator/fragment offsets for visual alignment
+ long-gun IK fields as reference for future body/hand stabilization
```

## Runtime plan

First ScriptHook lab should add:

1. Attach a left pistol prop to `smic_player_default_hand_1_rm` or `smic_player_default_hand_1`.
2. Add nudge controls for offset/euler tuning.
3. Save the offset preset to JSON.
4. Keep the real player weapon as the right-hand/native weapon.
5. Use ScriptHook raycast/simulated damage for the left trigger.
6. Draw debug muzzle/attachment proof on-screen.
7. Only after the visual prop is stable, compare against NaturalMotion arm/body stability.

## Important boundary

This pass still does not rebuild WFT/WEDT files. It gets the data out, groups it, exports candidate transforms, and turns it into a ScriptHook test plan. That is the right next bridge now that hooks are working.
