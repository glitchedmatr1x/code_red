#!/usr/bin/env python3
"""Build/refresh the CodeRED DualGunLab left-hand bypass plan from prior reports."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CodeRED DualGunLab left-hand bypass JSON plan")
    parser.add_argument("--attachment-report", default="reports/wft_wedt_attachment_lab")
    parser.add_argument("--out", default="reports/dualgun_left_hand_bypass/dualgun_left_hand_bypass_plan.json")
    args = parser.parse_args()
    src = Path(args.attachment_report)
    weapon_rows = read_csv(src / "weapon_dualgun_comparison.csv")
    hand_rows = read_csv(src / "smic_player_hand_rows.csv")
    gunbelt_rows = read_csv(src / "smic_gunbelt_rows.csv")
    dual = next((r for r in weapon_rows if r.get("weapon_file") == "base_dualpistol.weap"), {})
    pistol = next((r for r in weapon_rows if r.get("weapon_file") == "base_pistol.weap"), {})
    long_refs = [r for r in weapon_rows if r.get("has_real_act_animset") == "1"][:4]
    locators = []
    for row in hand_rows:
        for item in (row.get("smics") or "").split():
            if "hand" in item.lower() and item not in locators:
                locators.append(item)
    if not locators:
        locators = ["smic_player_default_hand_1_rm", "smic_player_default_hand_1"]
    payload = {
        "schema": "codered.dualgun_left_hand_bypass_plan.v1",
        "mode": "script_hook_runtime_bypass",
        "goal": "Make left-hand pistol usable without waiting for full native dual-wield animation rebuild.",
        "decision": "Do not rely on base_dualpistol native AnimSet yet; it resolves to DoNothing/no AnimSet in current tune data.",
        "right_hand": {
            "mode": "native_equipped_weapon",
            "reason": "Keep normal game weapon, camera, ammo, and right-trigger path stable."
        },
        "left_hand": {
            "mode": "attached_prop_plus_simulated_fire",
            "first_locator": locators[0],
            "fallback_locator": locators[1] if len(locators) > 1 else locators[0],
            "initial_offset": [0.030, 0.018, -0.055],
            "initial_eulers": [-6.0, 0.0, 88.0],
            "initial_muzzle_offset": [0.0, 0.030, -0.100],
            "requires_native_probe": [
                "create object/prop or usable weapon fragment instance",
                "attach object/prop to player locator/bone",
                "raycast/projectile/damage native for independent left fire"
            ]
        },
        "weapon_data": {
            "base_dualpistol": dual,
            "base_pistol": pistol,
            "long_gun_act_animset_references": long_refs
        },
        "source_counts": {
            "player_hand_rows": len(hand_rows),
            "gunbelt_rows": len(gunbelt_rows),
            "weapon_rows": len(weapon_rows),
        },
        "guardrails": [
            "No WFT/WEDT mutation in this pass.",
            "No guessed actor enum spawns.",
            "No native attach/fire call unless SDK hash and signature are confirmed.",
            "Save offsets to scratch/codered_dualgunlab_state.json before patching tune/model data."
        ]
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
