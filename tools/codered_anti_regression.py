#!/usr/bin/env python3
"""Code RED anti-regression checks for the stable launcher and full backend.

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
FULL_WORKBENCH_PATH = REPO_ROOT / "python_workbench.py"
FULL_BACKEND_HARNESS_PATH = REPO_ROOT / "tools" / "codered_full_backend_rpf6_harness.py"
SCRIPT_WORKSHOP_PATH = REPO_ROOT / "tools" / "codered_script_workshop.py"
DECOMPILE_ATTEMPT_PATH = REPO_ROOT / "tools" / "codered_script_decompile_attempt.py"
RPF_DEEP_PROBE_PATH = REPO_ROOT / "tools" / "codered_rpf_deep_probe.py"
FREEMODE_INIT_INSPECTOR_PATH = REPO_ROOT / "tools" / "codered_freemode_init_inspector.py"

SCRIPT_LANE_EXTENSIONS = (".wsc", ".xsc", ".sco", ".wsv")
ARCHIVE_LANE_EXTENSIONS = (".rpf", ".zip", ".z01")

FULL_BACKEND_REQUIRED_SYMBOLS = {
    "audit_rpf6_archive": "RPF6 audit / inventory backend",
    "_codered_run_archive_proof_pass": "copied archive proof pass",
    "_codered_build_stage_report": "readiness and lane status report",
    "_codered_build_completion_report": "completion planner report",
    "_codered_build_script_toolchain_pack": "Magic-RDR / SC-CL script toolchain pack export",
    "_codered_detect_script_resource_tooling": "script compiler / Magic-RDR tooling detection",
    "_codered_analyze_source_text": "source/code reading and validation lane",
    "_codered_apply_patch_folder_to_archive_copy": "safe copied-archive patch application",
}

REQUIRED_TOOL_FILES = {
    FULL_BACKEND_HARNESS_PATH: "full backend RPF6 extraction harness",
    SCRIPT_WORKSHOP_PATH: "compiler-aware Script Workshop",
    DECOMPILE_ATTEMPT_PATH: "script decompile attempt workflow",
    RPF_DEEP_PROBE_PATH: "RPF deep probe",
    FREEMODE_INIT_INSPECTOR_PATH: "Freemode / Init inspector",
}


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(REPO_ROOT), text=True, capture_output=True, check=False)


def _check_help(path: Path, failures: list[str]) -> None:
    result = _run_command([sys.executable, str(path), "--help"])
    if result.returncode != 0:
        failures.append(f"{path.name} --help failed: {result.stderr or result.stdout}")


def _write_fake_freemode_harness(temp: Path) -> Path:
    harness = temp / "fake_freemode_harness"
    harness.mkdir(parents=True, exist_ok=True)
    (harness / "full_backend_rpf6_harness_summary.json").write_text(
        json.dumps(
            {
                "backend_ok": True,
                "decrypt_extract_status": "confirmed_non_z_init_scripts_extracted",
                "non_z_init_extracted_script_count": 1,
                "notes": "mp_network session host lobby init smoke test",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (harness / "full_backend_rpf6_harness_selected_hits.json").write_text(
        json.dumps(
            [
                {
                    "value": "scripts/init_session.sco",
                    "category": "init_script_entry",
                    "raw_preview": "network session host client spawn",
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    return harness


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    if not MAIN_PATH.exists():
        failures.append("code_red_main.py is missing")
    if not RUNNER_PATH.exists():
        failures.append("run_workbench.py is missing")
    if not FULL_WORKBENCH_PATH.exists():
        failures.append("python_workbench.py full backend is missing")
    for path, label in REQUIRED_TOOL_FILES.items():
        if not path.exists():
            failures.append(f"Missing {label}: {path}")
    if failures:
        print(json.dumps({"ok": False, "failures": failures}, indent=2))
        return 1

    module = _load_module(MAIN_PATH, "code_red_main")
    full_backend = _load_module(FULL_WORKBENCH_PATH, "python_workbench")
    _load_module(FULL_BACKEND_HARNESS_PATH, "codered_full_backend_rpf6_harness")
    _load_module(SCRIPT_WORKSHOP_PATH, "codered_script_workshop")
    _load_module(DECOMPILE_ATTEMPT_PATH, "codered_script_decompile_attempt")
    _load_module(RPF_DEEP_PROBE_PATH, "codered_rpf_deep_probe")
    _load_module(FREEMODE_INIT_INSPECTOR_PATH, "codered_freemode_init_inspector")

    for name, label in FULL_BACKEND_REQUIRED_SYMBOLS.items():
        if not hasattr(full_backend, name):
            failures.append(f"Full backend missing {name}: {label}")

    if hasattr(full_backend, "_codered_build_stage_report"):
        try:
            stage_report = full_backend._codered_build_stage_report(REPO_ROOT)
            text = str(stage_report.get("text", "")) if isinstance(stage_report, dict) else ""
            required_phrases = ["Archive inventory/export", "Script compile-back", "Magic-RDR", "SC-CL"]
            for phrase in required_phrases:
                if phrase not in text:
                    warnings.append(f"Stage report did not mention expected lane/tooling phrase: {phrase}")
        except Exception as exc:
            failures.append(f"Full backend stage report failed: {exc}")

    for ext in SCRIPT_LANE_EXTENSIONS:
        lane = module.classify_extension(f"guard{ext}")
        if lane != "Scripts":
            failures.append(f"{ext} routed to {lane}, expected Scripts")

    for ext in ARCHIVE_LANE_EXTENSIONS:
        lane = module.classify_extension(f"guard{ext}")
        if lane != "Archives":
            failures.append(f"{ext} routed to {lane}, expected Archives")

    self_test = _run_command([sys.executable, "code_red_main.py", "--self-test"])
    if self_test.returncode != 0:
        failures.append(f"--self-test failed: {self_test.stderr or self_test.stdout}")

    for tool in (FULL_BACKEND_HARNESS_PATH, SCRIPT_WORKSHOP_PATH, DECOMPILE_ATTEMPT_PATH, RPF_DEEP_PROBE_PATH, FREEMODE_INIT_INSPECTOR_PATH):
        _check_help(tool, failures)

    with tempfile.TemporaryDirectory(prefix="codered_guard_") as temp_dir:
        temp = Path(temp_dir)
        fake_rpf = temp / "content.rpf"
        fake_rpf.write_bytes(
            b"RPF6" + b"\0" * 64 +
            b"scripts/test_guard.wsc\0" +
            b"scripts/test_guard.xsc\0" +
            b"scripts/test_guard.sco\0" +
            b"scripts/test_guard.wsv\0" +
            b"textures/test_guard.wtd\0" +
            b"textures/test_guard.wtx\0" +
            b"meshes/test_guard.wft\0" +
            b"meshes/test_guard.wvd\0" +
            b"strings/test_guard.strtbl\0" +
            b"audio/test_guard.awc\0" +
            b"world/test_guard.wpl\0" +
            b"world/test_guard.dat\0"
        )
        rpf_records = module.scan_archive_members(fake_rpf)
        expected_rpf_members = {
            ".wsc": "Scripts",
            ".xsc": "Scripts",
            ".sco": "Scripts",
            ".wsv": "Scripts",
            ".wtd": "Textures",
            ".wtx": "Textures",
            ".wft": "Meshes",
            ".wvd": "Meshes",
            ".strtbl": "Strings",
            ".awc": "Audio",
            ".wpl": "World",
            ".dat": "World",
        }
        for ext, lane in expected_rpf_members.items():
            if not any(rec.source == "rpf" and rec.extension == ext and rec.lane == lane for rec in rpf_records):
                failures.append(f"RPF scan did not preserve {ext} in {lane} lane")

        fake_zip = temp / "package.zip"
        with zipfile.ZipFile(fake_zip, "w") as zf:
            zf.writestr("scripts/from_zip.wsc", "// package sample")
            zf.writestr("scripts/from_zip.wsv", b"wsv sample")
            zf.writestr("textures/from_zip.wtd", b"texture sample")
        zip_records = module.scan_archive_members(fake_zip)
        if not any(rec.source == "zip" and rec.extension == ".wsc" and rec.lane == "Scripts" for rec in zip_records):
            failures.append("ZIP package scan did not preserve .wsc in Scripts lane")
        if not any(rec.source == "zip" and rec.extension == ".wsv" and rec.lane == "Scripts" for rec in zip_records):
            failures.append("ZIP package scan did not preserve .wsv in Scripts lane")
        if not any(rec.source == "zip" and rec.extension == ".wtd" and rec.lane == "Textures" for rec in zip_records):
            failures.append("ZIP package scan did not preserve .wtd in Textures lane")

        cli_scan = _run_command([sys.executable, "code_red_main.py", "--scan-archive", str(fake_rpf)])
        if cli_scan.returncode != 0:
            failures.append(f"--scan-archive failed on synthetic RPF: {cli_scan.stderr or cli_scan.stdout}")
        elif "test_guard.wsc" not in cli_scan.stdout or "test_guard.wsv" not in cli_scan.stdout or "test_guard.wtd" not in cli_scan.stdout:
            failures.append("--scan-archive output did not include synthetic RPF script/WSV/texture members")

        fake_harness = _write_fake_freemode_harness(temp)
        freemode_out = temp / "freemode_smoke_out"
        freemode_smoke = _run_command([
            sys.executable,
            str(FREEMODE_INIT_INSPECTOR_PATH),
            "--harness",
            str(fake_harness),
            "--out",
            str(freemode_out),
        ])
        if freemode_smoke.returncode != 0:
            failures.append(f"Freemode inspector smoke failed: {freemode_smoke.stderr or freemode_smoke.stdout}")
        else:
            try:
                summary = json.loads((freemode_out / "freemode_init_inspector_summary.json").read_text(encoding="utf-8"))
                if summary.get("mp_network_count", 0) < 1:
                    failures.append("Freemode inspector smoke did not detect MP/network signal")
            except Exception as exc:
                failures.append(f"Freemode inspector smoke summary unreadable: {exc}")

    result = {
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "full_backend_required_symbols": FULL_BACKEND_REQUIRED_SYMBOLS,
        "checked": [
            "run_workbench.py exists",
            "code_red_main.py imports",
            "python_workbench.py full backend imports",
            "full backend RPF6/archive/script/source symbols exist",
            "full backend harness imports and exposes --help",
            "Script Workshop imports and exposes --help",
            "script decompile attempt imports and exposes --help",
            "RPF deep probe imports and exposes --help",
            "Freemode Init Inspector imports and exposes --help",
            "Freemode Init Inspector detects synthetic MP/session/init harness output",
            "script lane guard including .wsv",
            "archive lane guard",
            "headless self-test",
            "synthetic RPF inventory across scripts/WSV/textures/meshes/strings/audio/world",
            "synthetic ZIP package inventory including WSV",
            "headless --scan-archive",
        ],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
