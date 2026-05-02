from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
raise SystemExit(subprocess.call([sys.executable, str(ROOT / "rpf_edit_lab.py")], cwd=str(ROOT)))
