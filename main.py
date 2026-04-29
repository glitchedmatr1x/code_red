from __future__ import annotations

import importlib.util
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / 'logs'
for folder in (ROOT / 'imports', ROOT / 'game', ROOT / 'logs', ROOT / 'combine updates'):
    folder.mkdir(parents=True, exist_ok=True)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_crash_log(exc: BaseException) -> Path:
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = LOGS_DIR / f'code_red_main_crash_{stamp}.log'
    path.write_text('Code RED main crash\n\n' + traceback.format_exc(), encoding='utf-8')
    return path

def main() -> int:
    try:
        wb = _load_module('codered_workbench', ROOT / 'python_workbench.py')
        app = wb.WorkbenchApp(startup_workspace=ROOT)
        app.title('Code RED')
        app.mainloop()
        return 0
    except Exception as exc:
        crash_path = _write_crash_log(exc)
        print(f'Code RED crash log written to {crash_path}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
