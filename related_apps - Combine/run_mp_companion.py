from __future__ import annotations
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_CANDIDATES = [
    ROOT / "Code_RED_MP_Companion_v19" / "mp_companion.py",
    ROOT / "data" / "Code_RED_MP_Companion_v19" / "mp_companion.py",
    ROOT.parent / "data" / "Code_RED_MP_Companion_v19" / "mp_companion.py",
]
APP = next((candidate for candidate in APP_CANDIDATES if candidate.exists()), APP_CANDIDATES[0])
if not APP.exists():
    checked = "\n".join(str(candidate) for candidate in APP_CANDIDATES)
    raise SystemExit(f"Missing MP Companion. Checked:\n{checked}")
runpy.run_path(str(APP), run_name="__main__")
