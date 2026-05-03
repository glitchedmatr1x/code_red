from __future__ import annotations

import argparse
import importlib.util
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / 'logs'
RUNTIME_FOLDERS = (
    ROOT / 'imports',
    ROOT / 'game',
    ROOT / 'logs',
    ROOT / 'combine updates',
)
COMPANION_WORKSPACE_CANDIDATES = (
    ROOT / 'related_apps' / 'Code_RED_MP_Companion_v19',
    ROOT / 'data' / 'Code_RED_MP_Companion_v19',
    ROOT / 'Code_RED_MP_Companion_v19',
)


def _ensure_runtime_folders() -> None:
    for folder in RUNTIME_FOLDERS:
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
    del exc  # traceback.format_exc() reads the active exception.
    _ensure_runtime_folders()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = LOGS_DIR / f'code_red_main_crash_{stamp}.log'
    path.write_text('Code RED main crash\n\n' + traceback.format_exc(), encoding='utf-8')
    return path


def _detect_companion_workspace() -> Path | None:
    return next((candidate for candidate in COMPANION_WORKSPACE_CANDIDATES if candidate.exists()), None)


def _resolve_workspace(raw_workspace: str | None, use_companion_workspace: bool) -> Path:
    if raw_workspace:
        path = Path(raw_workspace)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f'Workspace does not exist: {path}')
        return path
    if use_companion_workspace:
        companion = _detect_companion_workspace()
        if companion is not None:
            return companion
    return ROOT


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Launch the Code RED workbench.')
    parser.add_argument(
        '--workspace',
        help='Optional startup workspace. Relative paths are resolved from the Code RED root.',
    )
    parser.add_argument(
        '--legacy-companion-workspace',
        action='store_true',
        help='Compatibility mode for the old run_workbench.py behavior: start inside MP Companion if present.',
    )
    parser.add_argument(
        '--title',
        default='Code RED',
        help='Window title. Defaults to the canonical Code RED title.',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Resolve startup paths and exit without opening the Tk workbench. Useful for launch tests.',
    )
    parser.add_argument(
        '--one-app-status',
        action='store_true',
        help='Print the one-app lane registry/status report and exit.',
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        _ensure_runtime_folders()
        workspace = _resolve_workspace(args.workspace, args.legacy_companion_workspace)
        workbench_path = ROOT / 'python_workbench.py'
        if not workbench_path.exists():
            raise FileNotFoundError(f'Missing workbench: {workbench_path}')
        if args.dry_run:
            print(f'Code RED root: {ROOT}')
            print(f'Workbench: {workbench_path}')
            print(f'Startup workspace: {workspace}')
            print(f'Window title: {args.title}')
            companion = _detect_companion_workspace()
            print(f'MP Companion workspace: {companion if companion else "not found"}')
            return 0
        if args.one_app_status:
            from codered_app.launcher_registry import build_status_report, report_to_markdown
            print(report_to_markdown(build_status_report(ROOT)))
            return 0
        wb = _load_module('codered_workbench', workbench_path)
        app = wb.WorkbenchApp(startup_workspace=workspace)
        app.title(args.title)
        app.mainloop()
        return 0
    except Exception as exc:
        crash_path = _write_crash_log(exc)
        print(f'Code RED crash log written to {crash_path}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
