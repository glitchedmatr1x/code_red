#!/usr/bin/env python3
"""Code RED SC-CL Bitbucket setup helper.

The public GTAResources/SC-CL mirror README points to the original source:
https://bitbucket.org/scclteam/sc-cl

Use this helper when the local SC-CL-master folder is only a partial/tool source
or contains stale generated LLVM.sln/CMake paths. It prepares a clean source
folder, gives exact git clone commands, and can run the existing Code RED
build/adopt helper after the source is staged.

This helper does not download anything itself unless --clone is supplied and git
is available on the user's machine.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-sccl-bitbucket-setup"
BITBUCKET_URL = "https://bitbucket.org/scclteam/sc-cl.git"
TARGET_DIR = Path("resources/SC-CL_bitbucket_source")
REPORT_JSON = Path("logs/CodeRED_SCCL_Bitbucket_Setup_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Bitbucket_Setup_Report.md")
PASS_LOG = Path("logs/CodeRED_SCCL_Bitbucket_Setup_Lane_Pass_2026-05-03.md")


@dataclass
class BitbucketReport:
    version: str
    generated_utc: str
    root: str
    bitbucket_url: str
    target_dir: str
    ok: bool
    git_exe: str | None
    cloned: bool = False
    source_exists: bool = False
    llvm_source_root: str | None = None
    sccl_exe: str | None = None
    build_exit_code: int | None = None
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


def find_sccl_exe(source: Path) -> Path | None:
    if not source.exists():
        return None
    preferred = [
        source / "SC-CL.exe",
        source / "bin" / "SC-CL.exe",
        source / "Release" / "SC-CL.exe",
        source / "x64" / "Release" / "SC-CL.exe",
        source / "codered_llvm_build" / "Release" / "bin" / "SC-CL.exe",
        source / "codered_llvm_build" / "bin" / "Release" / "SC-CL.exe",
        source / "llvm-14.0.0.src" / "MinSizeRel" / "bin" / "SC-CL.exe",
    ]
    for path in preferred:
        if path.exists():
            return path
    for path in source.rglob("SC-CL.exe"):
        return path
    return None


def maybe_clone(target: Path, git_exe: str | None, report: BitbucketReport, force: bool) -> None:
    if target.exists() and any(target.iterdir()) and not force:
        report.actions.append(f"Source folder already exists: {target}")
        return
    if force and target.exists():
        shutil.rmtree(target)
        report.actions.append(f"Removed existing source folder for clean clone: {target}")
    if not git_exe:
        report.warnings.append("git was not found in PATH, so Code RED cannot clone the Bitbucket source automatically.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([git_exe, "clone", BITBUCKET_URL, str(target)], capture_output=True, text=True, check=False)
    report.actions.append(f"git clone exit: {proc.returncode}")
    if proc.returncode == 0:
        report.cloned = True
    else:
        report.warnings.append("git clone failed. See logs/CodeRED_SCCL_Bitbucket_Git_Output.txt")
        write_text(Path(report.root) / "logs" / "CodeRED_SCCL_Bitbucket_Git_Output.txt", proc.stdout + "\n" + proc.stderr)


def run_build_helper(root: Path, target: Path, report: BitbucketReport, adopt: bool) -> None:
    helper = root / "tools" / "codered_sccl_build_from_source.py"
    if not helper.exists():
        report.warnings.append(f"Missing build helper: {helper}")
        return
    args = [sys.executable, str(helper), "--source", str(target)]
    if adopt:
        args.append("--adopt")
    proc = subprocess.run(args, cwd=str(root), capture_output=True, text=True, check=False, timeout=3600)
    report.build_exit_code = proc.returncode
    write_text(root / "logs" / "CodeRED_SCCL_Bitbucket_Build_Output.txt", proc.stdout + "\n" + proc.stderr)
    report.actions.append(f"build helper exit: {proc.returncode}")


def prepare(root: Path, target: Path, clone: bool, force: bool, build: bool, adopt: bool) -> BitbucketReport:
    root = root.resolve()
    target = target.resolve()
    git_exe = shutil.which("git")
    report = BitbucketReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        bitbucket_url=BITBUCKET_URL,
        target_dir=str(target),
        ok=False,
        git_exe=git_exe,
    )
    if clone:
        maybe_clone(target, git_exe, report, force)
    report.source_exists = target.exists()
    llvm_root = target / "llvm-14.0.0.src" / "CMakeLists.txt"
    if llvm_root.exists():
        report.llvm_source_root = str(llvm_root.parent)
    exe = find_sccl_exe(target)
    if exe:
        report.sccl_exe = str(exe)
        report.ok = True
    if build and target.exists():
        run_build_helper(root, target, report, adopt=adopt)
        exe = find_sccl_exe(target)
        if exe:
            report.sccl_exe = str(exe)
            report.ok = True
    if not target.exists():
        report.warnings.append("Bitbucket source folder is not staged yet.")
    if target.exists() and not report.llvm_source_root:
        report.warnings.append("Source is staged, but llvm-14.0.0.src/CMakeLists.txt was not found. If build still fails, this may still be an incomplete source package.")
    if not report.sccl_exe:
        report.warnings.append("SC-CL.exe is not available yet. Build or obtain it before compile-output proof.")
    report.next_steps = [
        f"Clone manually if needed: git clone {BITBUCKET_URL} {rel(target, root)}",
        f"Probe/build: py -3 tools\\codered_sccl_build_from_source.py --source \"{target}\" --adopt",
        "If SC-CL.exe is produced, run: py -3 tools\\codered_sccl_easy_setup.py status --run-validator",
        "Then run: related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat",
    ]
    write_outputs(root, report)
    return report


def markdown(report: BitbucketReport) -> str:
    lines = [
        "# Code RED SC-CL Bitbucket Setup Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Result: **{'READY' if report.ok else 'NEEDS BUILD'}**",
        f"Bitbucket source: `{report.bitbucket_url}`",
        f"Target dir: `{report.target_dir}`",
        f"git: `{report.git_exe}`",
        f"source_exists: `{report.source_exists}`",
        f"llvm_source_root: `{report.llvm_source_root}`",
        f"SC-CL.exe: `{report.sccl_exe}`",
        f"build_exit_code: `{report.build_exit_code}`",
        "",
        "## Actions",
        "",
    ]
    lines.extend(f"- {a}" for a in report.actions or ["No actions run yet."])
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in report.warnings)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {s}" for s in report.next_steps)
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, report: BitbucketReport) -> None:
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, markdown(report))
    write_text(root / PASS_LOG,
        "# Code RED SC-CL Bitbucket Setup Lane Pass\n\n"
        "Added preferred setup route for the upstream Bitbucket SC-CL source.\n\n"
        f"Report: `{REPORT_MD.as_posix()}`\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set up the preferred Bitbucket SC-CL source for Code RED.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--target", default=None, help="Target folder for Bitbucket source. Defaults to resources/SC-CL_bitbucket_source.")
    parser.add_argument("--clone", action="store_true", help="Run git clone if the target is not already staged.")
    parser.add_argument("--force", action="store_true", help="Delete target before cloning. Use carefully.")
    parser.add_argument("--build", action="store_true", help="Run Code RED build-from-source helper after staging.")
    parser.add_argument("--adopt", action="store_true", help="Adopt SC-CL.exe into Code RED if build/find succeeds.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = root_from_arg(args.root)
    target = Path(args.target).resolve() if args.target else (root / TARGET_DIR)
    report = prepare(root, target, clone=args.clone, force=args.force, build=args.build, adopt=args.adopt)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
