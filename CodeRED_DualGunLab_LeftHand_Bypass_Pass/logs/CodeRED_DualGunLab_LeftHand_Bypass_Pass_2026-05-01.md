# CodeRED DualGunLab — Left-Hand Bypass Pass

Date: 2026-05-01

## Summary

This pass adds a guarded ScriptHookRDR lab for the dual-pistol experiment. It does not mutate WFT/WEDT files and does not guess unsafe native signatures.

The working design is a bypass:

```text
right hand = native weapon path
left hand = prop/fragment attachment + simulated left fire
```

## Why

The attachment decoder found `smic_player_default_hand_1_rm` and `smic_player_default_hand_1` as usable player hand SMIC references. It also found that `base_dualpistol.weap` does not currently expose a real ACT/AnimSet path; it uses `donothing` / `DoNothing` / no AnimSet. The left side therefore needs to be proven through ScriptHook runtime control first.

## Added

```text
related_apps/Code_RED_ScriptHookRDR_DualGunLab/CodeRED_DualGunLab.cpp
related_apps/Code_RED_ScriptHookRDR_DualGunLab/CodeRED_DualGunLab.ini
related_apps/Code_RED_ScriptHookRDR_DualGunLab/build_dualgunlab.bat
tools/codered_dualgun_native_probe.py
tools/codered_dualgun_plan_builder.py
reports/dualgun_left_hand_bypass/*
```

## Current guardrails

- No guessed actor enum spawns.
- No guessed WFT/WEDT patching.
- No guessed attach/fire native calls.
- Runtime overlay and JSON proof are safe to test first.
- Actual visual attach and damage/fire requires confirmed ScriptHookRDR native hashes/signatures.

## Next milestone

1. Run `codered_dualgun_native_probe.py` against the ScriptHookRDR SDK.
2. Confirm create/attach/detach/projectile/raycast signatures.
3. Unlock the guarded attach call inside `CodeRED_DualGunLab.cpp`.
4. Tune offsets in-game using the Numpad controls.
5. Save the working offset JSON.
6. Only then convert the runtime proof into a model/tune patch.
