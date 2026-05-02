#!/usr/bin/env python3
"""Find ScriptHookRDR SDK native candidates for CodeRED DualGunLab.

This does not call the game. It scans ScriptHookRDR SDK headers/source for native
names and hashes that look useful for a left-hand pistol prop/fire bypass.

Usage:
    py -3 tools\codered_dualgun_native_probe.py "D:\path\to\ScriptHookRDR_SDK" --out reports\dualgun_left_hand_bypass
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable

HASH_RE = re.compile(r"0x[0-9A-Fa-f]{6,16}")
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

CATEGORIES: dict[str, list[str]] = {
    "create_prop_or_object": ["CREATE_OBJECT", "CREATE_PROP", "CREATE_GRINGO", "CREATE_ITEM", "CREATE_ACTOR_IN_LAYOUT", "CREATE_OBJECT_IN_LAYOUT", "CREATE_PROP_IN_LAYOUT"],
    "attach": ["ATTACH", "BONE", "LOCATOR", "SMIC", "OBJECT_TO", "PROP_TO", "ACTOR_TO"],
    "detach_delete": ["DETACH", "DELETE_OBJECT", "DESTROY", "RELEASE_OBJECT", "REMOVE_OBJECT"],
    "weapon_fire": ["FIRE", "PROJECTILE", "BULLET", "SHOOT", "WEAPON", "AMMO", "GIVE_WEAPON"],
    "raycast_damage": ["RAY", "TRACE", "LOS", "LINE_OF_SIGHT", "DAMAGE", "APPLY_DAMAGE", "HIT"],
    "player_actor": ["GET_PLAYER_ACTOR", "GET_POSITION", "GET_HEADING", "IS_ACTOR_VALID"],
}


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for suffix in ("*.h", "*.hpp", "*.cpp", "*.c", "*.cs", "*.txt"):
        yield from root.rglob(suffix)


def classify(text_upper: str) -> list[str]:
    cats: list[str] = []
    for cat, tokens in CATEGORIES.items():
        if any(tok in text_upper for tok in tokens):
            cats.append(cat)
    return cats


def scan_file(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return rows
    for idx, line in enumerate(lines, 1):
        upper = line.upper()
        cats = classify(upper)
        if not cats:
            continue
        hashes = HASH_RE.findall(line)
        words = [w for w in WORD_RE.findall(line) if any(tok in w.upper() for toks in CATEGORIES.values() for tok in toks)]
        rows.append({
            "file": str(path),
            "line": idx,
            "categories": "|".join(cats),
            "hashes": "|".join(hashes),
            "symbols": "|".join(dict.fromkeys(words)),
            "text": line.strip()[:500],
        })
    return rows


def pick_suggestions(rows: list[dict]) -> dict[str, str]:
    suggestions = {
        "CreateObjectOrProp": "0x0",
        "DeleteObjectOrProp": "0x0",
        "AttachObjectToActorLocator": "0x0",
        "DetachObject": "0x0",
        "FireProjectileOrBullet": "0x0",
        "DamageActor": "0x0",
        "RaycastOrGetAimHit": "0x0",
    }
    priority = [
        ("CreateObjectOrProp", "create_prop_or_object", ["CREATE_OBJECT_IN_LAYOUT", "CREATE_PROP_IN_LAYOUT", "CREATE_OBJECT", "CREATE_PROP"]),
        ("AttachObjectToActorLocator", "attach", ["ATTACH", "LOCATOR", "BONE"]),
        ("DetachObject", "detach_delete", ["DETACH"]),
        ("DeleteObjectOrProp", "detach_delete", ["DELETE_OBJECT", "REMOVE_OBJECT", "DESTROY"]),
        ("FireProjectileOrBullet", "weapon_fire", ["PROJECTILE", "BULLET", "FIRE", "SHOOT"]),
        ("DamageActor", "raycast_damage", ["DAMAGE", "APPLY_DAMAGE"]),
        ("RaycastOrGetAimHit", "raycast_damage", ["RAY", "TRACE", "LINE_OF_SIGHT", "LOS"]),
    ]
    for key, cat, tokens in priority:
        candidates = []
        for row in rows:
            if cat not in row["categories"] or not row["hashes"]:
                continue
            text = row["text"].upper()
            score = sum(10 for tok in tokens if tok in text) + len(row["hashes"].split("|"))
            candidates.append((score, row))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            suggestions[key] = candidates[0][1]["hashes"].split("|")[0]
    return suggestions


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["file", "line", "categories", "hashes", "symbols", "text"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)


def write_ini(path: Path, suggestions: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[natives]",
        "GetPlayerActor=0xE8CFDD53",
        "IsActorValid=0xBA6C3E92",
        "GetPosition=0x99BD9D6F",
        "GetHeading=0x42DE39F0",
        "",
        "; Suggested by SDK scan. Review signatures before using live.",
    ]
    for key, value in suggestions.items():
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan ScriptHookRDR SDK for DualGunLab native candidates")
    parser.add_argument("sdk", help="ScriptHookRDR SDK folder, source folder, or header file")
    parser.add_argument("--out", default="reports/dualgun_left_hand_bypass")
    args = parser.parse_args()
    root = Path(args.sdk)
    out = Path(args.out)
    rows: list[dict] = []
    for file in iter_files(root):
        rows.extend(scan_file(file))
    rows.sort(key=lambda r: (r["categories"], r["file"], int(r["line"])))
    suggestions = pick_suggestions(rows)
    write_csv(out / "scripthook_native_candidates.csv", rows)
    write_ini(out / "CodeRED_DualGunLab.native_suggestions.ini", suggestions)
    (out / "native_probe_summary.json").write_text(json.dumps({
        "sdk": str(root),
        "candidate_count": len(rows),
        "suggestions": suggestions,
        "warning": "Suggestions are hash candidates only; confirm signatures before enabling attach/fire calls."
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} candidates to {out}")


if __name__ == "__main__":
    main()
