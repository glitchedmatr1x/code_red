#!/usr/bin/env python3
"""User-facing RPF edit lab launcher.

The GUI lives in python_workbench.py. This file exists so the one-app registry
has a stable, obvious launch target for Magic-RDR-style archive browsing.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open Code RED RPF edit lab")
    parser.add_argument("--archive", default="", help="Optional archive path to inventory first")
    args = parser.parse_args(argv)
    if args.archive:
        return subprocess.call([
            sys.executable,
            str(ROOT / "tools" / "codered_rpf_utils.py"),
            "inventory",
            "--archive",
            args.archive,
            "--out",
            str(ROOT / "logs" / "rpf_edit_lab_inventory"),
        ], cwd=str(ROOT))
    return subprocess.call([sys.executable, str(ROOT / "main.py")], cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
