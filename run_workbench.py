from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET_CANDIDATES = [
    ROOT / "related_apps" / "Code_RED_MP_Companion_v19",
    ROOT / "data" / "Code_RED_MP_Companion_v19",
    ROOT / "Code_RED_MP_Companion_v19",
]
TARGET = next((candidate for candidate in TARGET_CANDIDATES if candidate.exists()), ROOT)

spec = importlib.util.spec_from_file_location("codered_workbench", ROOT / "python_workbench.py")
if spec is None or spec.loader is None:
    raise SystemExit("Could not load python_workbench.py")
module = importlib.util.module_from_spec(spec)
sys.modules["codered_workbench"] = module
spec.loader.exec_module(module)
app = module.WorkbenchApp(startup_workspace=TARGET if TARGET.exists() else ROOT)
app.title("Code RED Resource Workbench")
app.mainloop()
