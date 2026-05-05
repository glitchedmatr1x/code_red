#!/usr/bin/env python3
"""
Code RED AI menu / related_apps doctor.

Local read-only scan. It checks whether related_apps exists, finds likely AI
menu/trainer files, and verifies whether the current camp-car proof artifacts
are present and referenced anywhere in the app files.

Run from repo root:
  py -3 tools\codered_ai_menu_doctor.py

Optional:
  py -3 tools\codered_ai_menu_doctor.py --root "D:\\Games\\Red Dead Redemption\\Code_RED"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

SCRIPT_EXTS = {".py", ".ps1", ".bat", ".cmd", ".ini", ".json", ".md", ".txt", ".cfg"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "output", "proof_packages", "playtest_kits"}
MENU_TERMS = [
    "ai", "menu", "trainer", "silent", "virtues", "scripthook", "script hook",
    "camp_car_probe", "camp car", "vehicle", "car01", "ACTOR_VEHICLE_Car01",
    "sco", "xsc", "wsc", "rpf", "spawn", "CREATE_ACTOR_IN_LAYOUT",
]
ARTIFACTS = {
    "xsc": "script_compiling/sccl/output/camp_car_probe/camp_car_probe.xsc",
    "sco": "script_compiling/sccl/output/camp_car_probe_sco/camp_car_probe.sco",
    "wsc": "script_compiling/sccl/output/camp_car_probe_wsc/camp_car_probe.wsc",
}
EXPECTED_HASHES = {
    "xsc": "C8DC6821D04A76302C123814A8DCBD507DD6200E",
    "sco": "0351E47E3B0F5C6BA7C8D75A6C8FDA92A78D8C8B",
    "wsc": "2729784CA37478DD22E0CFE8BD52B11793A36E14",
}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            yield base / name


def score_file(path: Path, root: Path) -> dict | None:
    rel = path.relative_to(root).as_posix()
    low_rel = rel.lower()
    if path.suffix.lower() not in SCRIPT_EXTS and not any(term in low_rel for term in ["ai", "menu", "trainer", "silent", "virtues"]):
        return None
    text = read_text(path)
    low = (low_rel + "\n" + text[:200000]).lower()
    hits = sorted({term for term in MENU_TERMS if term.lower() in low})
    if not hits:
        return None
    score = len(hits) * 10
    if "related_apps" in low_rel:
        score += 30
    if any(k in low_rel for k in ["ai", "menu", "trainer", "silent", "virtues"]):
        score += 20
    if "camp_car_probe" in low:
        score += 40
    return {
        "score": score,
        "relative_path": rel,
        "suffix": path.suffix.lower(),
        "size": path.stat().st_size,
        "hits": hits,
        "references_camp_car_probe": "camp_car_probe" in low,
        "references_current_artifacts": any(name in low for name in ["camp_car_probe.xsc", "camp_car_probe.sco", "camp_car_probe.wsc"]),
    }


def artifact_status(root: Path) -> list[dict]:
    rows = []
    for key, rel in ARTIFACTS.items():
        path = root / rel
        row = {
            "kind": key,
            "relative_path": rel,
            "exists": path.exists(),
            "length": None,
            "sha1": None,
            "matches_expected_current_hash": False,
        }
        if path.exists():
            row["length"] = path.stat().st_size
            row["sha1"] = sha1(path)
            row["matches_expected_current_hash"] = row["sha1"] == EXPECTED_HASHES.get(key)
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Code_RED repo root")
    parser.add_argument("--out", default="logs/ai_menu_doctor", help="Output prefix")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Missing root: {root}")

    related = root / "related_apps"
    rows = []
    scan_roots = [related] if related.exists() else [root]
    for scan_root in scan_roots:
        for path in iter_files(scan_root):
            try:
                row = score_file(path, root)
            except Exception as exc:
                row = {"score": 1, "relative_path": path.relative_to(root).as_posix(), "error": str(exc)}
            if row:
                rows.append(row)

    rows.sort(key=lambda r: (-int(r.get("score", 0)), r.get("relative_path", "")))
    artifacts = artifact_status(root)
    has_current_artifacts = all(a["exists"] and a["matches_expected_current_hash"] for a in artifacts)
    references_current = any(row.get("references_current_artifacts") for row in rows)
    references_probe = any(row.get("references_camp_car_probe") for row in rows)

    verdict = []
    if not related.exists():
        verdict.append("related_apps folder was not found locally at repo root")
    if not rows:
        verdict.append("no likely AI menu/trainer files were found by the scan")
    if has_current_artifacts:
        verdict.append("current camp-car artifacts are present and match expected hashes")
    else:
        verdict.append("one or more current camp-car artifacts are missing or hash-mismatched")
    if not references_probe:
        verdict.append("AI menu/trainer files do not appear wired to camp_car_probe yet")
    elif not references_current:
        verdict.append("AI menu/trainer mentions camp_car_probe but not the current artifact file names")
    else:
        verdict.append("AI menu/trainer appears to reference current camp-car artifacts")

    report = {
        "root": str(root),
        "related_apps_exists": related.exists(),
        "artifact_status": artifacts,
        "candidate_count": len(rows),
        "candidates": rows[:100],
        "verdict": verdict,
        "boundary": "Read-only local scan. No files modified.",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_path = out.with_suffix(".json")
    md_path = out.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Code RED AI Menu Doctor",
        "",
        f"Root: `{root}`",
        f"related_apps exists: `{related.exists()}`",
        "",
        "Boundary: read-only local scan. No files modified.",
        "",
        "## Verdict",
        "",
    ]
    for item in verdict:
        lines.append(f"- {item}")
    lines.extend(["", "## Artifact status", ""])
    for artifact in artifacts:
        lines.append(f"- `{artifact['kind']}` `{artifact['relative_path']}` exists=`{artifact['exists']}` length=`{artifact['length']}` sha1=`{artifact['sha1']}` current=`{artifact['matches_expected_current_hash']}`")
    lines.extend(["", "## Candidate AI menu / trainer files", ""])
    for row in rows[:50]:
        lines.append(f"### score {row.get('score')} — `{row.get('relative_path')}`")
        if row.get("error"):
            lines.append(f"- error: `{row['error']}`")
        else:
            lines.append(f"- hits: {', '.join(row.get('hits') or [])}")
            lines.append(f"- references camp_car_probe: `{row.get('references_camp_car_probe')}`")
            lines.append(f"- references current artifacts: `{row.get('references_current_artifacts')}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("# Code RED AI Menu Doctor")
    print(f"Root: {root}")
    print(f"related_apps exists: {related.exists()}")
    print(f"Candidates: {len(rows)}")
    print(f"JSON: {json_path}")
    print(f"MD: {md_path}")
    print("Verdict:")
    for item in verdict:
        print(f"  - {item}")
    print("Top candidates:")
    for row in rows[:10]:
        print(f"  score={row.get('score')} {row.get('relative_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
