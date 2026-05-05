#!/usr/bin/env python3
"""
Code RED gringo descriptor scanner.

Read-only scanner for extracted RPF workspaces. This focuses on XML-like gringo
descriptor files that reference compiled gringo scripts through fields such as:

- mp_QueryName
- mp_ScriptName
- GringoComponentList
- ActivationRadius
- bCritical
- bMaintainState
- bLargeScript

Use this after the WSC/SCO inspector shows that scripts are mostly compiled and
not string-readable.

Usage from repo root:
  py -3 tools/codered_scan_gringo_descriptors.py --root "C:\\Users\\glitc\\OneDrive\\Desktop\\CodeRED_RPF_Extracts"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

SCRIPT_LEADS = [
    "playercamp", "campfire", "vehicle_generator", "car_gringo", "playercar",
    "carcrank_gringo", "gen_vehicle_brain", "zombie_camp",
]

FIELD_PATTERNS = {
    "mp_QueryName": re.compile(r"<mp_QueryName[^>]*>(.*?)</mp_QueryName>", re.I | re.S),
    "mp_ScriptName": re.compile(r"<mp_ScriptName[^>]*>(.*?)</mp_ScriptName>", re.I | re.S),
    "ActivationRadius": re.compile(r"<ActivationRadius[^>]*value=\"([^\"]*)\"", re.I),
    "bCritical": re.compile(r"<bCritical[^>]*value=\"([^\"]*)\"", re.I),
    "bMaintainState": re.compile(r"<bMaintainState[^>]*value=\"([^\"]*)\"", re.I),
    "bLargeScript": re.compile(r"<bLargeScript[^>]*value=\"([^\"]*)\"", re.I),
}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def clean_xml_text(value: str) -> str:
    # Rockstar XML commonly stores the useful text inside tag text, with
    # content="ascii" on the node. Keep this conservative.
    return re.sub(r"\s+", " ", value or "").strip()


def extract_regex_fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, pattern in FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            out[key] = clean_xml_text(match.group(1))
    return out


def extract_xml_fields(path: Path, text: str) -> dict[str, str]:
    fields = extract_regex_fields(text)
    try:
        root = ET.fromstring(text)
    except Exception:
        return fields

    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag in {"mp_QueryName", "mp_ScriptName"} and elem.text:
            fields[tag] = clean_xml_text(elem.text)
        if tag in {"ActivationRadius", "bCritical", "bMaintainState", "bLargeScript"}:
            value = elem.attrib.get("value")
            if value is not None:
                fields[tag] = value
    return fields


def score_descriptor(rel: str, text: str, fields: dict[str, str]) -> int:
    joined = (rel + "\n" + text + "\n" + json.dumps(fields)).lower()
    score = 0
    for lead in SCRIPT_LEADS:
        if lead.lower() in joined:
            score += 20
    if "vehicle" in joined:
        score += 25
    if "car" in joined:
        score += 20
    if "playercamp" in joined:
        score += 30
    if "mp_scriptname" in joined or "mp_ScriptName" in fields:
        score += 15
    if "activationradius" in joined or "ActivationRadius" in fields:
        score += 5
    return score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Extracted RPF root folder")
    parser.add_argument("--out", default="logs/gringo_descriptor_scan", help="Output prefix")
    parser.add_argument("--top", type=int, default=250)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Missing root: {root}")

    rows = []
    for path in root.rglob("*.xml"):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "gringo" not in (rel + text).lower() and "mp_scriptname" not in text.lower():
            continue
        fields = extract_xml_fields(path, text)
        score = score_descriptor(rel, text, fields)
        if score <= 0 and not fields:
            continue
        rows.append({
            "score": score,
            "relative_path": rel,
            "size": path.stat().st_size,
            "sha1": sha1(path),
            "mp_QueryName": fields.get("mp_QueryName", ""),
            "mp_ScriptName": fields.get("mp_ScriptName", ""),
            "ActivationRadius": fields.get("ActivationRadius", ""),
            "bCritical": fields.get("bCritical", ""),
            "bMaintainState": fields.get("bMaintainState", ""),
            "bLargeScript": fields.get("bLargeScript", ""),
        })

    rows.sort(key=lambda row: (-row["score"], row["relative_path"]))
    rows = rows[: args.top]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_path = out.with_suffix(".json")
    csv_path = out.with_suffix(".csv")
    md_path = out.with_suffix(".md")

    report = {
        "root": str(root),
        "boundary": "Read-only descriptor scan. No archives or game files modified.",
        "candidate_count": len(rows),
        "rows": rows,
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["score", "relative_path"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    lines = [
        "# Code RED Gringo Descriptor Scan",
        "",
        f"Root: `{root}`",
        f"Candidates: `{len(rows)}`",
        "",
        "Boundary: read-only descriptor scan. No archives or game files modified.",
        "",
    ]
    for row in rows[:80]:
        lines.append(f"## score {row['score']} — `{row['relative_path']}`")
        lines.append(f"- mp_QueryName: `{row['mp_QueryName']}`")
        lines.append(f"- mp_ScriptName: `{row['mp_ScriptName']}`")
        lines.append(f"- ActivationRadius: `{row['ActivationRadius']}`")
        lines.append(f"- bCritical: `{row['bCritical']}`")
        lines.append(f"- bMaintainState: `{row['bMaintainState']}`")
        lines.append(f"- bLargeScript: `{row['bLargeScript']}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("# Code RED Gringo Descriptor Scan")
    print(f"Root: {root}")
    print(f"Candidates: {len(rows)}")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    print(f"MD: {md_path}")
    for row in rows[:12]:
        print(f"  score={row['score']:>3} {row['relative_path']} -> {row['mp_ScriptName']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
