#!/usr/bin/env python3
"""Patch-folder apply wrapper for copied RPF archives.

This delegates to the already proven ``python_workbench.py`` archive patch
backend. It never edits the source archive in place.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"


def load_backend():
    spec = importlib.util.spec_from_file_location("codered_workbench_backend_patch", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def apply_patch_folder(archive: Path, patch_root: Path, output_archive: Path | None = None) -> dict:
    wb = load_backend()
    if not hasattr(wb, "_codered_apply_patch_folder_to_archive_copy"):
        raise RuntimeError("python_workbench.py does not expose the copied-archive patch backend")
    return wb._codered_apply_patch_folder_to_archive_copy(archive, patch_root, output_archive=output_archive)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply a patch folder to a copied RPF archive")
    parser.add_argument("--archive", required=True, help="Source RPF archive. It is copied first.")
    parser.add_argument("--patch-root", required=True, help="Folder containing replacement files by internal path.")
    parser.add_argument("--out", default="", help="Optional output archive path.")
    args = parser.parse_args(argv)
    result = apply_patch_folder(
        Path(args.archive),
        Path(args.patch_root),
        output_archive=Path(args.out) if args.out else None,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
