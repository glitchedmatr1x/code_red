#!/usr/bin/env python3
"""Code RED SC-CL build finalizer.

Run this after building SC-CL from CMake/Visual Studio or after placing a
prebuilt SC-CL.exe somewhere in the Code RED tree.

It makes the last stage simple:
- find SC-CL.exe in known source/build/drop folders
- copy/adopt it into the Code RED Windows build kit
- mirror it into resources/SC-CL_DROP_HERE
- run the compiler setup validator
- optionally run the vehicle menu compile helper
- write proof reports

It does not install scripts into the game and it does not promote compiled
outputs into archives.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-sccl-finalize-build"
KIT = Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1")
DROP = Path("resources/SC-CL_DROP_HERE")
BITBUCKET_SOURCE = Path("resources/SC-CL_bitbucket_source")
LOCAL_SOURCE = Path("SC-CL-master")
REPORT_JSON = Path("logs/CodeRED_SCCL_Finalize_Build_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Finalize_Build_Report.md")
PASS_LOG = Path("logs/CodeRED_SCCL_Finalize_Build_Lane_Pass_2026-05-03.md")
VALIDATOR_OUTPUT = Path("logs/CodeRED_SCCL_Finalize_Validator_Output.txt")
COMPILE_HELPER_OUTPUT = Path("logs/CodeRED_SCCL_Finalize_Compile_Helper_Output.txt")


@dataclass
class FinalizeReport:
    version: str
    generated_utc: str
    root: str
    ok: bool
    sccl_exe: str | None = None
    adopted_to: str | None = None
    mirrored_to: str | None = None
    validator_exit: int | None = None
    compile_helper_exit: int | None = None
    searched_paths: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def root_from_arg(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else Path(__file__).resolve().parents[1]


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="ignore")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def preferred_exe_paths(root: Path, explicit: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("SCCL_EXE")
    if explicit:
        paths.append(explicit)
    if env:
        paths.append(Path(env))
    for base in [root / BITBUCKET_SOURCE, root / LOCAL_SOURCE, root / DROP, root / KIT, root]:
        paths.extend([
            base / "SC-CL.exe",
            base / "sc-cl.exe",
            base / "sccl.exe",
            base / "bin" / "SC-CL.exe",
            base / "Release" / "SC-CL.exe",
            base / "x64" / "Release" / "SC-CL.exe",
            base / "build" / "Release" / "SC-CL.exe",
            base / "build" / "bin" / "Release" / "SC-CL.exe",
            base / "codered_build" / "Release" / "SC-CL.exe",
            base / "codered_build" / "bin" / "Release" / "SC-CL.exe",
            base / "codered_llvm_build" / "Release" / "bin" / "SC-CL.exe",
            base / "codered_llvm_build" / "bin" / "Release" / "SC-CL.exe",
            base / "llvm-14.0.0.src" / "MinSizeRel" / "bin" / "SC-CL.exe",
        ])
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def fallback_recursive_search(root: Path) -> Path | None:
    search_roots = [root / BITBUCKET_SOURCE, root / LOCAL_SOURCE, root / DROP, root / KIT]
    names = {"sc-cl.exe", "sccl.exe", "sc_cl.exe"}
    for base in search_roots:
        if not base.exists():
            continue
        for path in base.rglob("*.exe"):
            if path.name.lower() in names:
                return path
    return None


def find_exe(root: Path, explicit: Path | None, report: FinalizeReport) -> Path | None:
    for path in preferred_exe_paths(root, explicit):
        report.searched_paths.append(str(path))
        if path.exists():
            return path
    found = fallback_recursive_search(root)
    if found:
        report.searched_paths.append(str(found))
    return found


def copy_exe(root: Path, source: Path, report: FinalizeReport) -> None:
    target = root / KIT / "SC-CL.exe"
    mirror = root / DROP / "SC-CL.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
        report.actions.append(f"Copied SC-CL.exe into build kit: {rel(target, root)}")
    else:
        report.actions.append(f"SC-CL.exe already in build kit: {rel(target, root)}")
    if target.resolve() != mirror.resolve():
        shutil.copy2(target, mirror)
        report.actions.append(f"Mirrored SC-CL.exe into drop folder: {rel(mirror, root)}")
    report.adopted_to = rel(target, root)
    report.mirrored_to = rel(mirror, root)


def run_command(root: Path, command: list[str], output_path: Path, timeout: int = 900) -> int:
    proc = subprocess.run(command, cwd=str(root), capture_output=True, text=True, timeout=timeout, check=False)
    write_text(root / output_path, proc.stdout + "\n" + proc.stderr)
    return proc.returncode


def finalize(root: Path, explicit: Path | None, run_validator: bool, run_compile_helper: bool) -> FinalizeReport:
    root = root.resolve()
    report = FinalizeReport(version=VERSION, generated_utc=utc_now(), root=str(root), ok=False)
    exe = find_exe(root, explicit, report)
    if not exe:
        report.warnings.append("No SC-CL.exe was found. Build it first or place it in resources/SC-CL_DROP_HERE/SC-CL.exe.")
        report.next_steps = [
            "Build SC-CL in Visual Studio/CMake, then rerun this finalizer.",
            "Or copy a prebuilt SC-CL.exe to resources\\SC-CL_DROP_HERE\\SC-CL.exe and rerun this finalizer.",
            "Command: py -3 tools\\codered_sccl_finalize_build.py --validate",
        ]
        write_outputs(root, report)
        return report

    report.sccl_exe = str(exe)
    copy_exe(root, exe, report)

    if run_validator:
        validator = root / "tools" / "codered_script_compile_validation.py"
        if validator.exists():
            report.validator_exit = run_command(root, [sys.executable, str(validator)], VALIDATOR_OUTPUT)
            report.actions.append(f"Script compile validator exit: {report.validator_exit}")
        else:
            report.warnings.append(f"Missing validator: {validator}")

    if run_compile_helper:
        helper = root / KIT / "run_build_then_compile_vehicle_menu_probe.bat"
        if helper.exists():
            if sys.platform.startswith("win"):
                report.compile_helper_exit = run_command(root, ["cmd", "/c", str(helper)], COMPILE_HELPER_OUTPUT, timeout=1200)
                report.actions.append(f"Vehicle menu compile helper exit: {report.compile_helper_exit}")
            else:
                report.warnings.append("Compile helper is a Windows .bat; run it on Windows for final proof.")
        else:
            report.warnings.append(f"Missing compile helper: {helper}")

    validation_ok = report.validator_exit in (None, 0)
    compile_ok = report.compile_helper_exit in (None, 0)
    report.ok = bool(report.sccl_exe and report.adopted_to and validation_ok and compile_ok)
    report.next_steps = [
        "Run: py -3 tools\\codered_sccl_easy_setup.py status --run-validator",
        "Run: related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat",
        "If the compile helper passes, move to controlled compiled-output verification; do not auto-promote into archives yet.",
    ]
    write_outputs(root, report)
    return report


def markdown(report: FinalizeReport) -> str:
    lines = [
        "# Code RED SC-CL Finalize Build Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Result: **{'PASS' if report.ok else 'NEEDS ATTENTION'}**",
        f"SC-CL.exe found: `{report.sccl_exe}`",
        f"Adopted to: `{report.adopted_to}`",
        f"Mirrored to: `{report.mirrored_to}`",
        f"Validator exit: `{report.validator_exit}`",
        f"Compile helper exit: `{report.compile_helper_exit}`",
        "",
        "## Actions",
        "",
    ]
    lines.extend(f"- {a}" for a in report.actions or ["No actions completed."])
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in report.warnings)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {s}" for s in report.next_steps)
    lines.extend(["", "## Searched Paths", ""])
    lines.extend(f"- `{p}`" for p in report.searched_paths[:200])
    if len(report.searched_paths) > 200:
        lines.append(f"- ... {len(report.searched_paths) - 200} more")
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, report: FinalizeReport) -> None:
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, markdown(report))
    write_text(root / PASS_LOG,
        "# Code RED SC-CL Finalize Build Lane Pass\n\n"
        "Added a single finalizer that finds/adopts SC-CL.exe, runs validation, and records proof.\n\n"
        f"Report: `{REPORT_MD.as_posix()}`\n",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Find/adopt a built SC-CL.exe and run proof checks.")
    p.add_argument("--root", default=None)
    p.add_argument("--sccl", default=None, help="Explicit path to SC-CL.exe if known")
    p.add_argument("--validate", action="store_true", help="Run codered_script_compile_validation.py after adoption")
    p.add_argument("--compile-helper", action="store_true", help="Also run the vehicle menu compile helper batch file")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = root_from_arg(args.root)
    explicit = Path(args.sccl).resolve() if args.sccl else None
    report = finalize(root, explicit, run_validator=args.validate, run_compile_helper=args.compile_helper)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
