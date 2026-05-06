#!/usr/bin/env python3
"""Conservative Code RED launcher helper.

Copy this file into the Code_RED folder and run:
    python launch_code_red.py

It prefers the packaged executable if present, then the intended Python runner,
then the implementation fallback.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXE_CANDIDATES = ["Code_RED.exe", "Code RED.exe"]
PY_CANDIDATES = ["run_workbench.py", "python_workbench.py"]


def run() -> int:
    os.chdir(ROOT)
    print(f"[Code RED] Starting from: {ROOT}")

    for name in EXE_CANDIDATES:
        path = ROOT / name
        if path.exists():
            print(f"[Code RED] Launching {name}")
            return subprocess.call([str(path)])

    for name in PY_CANDIDATES:
        path = ROOT / name
        if path.exists():
            print(f"[Code RED] Launching {name}")
            return subprocess.call([sys.executable, str(path)])

    print("[Code RED] No launch target found.")
    print("Expected one of: Code_RED.exe, Code RED.exe, run_workbench.py, python_workbench.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
