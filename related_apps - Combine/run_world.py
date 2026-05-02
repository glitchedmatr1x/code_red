from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from code_red_cleanroom_world_v32 import main
except Exception as exc:
    print("Code RED 3D world could not start.", file=sys.stderr)
    print("Panda3D is probably not installed for this Python.", file=sys.stderr)
    print("Run install_runtime.bat, then retry.", file=sys.stderr)
    print(f"Import error: {exc}", file=sys.stderr)
    raise SystemExit(1)

if __name__ == "__main__":
    raise SystemExit(main())
