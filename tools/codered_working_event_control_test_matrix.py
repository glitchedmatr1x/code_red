#!/usr/bin/env python3
"""
Code RED Working Event Seat/Control Test Matrix

This does not patch WSC files. It verifies the local files that should be used
for the known-good vehicle event tests and writes a clean markdown test sheet.

Usage:
  py -3 tools\codered_working_event_control_test_matrix.py report --input-dir imports --out logs\working_event_seat_control_tests
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime

EXPECTED = [
    {
        "file": "beat_crime_wagonthief.wsc",
        "role": "Confirmed truck-capable WagonThief event",
        "recommended_patch": "Use the known-good WagonThief 1183..1197 -> 1193/1194 patch.",
        "runtime_test": "F7 unlock nearest 1193/1194 seats; F8 try driver seat; F9 keep NPC driver / passenger-gunner lane.",
        "risk": "Low if tested alone.",
    },
    {
        "file": "event_roadside_ambush.wsc",
        "role": "Confirmed one-vehicle ambush event",
        "recommended_patch": "Use Ambush 1177..1188 -> 1193/1194 patch.",
        "runtime_test": "F7 unlock nearest 1193/1194 seats; F8 try driver seat.",
        "risk": "Low if tested alone.",
    },
    {
        "file": "event_roadside_prisoners.wsc",
        "role": "Confirmed transport/prison wagon replacement target",
        "recommended_patch": "Use direct-id 1197 -> 1193 Truck01 for truck-only transport test.",
        "runtime_test": "F7 unlock nearest 1193/1194 seats; check transport behavior survives.",
        "risk": "Low-medium; transport logic may still expect wagon-specific layout.",
    },
    {
        "file": "short_update_thread.wsc",
        "role": "Global mounted-gun / seat suspect",
        "recommended_patch": "Do not patch broadly in this lane.",
        "runtime_test": "Reference only until runtime unlock proves which seats are affected.",
        "risk": "High if patched globally.",
    },
]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def inspect_file(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    data = path.read_bytes()
    return {
        "exists": True,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "magic_hex": data[:4].hex().upper(),
        "is_rsc85": data[:4] == b"RSC\x85",
    }

def cmd_report(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for spec in EXPECTED:
        info = inspect_file(input_dir / spec["file"])
        rows.append({**spec, **info})

    (out / "working_event_seat_control_matrix.json").write_text(
        json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"), "input_dir": str(input_dir), "tests": rows}, indent=2),
        encoding="utf-8",
    )

    md = []
    md.append("# Code RED Working Event Seat/Control Test Matrix")
    md.append("")
    md.append(f"Generated: `{datetime.now().isoformat(timespec='seconds')}`")
    md.append(f"Input folder: `{input_dir}`")
    md.append("")
    md.append("| File | Present | RSC85 | Size | Role | Risk |")
    md.append("|---|---:|---:|---:|---|---|")
    for r in rows:
        md.append(f"| `{r['file']}` | {r.get('exists', False)} | {r.get('is_rsc85', '')} | {r.get('size', '')} | {r['role']} | {r['risk']} |")
    md.append("")
    md.append("## Test sequence")
    for i, r in enumerate(rows, 1):
        md.append(f"### {i}. {r['file']}")
        md.append(f"- Role: {r['role']}")
        md.append(f"- Patch lane: {r['recommended_patch']}")
        md.append(f"- Runtime test: {r['runtime_test']}")
        if r.get("exists"):
            md.append(f"- SHA256: `{r['sha256']}`")
        else:
            md.append("- Missing from input folder.")
        md.append("")
    md.append("## Hard rules")
    md.append("- Test one WSC event patch at a time.")
    md.append("- Do not stack population/global/dynamite/roadside robbery experiments in this lane.")
    md.append("- Runtime unlock should initially whitelist only `1193 Truck01` and `1194 Car01`.")
    md.append("- If a test crashes, roll back that one WSC and keep the runtime unlocker disabled for a control boot.")
    (out / "working_event_seat_control_matrix.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"status": "complete", "out": str(out), "files": rows}, indent=2))
    return 0

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("report")
    p.add_argument("--input-dir", default="imports")
    p.add_argument("--out", default="logs/working_event_seat_control_tests")
    p.set_defaults(func=cmd_report)
    args = ap.parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
