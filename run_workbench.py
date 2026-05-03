from __future__ import annotations

"""Compatibility launcher for the old Code RED Resource Workbench path.

The canonical launcher is now main.py. This wrapper preserves the old
MP-Companion startup behavior for users or shortcuts that still call
run_workbench.py directly, while sharing main.py crash logging and path setup.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as codered_main  # noqa: E402


if __name__ == '__main__':
    raise SystemExit(
        codered_main.main([
            '--legacy-companion-workspace',
            '--title',
            'Code RED Resource Workbench',
            *sys.argv[1:],
        ])
    )
