#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codered_app.launcher_registry import build_status_report, report_to_markdown, write_status_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print or write Code RED one-app lane status.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    parser.add_argument("--write", action="store_true", help="Write logs/one_app_status outputs.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Optional output folder for --write.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.write:
        result = write_status_outputs(args.root, args.out_dir)
        report = result["report"]
        print(f"Wrote: {result['markdown']}")
        print(f"Wrote: {result['json']}")
    else:
        report = build_status_report(args.root)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report_to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
