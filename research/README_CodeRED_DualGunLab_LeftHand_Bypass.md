# CodeRED DualGunLab — Left-Hand Bypass Pass

This pass starts the practical dual-pistol path without waiting for a full WFT/WEDT or AnimSet rebuild.

## Decision

The safe bypass is:

```text
right hand = native equipped pistol / normal game weapon path
left hand  = attached pistol prop + ScriptHook simulated left fire
```

The previous attachment scan showed `base_dualpistol.weap` and `base_pistol.weap` both use `ACTFileName=donothing`, `ACTRoot=DoNothing`, and no real `AnimSet`, while long guns carry real ACT/AnimSet/IK data. That means native dual-pistol data is not enough yet. The left-hand weapon should be proved through ScriptHook first.

## Added files

```text
related_apps/Code_RED_ScriptHookRDR_DualGunLab/CodeRED_DualGunLab.cpp
related_apps/Code_RED_ScriptHookRDR_DualGunLab/CodeRED_DualGunLab.ini
related_apps/Code_RED_ScriptHookRDR_DualGunLab/build_dualgunlab.bat
tools/codered_dualgun_native_probe.py
tools/codered_dualgun_plan_builder.py
reports/dualgun_left_hand_bypass/dualgun_left_hand_bypass_plan.json
reports/dualgun_left_hand_bypass/source_script_hook_dualgun_attachment_plan.json
reports/dualgun_left_hand_bypass/weapon_dualgun_comparison.csv
reports/dualgun_left_hand_bypass/smic_player_hand_rows.csv
reports/dualgun_left_hand_bypass/smic_gunbelt_rows.csv
```

## Controls in the lab plugin

```text
F9  toggle overlay
F10 toggle DualGunLab enabled
F11 left-fire bypass pulse
F12 save state JSON
Numpad 4/6, 8/2, 7/9 nudge left pistol XYZ offset
Numpad 1/3, 5/0, +/- nudge pitch/yaw/roll
```

The plugin writes:

```text
CodeRED_DualGunLab.log
scratch/codered_dualgunlab_state.json
```

## Build

Run from the Code_RED repository root in a Visual Studio x64 Native Tools Command Prompt:

```bat
related_apps\Code_RED_ScriptHookRDR_DualGunLab\build_dualgunlab.bat
```

Copy these beside `RDR.exe`:

```text
related_apps\Code_RED_ScriptHookRDR_DualGunLab\build\CodeRED_DualGunLab.asi
related_apps\Code_RED_ScriptHookRDR_DualGunLab\CodeRED_DualGunLab.ini
```

## Native hash/signature gate

The first build is intentionally protected. It will not blind-call unknown attach/projectile natives. Run the probe against the ScriptHookRDR SDK first:

```bat
py -3 tools\codered_dualgun_native_probe.py "D:\Path\To\ScriptHookRDR_SDK" --out reports\dualgun_left_hand_bypass
```

Then review:

```text
reports\dualgun_left_hand_bypass\scripthook_native_candidates.csv
reports\dualgun_left_hand_bypass\CodeRED_DualGunLab.native_suggestions.ini
```

Only copy confirmed native hashes/signatures into `CodeRED_DualGunLab.ini`.

## Why this is a bypass

A true native dual-pistol route needs the real animation/action/attachment path. The current data suggests that dual pistol has no useful AnimSet in the base weapon file, so the first playable proof should bypass that missing layer:

```text
1. Native right-hand pistol remains unchanged.
2. Left pistol is attached to smic_player_default_hand_1_rm.
3. Left trigger gets its own simulated projectile/raycast/damage path.
4. Offsets are tuned live and saved.
5. Only after visual/fire proof do we patch WFT/WEDT, tune, ACT, ASD, or NaturalMotion.
```
