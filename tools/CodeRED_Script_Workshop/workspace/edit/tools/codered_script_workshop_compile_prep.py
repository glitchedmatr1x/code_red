#!/usr/bin/env python3
"""Compatibility wrapper for Script Workshop compile/edit prep.

The standalone extension now owns the safe edit/import/recompile queue workflow.
This wrapper preserves the existing Code RED lane command and generated manifest names.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "related_apps" / "CodeRED_Script_Workshop" / "CodeRED_Script_Workshop.py"

if not APP.exists():
    raise SystemExit(f"Missing Script Workshop extension: {APP}")

sys.path.insert(0, str(APP.parent))
from CodeRED_Script_Workshop import main  # type: ignore  # noqa: E402

if __name__ == "__main__":
    args = list(sys.argv[1:])
    # Prep maps to scan/refresh so candidates, queues, and proof plan are regenerated.
    if not args or args[0].startswith("--"):
        args = ["scan", *args]
    raise SystemExit(main(args))
