#!/usr/bin/env python3
"""
Code RED AI Menu car-spawn readiness doctor.

Read-only local scan. This is different from checking whether the menu loads
camp_car_probe. It checks whether the existing ScriptHookRDR AI Menu can spawn
ACTOR_VEHICLE_Car01 directly from its native bridge/menu data.

Run from repo root:
  py -3 tools\codered_ai_menu_car_spawn_doctor.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path

MENU_SOURCE_CANDIDATES = [
    "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp",
    "related_apps/CodeRED_Script_Workshop/workspace/edit/related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp",
    "related_apps/CodeRED_Script_Workshop/workspace/import_queue/related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.bridge_candidate.cpp",
]

DATA_CANDIDATES = [
    "data/codered/actor_enum_map.csv",
    "data/codered/npc_roster.txt",
    "data/codered/ai_behavior_actions.csv",
    "related_apps/CodeRED_Script_Workshop/workspace/edit/data/codered/actor_enum_map.csv",
    "related_apps/CodeRED_Script_Workshop/workspace/edit/data/codered/npc_roster.txt",
    "related_apps/CodeRED_Script_Workshop/workspace/edit/data/codered/ai_behavior_actions.csv",
]

REQUIRED_SOURCE_TOKENS = [
    "CR_NATIVE_CREATE_ACTOR_IN_LAYOUT",
    "CR_NATIVE_GET_PLAYER_ACTOR",
    "CR_NATIVE_GET_POSITION",
    "CR_NATIVE_START_VEHICLE",
    "CR_NATIVE_GET_VEHICLE",
    "CREATE_ACTOR_IN_LAYOUT",
    "START_VEHICLE",
    "GET_VEHICLE",
]

CAR_ENUM_TOKENS = [
    "ACTOR_VEHICLE_Car01",
    "VEHICLE_Car01",
    "Car01",
    "car01",
]

ACTION_TOKENS = [
    "spawn_selected_npc_request",
    "status_request",
    "regroup_near_player_request",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def file_row(root: Path, rel: str) -> dict:
    path = root / rel
    return {
        "relative_path": rel,
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else None,
    }


def find_source(root: Path) -> tuple[Path | None, str]:
    for rel in MENU_SOURCE_CANDIDATES:
        path = root / rel
        if path.exists():
            return path, rel
    return None, ""


def scan_actor_enum_maps(root: Path) -> list[dict]:
    rows = []
    for rel in DATA_CANDIDATES:
        if "actor_enum_map" not in rel:
            continue
        path = root / rel
        text = read_text(path)
        if not text:
            rows.append({"relative_path": rel, "exists": path.exists(), "has_car01": False, "matches": []})
            continue
        matches = []
        for line in text.splitlines():
            low = line.lower()
            if any(token.lower() in low for token in CAR_ENUM_TOKENS):
                matches.append(line.strip())
        rows.append({
            "relative_path": rel,
            "exists": True,
            "has_car01": bool(matches),
            "matches": matches[:20],
        })
    return rows


def scan_rosters(root: Path) -> list[dict]:
    rows = []
    for rel in DATA_CANDIDATES:
        if "npc_roster" not in rel:
            continue
        path = root / rel
        text = read_text(path)
        matches = []
        if text:
            for line in text.splitlines():
                low = line.lower()
                if any(token.lower() in low for token in CAR_ENUM_TOKENS) or "car" in low or "vehicle" in low:
                    matches.append(line.strip())
        rows.append({
            "relative_path": rel,
            "exists": path.exists(),
            "has_vehicle_roster_entry": bool(matches),
            "matches": matches[:20],
        })
    return rows


def scan_actions(root: Path) -> list[dict]:
    rows = []
    for rel in DATA_CANDIDATES:
        if "ai_behavior_actions" not in rel:
            continue
        path = root / rel
        text = read_text(path)
        matches = []
        if text:
            for line in text.splitlines():
                low = line.lower()
                if any(token.lower() in low for token in ACTION_TOKENS) or "vehicle" in low or "car" in low:
                    matches.append(line.strip())
        rows.append({
            "relative_path": rel,
            "exists": path.exists(),
            "has_spawn_action": "spawn_selected_npc_request" in text,
            "has_vehicle_action": any("vehicle" in m.lower() or "car" in m.lower() for m in matches),
            "matches": matches[:30],
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="logs/ai_menu_car_spawn_doctor")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    source_path, source_rel = find_source(root)
    source_text = read_text(source_path) if source_path else ""

    source_token_status = {token: token in source_text for token in REQUIRED_SOURCE_TOKENS}
    has_source_core = all(source_token_status.values())
    has_direct_car_literal = any(token in source_text for token in CAR_ENUM_TOKENS)
    has_spawn_request_impl = "spawn_selected_npc_request" in source_text
    has_create_actor_call = "CR_NATIVE_CREATE_ACTOR_IN_LAYOUT" in source_text
    has_start_vehicle_call = "CR_NATIVE_START_VEHICLE" in source_text

    enum_rows = scan_actor_enum_maps(root)
    roster_rows = scan_rosters(root)
    action_rows = scan_actions(root)

    enum_has_car = any(row["has_car01"] for row in enum_rows)
    roster_has_vehicle = any(row["has_vehicle_roster_entry"] for row in roster_rows)
    actions_have_spawn = any(row["has_spawn_action"] for row in action_rows)

    verdict = []
    if source_path:
        verdict.append(f"AI menu source found: {source_rel}")
    else:
        verdict.append("AI menu source not found in expected related_apps paths")
    if has_source_core and has_spawn_request_impl and has_create_actor_call:
        verdict.append("AI menu source has the core native bridge and spawn action machinery")
    else:
        verdict.append("AI menu source is missing one or more core spawn/native pieces")
    if enum_has_car:
        verdict.append("actor enum map contains a Car01/vehicle entry")
    else:
        verdict.append("actor enum map does not show a Car01/vehicle entry yet")
    if roster_has_vehicle:
        verdict.append("roster contains a vehicle/car entry")
    else:
        verdict.append("roster does not show a vehicle/car entry yet")
    if actions_have_spawn:
        verdict.append("action menu contains spawn_selected_npc_request")
    else:
        verdict.append("action menu does not show spawn_selected_npc_request")

    likely_ready = bool(source_path and has_source_core and has_spawn_request_impl and has_create_actor_call and enum_has_car and actions_have_spawn)
    if likely_ready:
        verdict.append("LIKELY READY for a direct AI-menu car spawn test if the menu build/install itself loads in-game")
    else:
        verdict.append("NOT READY for direct AI-menu car spawn without adding menu data or source wiring")

    report = {
        "root": str(root),
        "source": file_row(root, source_rel) if source_rel else None,
        "source_token_status": source_token_status,
        "has_direct_car_literal_in_source": has_direct_car_literal,
        "has_spawn_request_impl": has_spawn_request_impl,
        "has_create_actor_call": has_create_actor_call,
        "has_start_vehicle_call": has_start_vehicle_call,
        "actor_enum_maps": enum_rows,
        "rosters": roster_rows,
        "actions": action_rows,
        "likely_ready": likely_ready,
        "verdict": verdict,
        "boundary": "Read-only local scan. No files modified.",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_path = out.with_suffix(".json")
    md_path = out.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Code RED AI Menu Car Spawn Doctor",
        "",
        f"Root: `{root}`",
        "",
        "Boundary: read-only local scan. No files modified.",
        "",
        "## Verdict",
        "",
    ]
    for item in verdict:
        lines.append(f"- {item}")
    lines.extend(["", "## Source token status", ""])
    for token, present in source_token_status.items():
        lines.append(f"- `{token}`: `{present}`")
    lines.extend(["", "## Actor enum maps", ""])
    for row in enum_rows:
        lines.append(f"### `{row['relative_path']}` exists=`{row['exists']}` has_car01=`{row['has_car01']}`")
        for match in row.get("matches", [])[:10]:
            lines.append(f"- `{match}`")
    lines.extend(["", "## Rosters", ""])
    for row in roster_rows:
        lines.append(f"### `{row['relative_path']}` exists=`{row['exists']}` has_vehicle_entry=`{row['has_vehicle_roster_entry']}`")
        for match in row.get("matches", [])[:10]:
            lines.append(f"- `{match}`")
    lines.extend(["", "## Actions", ""])
    for row in action_rows:
        lines.append(f"### `{row['relative_path']}` exists=`{row['exists']}` has_spawn_action=`{row['has_spawn_action']}` has_vehicle_action=`{row['has_vehicle_action']}`")
        for match in row.get("matches", [])[:10]:
            lines.append(f"- `{match}`")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("# Code RED AI Menu Car Spawn Doctor")
    print(f"Root: {root}")
    print(f"JSON: {json_path}")
    print(f"MD: {md_path}")
    print(f"likely_ready: {likely_ready}")
    for item in verdict:
        print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
