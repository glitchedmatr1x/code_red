#!/usr/bin/env python3
"""Code RED anti-regression checks for the stable launcher.

Run from the repository root:

    python tools/codered_anti_regression.py

This test intentionally uses tiny synthetic files. It does not require or ship
real game archives, and it does not compile or mutate scripts.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = REPO_ROOT / "code_red_main.py"
RUNNER_PATH = REPO_ROOT / "run_workbench.py"


def _load_main_module():
    spec = importlib.util.spec_from_file_location("code_red_main", MAIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {MAIN_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(REPO_ROOT), text=True, capture_output=True, check=False)


def main() -> int:
    failures: list[str] = []
    if not MAIN_PATH.exists():
        failures.append("code_red_main.py is missing")
    if not RUNNER_PATH.exists():
        failures.append("run_workbench.py is missing")
    if failures:
        print(json.dumps({"ok": False, "failures": failures}, indent=2))
        return 1

    module = _load_main_module()

    for ext in (".wsc", ".xsc", ".sco"):
        lane = module.classify_extension(f"guard{ext}")
        if lane != "Scripts":
            failures.append(f"{ext} routed to {lane}, expected Scripts")

    for ext in (".rpf", ".zip", ".z01"):
        lane = module.classify_extension(f"guard{ext}")
        if lane != "Archives":
            failures.append(f"{ext} routed to {lane}, expected Archives")

    self_test = _run_command([sys.executable, "code_red_main.py", "--self-test"])
    if self_test.returncode != 0:
        failures.append(f"--self-test failed: {self_test.stderr or self_test.stdout}")

    with tempfile.TemporaryDirectory(prefix="codered_guard_") as temp_dir:
        temp = Path(temp_dir)
        fake_rpf = temp / "content.rpf"
        fake_rpf.write_bytes(
            b"RPF6" + b"\0" * 64 +
            b"scripts/test_guard.wsc\0" +
            b"textures/test_guard.wtd\0" +
            b"world/test_guard.wpl\0"
        )
        rpf_records = module.scan_archive_members(fake_rpf)
        if not any(rec.source == "rpf" and rec.extension == ".wsc" and rec.lane == "Scripts" for rec in rpf_records):
            failures.append("RPF scan did not preserve .wsc in Scripts lane")
        if not any(rec.source == "rpf" and rec.extension == ".wtd" and rec.lane == "Textures" for rec in rpf_records):
            failures.append("RPF scan did not preserve .wtd in Textures lane")

        fake_zip = temp / "package.zip"
        with zipfile.ZipFile(fake_zip, "w") as zf:
            zf.writestr("scripts/from_zip.wsc", "// package sample")
        zip_records = module.scan_archive_members(fake_zip)
        if not any(rec.source == "zip" and rec.extension == ".wsc" and rec.lane == "Scripts" for rec in zip_records):
            failures.append("ZIP package scan did not preserve .wsc in Scripts lane")

        cli_scan = _run_command([sys.executable, "code_red_main.py", "--scan-archive", str(fake_rpf)])
        if cli_scan.returncode != 0:
            failures.append(f"--scan-archive failed on synthetic RPF: {cli_scan.stderr or cli_scan.stdout}")
        elif "test_guard.wsc" not in cli_scan.stdout:
            failures.append("--scan-archive output did not include synthetic RPF script member")

    result = {
        "ok": not failures,
        "failures": failures,
        "checked": [
            "run_workbench.py exists",
            "code_red_main.py imports",
            "script lane guard",
            "archive lane guard",
            "headless self-test",
            "synthetic RPF inventory",
            "synthetic ZIP package inventory",
            "headless --scan-archive",
        ],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
