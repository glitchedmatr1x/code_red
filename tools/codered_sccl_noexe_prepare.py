#!/usr/bin/env python3
"""Prepare Code RED for the SC-CL compiler when SC-CL.exe is not available yet.

This is the no-exe path:
- create a clear compiler drop folder
- create Windows/Linux checklist files
- verify the Script Workshop and compile-lab source proof files exist
- write a proof report that says exactly what is done and what remains blocked

It does not download SC-CL and does not claim binary script roundtrip.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-sccl-noexe-prepare"
KIT = Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1")
LAB = Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1")
DROP = Path("resources/SC-CL_DROP_HERE")
REPORT_JSON = Path("logs/CodeRED_SCCL_NoExe_Prepare_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_NoExe_Prepare_Report.md")
PASS_LOG = Path("logs/CodeRED_SCCL_NoExe_Prepare_Lane_Pass_2026-05-03.md")

REQUIRED_PRE_COMPILER_FILES = [
    "related_apps/CodeRED_Script_Workshop/CodeRED_Script_Workshop.py",
    "tools/codered_sccl_easy_setup.py",
    "tools/codered_script_compile_validation.py",
    "related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/src/main.c",
    "related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/include/RDR/natives32.h",
    "related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/include/RDR/consts32.h",
    "related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/scripts/validate_vehicle_menu_probe.py",
    "related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/run_build_then_compile_vehicle_menu_probe.bat",
]


@dataclass
class NoExeReport:
    version: str
    generated_utc: str
    root: str
    ok: bool
    sccl_found: bool
    drop_folder: str
    missing_precompiler_files: list[str] = field(default_factory=list)
    generated_files: list[str] = field(default_factory=list)
    detected_tools: dict[str, str | None] = field(default_factory=dict)
    next_steps: list[str] = field(default_factory=list)
    blocked_until_sccl: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def find_sccl(root: Path) -> Path | None:
    candidates = [
        root / "SC-CL.exe",
        root / "resources/SC-CL.exe",
        root / "resources/SC-CL/SC-CL.exe",
        root / "resources/SC-CL_DROP_HERE/SC-CL.exe",
        root / "related_apps/code_red_sccl_attempt_bundle_v1/SC-CL.exe",
        root / "related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/SC-CL.exe",
        root / "related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/SC-CL.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_files(root: Path, drop: Path) -> list[str]:
    generated: list[str] = []
    drop.mkdir(parents=True, exist_ok=True)
    readme = drop / "README_DROP_SC_CL_EXE_HERE.txt"
    write_text(readme,
        "Code RED SC-CL Compiler Drop Folder\n"
        "===================================\n\n"
        "Put SC-CL.exe in this folder when you have it:\n\n"
        "  resources\\SC-CL_DROP_HERE\\SC-CL.exe\n\n"
        "Then run from the Code RED root:\n\n"
        "  py -3 tools\\codered_sccl_easy_setup.py status --run-validator\n"
        "  py -3 tools\\codered_sccl_easy_setup.py adopt --sccl resources\\SC-CL_DROP_HERE\\SC-CL.exe --run-validator\n"
        "  related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat\n\n"
        "Until SC-CL.exe exists, Code RED can prove scan/read/edit/import/recompile queues, but cannot prove compiled binary output.\n",
    )
    generated.append(rel(readme, root))
    checklist = root / "logs/CodeRED_SCCL_NoExe_Checklist.txt"
    write_text(checklist,
        "Code RED SC-CL No-Exe Checklist\n"
        "================================\n\n"
        "Current allowed proofs without SC-CL.exe:\n"
        "[x] Script Workshop self-test\n"
        "[x] Source/validator proof\n"
        "[x] Import/recompile queue prep\n"
        "[x] Windows helper generation\n"
        "[ ] SC-CL.exe staged\n"
        "[ ] Vehicle menu probe compiled\n"
        "[ ] Compiled output verified\n"
        "[ ] Binary script roundtrip proven\n\n"
        "Commands after SC-CL.exe is obtained:\n"
        "py -3 tools\\codered_sccl_easy_setup.py adopt --sccl resources\\SC-CL_DROP_HERE\\SC-CL.exe --run-validator\n"
        "related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat\n",
    )
    generated.append(rel(checklist, root))
    bat = root / "Run_CodeRED_SCCL_NoExe_Prepare.bat"
    write_text(bat,
        "@echo off\n"
        "setlocal\n"
        "cd /d \"%~dp0\"\n"
        "py -3 tools\\codered_sccl_noexe_prepare.py\n"
        "pause\n"
        "endlocal\n",
    )
    generated.append(rel(bat, root))
    return generated


def prepare(root: Path) -> NoExeReport:
    root = root.resolve()
    sccl = find_sccl(root)
    drop = root / DROP
    generated = build_files(root, drop)
    missing = [item for item in REQUIRED_PRE_COMPILER_FILES if not (root / item).exists()]
    detected = {
        "python": sys.executable,
        "sccl_exe": str(sccl) if sccl else None,
        "cl_exe": shutil.which("cl"),
        "msbuild": shutil.which("MSBuild.exe") or shutil.which("msbuild"),
    }
    report = NoExeReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        ok=not missing,
        sccl_found=sccl is not None,
        drop_folder=rel(drop, root),
        missing_precompiler_files=missing,
        generated_files=generated,
        detected_tools=detected,
        next_steps=[
            "Place SC-CL.exe in resources\\SC-CL_DROP_HERE when available.",
            "Run: py -3 tools\\codered_sccl_easy_setup.py adopt --sccl resources\\SC-CL_DROP_HERE\\SC-CL.exe --run-validator",
            "Run: related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat",
        ],
        blocked_until_sccl=[
            "actual source-to-compiled-script proof",
            "vehicle_menu_probe compiled output verification",
            "compiled .wsc/.xsc/.sco bytecode roundtrip",
            "automatic compiled-output promotion",
        ],
    )
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, markdown(report))
    write_text(root / PASS_LOG,
        "# Code RED SC-CL No-Exe Prepare Lane Pass\n\n"
        "Prepared the compiler-missing path with a drop folder, checklist, and proof report.\n\n"
        f"Report: `{REPORT_MD.as_posix()}`\n",
    )
    return report


def markdown(report: NoExeReport) -> str:
    lines = [
        "# Code RED SC-CL No-Exe Prepare Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Pre-compiler readiness: **{'PASS' if report.ok else 'MISSING FILES'}**",
        f"SC-CL found: `{report.sccl_found}`",
        f"Drop folder: `{report.drop_folder}`",
        "",
        "## Detected Tools",
        "",
    ]
    for key, value in report.detected_tools.items():
        lines.append(f"- {key}: `{value}`")
    if report.missing_precompiler_files:
        lines.extend(["", "## Missing Pre-Compiler Files", ""])
        lines.extend(f"- `{item}`" for item in report.missing_precompiler_files)
    lines.extend(["", "## Generated Files", ""])
    lines.extend(f"- `{item}`" for item in report.generated_files)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {item}" for item in report.next_steps)
    lines.extend(["", "## Blocked Until SC-CL.exe", ""])
    lines.extend(f"- {item}" for item in report.blocked_until_sccl)
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare the Code RED SC-CL stage when SC-CL.exe is not available yet.")
    parser.add_argument("--root", default=None)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    report = prepare(root)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
