
from __future__ import annotations
import argparse, json, os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from python_workbench import cleanup_candidates, human_size

def main() -> int:
    ap = argparse.ArgumentParser(description="Report removable bulk for Code RED Lite style packages.")
    ap.add_argument("path", nargs="?", default=str(ROOT))
    ap.add_argument("--output", default=str(ROOT / "docs" / "cleanup_audit.json"))
    args = ap.parse_args()
    scan_root = Path(args.path).resolve()
    items = cleanup_candidates(scan_root)
    total = 0
    for item in items:
        # human-readable sizes are kept in report; total best-effort omitted for exactness.
        pass
    report = {
        "scan_root": str(scan_root),
        "candidate_count": len(items),
        "policy": [
            "Do not ship raw RPF/resource archives inside the runtime app.",
            "Do not ship __pycache__, captures, old screenshots, backups, split zips, or compiler source trees.",
            "Keep README, Python entry points, small metadata, and empty folders needed by the runtime.",
        ],
        "candidates": items,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
