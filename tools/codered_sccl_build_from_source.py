#!/usr/bin/env python3
"""Code RED SC-CL Build From Source helper.

The SC-CL README confirms Red Dead Redemption support, but many local source
copies do not include a ready-made SC-CL.exe. This helper makes that stage less
manual:

1. Probe a local SC-CL source folder.
2. Reuse/adopt SC-CL.exe if it already exists anywhere under that folder.
3. Try Visual Studio/MSBuild when a .sln is present.
4. Try CMake when CMakeLists.txt is present.
5. Re-scan for SC-CL.exe and optionally copy it into the Code RED build kit.

It writes proof logs and never claims compiled script output unless SC-CL.exe is
actually produced or found.
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

VERSION = "1.0.0-sccl-build-from-source"
KIT = Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1")
DROP = Path("resources/SC-CL_DROP_HERE")
REPORT_JSON = Path("logs/CodeRED_SCCL_Build_From_Source_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Build_From_Source_Report.md")
PASS_LOG = Path("logs/CodeRED_SCCL_Build_From_Source_Lane_Pass_2026-05-03.md")
BUILD_LOG = Path("logs/CodeRED_SCCL_Build_From_Source_Output.txt")


@dataclass
class BuildAttempt:
    name: str
    command: list[str]
    cwd: str
    exit_code: int | None
    stdout_tail: str = ""
    stderr_tail: str = ""
    skipped_reason: str = ""


@dataclass
class BuildReport:
    version: str
    generated_utc: str
    root: str
    source: str
    ok: bool
    sccl_exe: str | None = None
    adopted_to: str | None = None
    source_exists: bool = False
    rdr_ready_markers: list[str] = field(default_factory=list)
    sln_files: list[str] = field(default_factory=list)
    cmake_lists: str | None = None
    msbuild: str | None = None
    cmake: str | None = None
    attempts: list[BuildAttempt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def root_from_arg(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else Path(__file__).resolve().parents[1]


def default_source(root: Path) -> Path:
    for candidate in [
        root / "SC-CL-master",
        root / "SC-CL",
        root / "resources" / "SC-CL-master",
        root / "resources" / "SC-CL",
        root / "related_apps" / "code_red_sccl_attempt_bundle_v1" / "SC-CL-master",
    ]:
        if candidate.exists():
            return candidate
    return root / "SC-CL-master"


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def tail(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="ignore")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def find_vswhere() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    found = shutil.which("vswhere")
    return Path(found) if found else None


def find_msbuild() -> Path | None:
    direct = shutil.which("MSBuild.exe") or shutil.which("msbuild")
    if direct:
        return Path(direct)
    vswhere = find_vswhere()
    if not vswhere:
        return None
    try:
        proc = subprocess.run(
            [str(vswhere), "-latest", "-requires", "Microsoft.Component.MSBuild", "-find", "MSBuild\\**\\Bin\\MSBuild.exe"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        for line in proc.stdout.splitlines():
            candidate = Path(line.strip())
            if candidate.exists():
                return candidate
    except Exception:
        return None
    return None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def rdr_markers(source: Path) -> list[str]:
    markers = []
    tokens = ["Red Dead Redemption", "RDR_SCO", "RDR_#SC", "XSC format", "CSC format", "SCO format"]
    files = []
    for name in ["README.md", "README.txt", "readme.md", "readme.txt"]:
        p = source / name
        if p.exists():
            files.append(p)
    files.extend(list(source.glob("*.md"))[:5])
    files.extend(list(source.glob("*.txt"))[:5])
    blob = "\n".join(read_text(p) for p in files)
    if not blob and source.exists():
        for p in list(source.rglob("*"))[:1500]:
            if p.is_file() and p.suffix.lower() in {".md", ".txt", ".h", ".hpp", ".cpp", ".c"}:
                blob += "\n" + read_text(p)
    for token in tokens:
        if token.lower() in blob.lower() and token not in markers:
            markers.append(token)
    return markers


def find_sccl_exe(source: Path) -> Path | None:
    if not source.exists():
        return None
    preferred = [
        source / "SC-CL.exe",
        source / "bin" / "SC-CL.exe",
        source / "Release" / "SC-CL.exe",
        source / "x64" / "Release" / "SC-CL.exe",
        source / "build" / "Release" / "SC-CL.exe",
        source / "build" / "bin" / "Release" / "SC-CL.exe",
        source / "llvm-14.0.0.src" / "MinSizeRel" / "bin" / "SC-CL.exe",
    ]
    for path in preferred:
        if path.exists():
            return path
    for path in source.rglob("SC-CL.exe"):
        if path.exists():
            return path
    return None


def run_attempt(name: str, command: list[str], cwd: Path, timeout: int = 900) -> BuildAttempt:
    try:
        proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
        return BuildAttempt(name=name, command=command, cwd=str(cwd), exit_code=proc.returncode, stdout_tail=tail(proc.stdout), stderr_tail=tail(proc.stderr))
    except Exception as exc:
        return BuildAttempt(name=name, command=command, cwd=str(cwd), exit_code=None, stderr_tail=str(exc))


def adopt_exe(root: Path, exe: Path) -> Path:
    target = root / KIT / "SC-CL.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, target)
    drop = root / DROP
    drop.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(exe, drop / "SC-CL.exe")
    except Exception:
        pass
    return target


def build(root: Path, source: Path, adopt: bool, no_build: bool) -> BuildReport:
    source = source.resolve()
    report = BuildReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        source=str(source),
        ok=False,
        source_exists=source.exists(),
    )
    if not source.exists():
        report.warnings.append(f"SC-CL source folder does not exist: {source}")
        report.next_steps = ["Put SC-CL-master in the Code RED root or pass --source with the real folder."]
        return report

    report.rdr_ready_markers = rdr_markers(source)
    report.sln_files = [str(p) for p in source.rglob("*.sln")]
    cmake_lists = source / "CMakeLists.txt"
    report.cmake_lists = str(cmake_lists) if cmake_lists.exists() else None
    msbuild = find_msbuild()
    cmake = shutil.which("cmake")
    report.msbuild = str(msbuild) if msbuild else None
    report.cmake = cmake

    exe = find_sccl_exe(source)
    if exe:
        report.sccl_exe = str(exe)
        if adopt:
            report.adopted_to = str(adopt_exe(root, exe))
        report.ok = True
        report.next_steps = [
            "Run: py -3 tools\\codered_sccl_easy_setup.py status --run-validator",
            "Run: related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat",
        ]
        return report

    if no_build:
        report.warnings.append("No SC-CL.exe found and --no-build was used.")
        report.next_steps = ["Run without --no-build to attempt MSBuild/CMake, or stage a prebuilt SC-CL.exe."]
        return report

    # Try MSBuild first if there is a solution.
    if report.sln_files and msbuild:
        sln = Path(report.sln_files[0])
        for platform in ["x64", "Win32", "Any CPU"]:
            cmd = [str(msbuild), str(sln), "/m", "/p:Configuration=Release", f"/p:Platform={platform}"]
            attempt = run_attempt(f"MSBuild Release {platform}", cmd, source)
            report.attempts.append(attempt)
            exe = find_sccl_exe(source)
            if exe:
                report.sccl_exe = str(exe)
                if adopt:
                    report.adopted_to = str(adopt_exe(root, exe))
                report.ok = True
                break
    elif report.sln_files and not msbuild:
        report.attempts.append(BuildAttempt(name="MSBuild", command=[], cwd=str(source), exit_code=None, skipped_reason=".sln exists but MSBuild was not detected."))

    # Try CMake if MSBuild did not produce an exe.
    if not report.ok and report.cmake_lists and cmake:
        build_dir = source / "codered_build"
        configure = run_attempt("CMake configure", [cmake, "-S", str(source), "-B", str(build_dir), "-A", "x64"], source)
        report.attempts.append(configure)
        if configure.exit_code == 0:
            compile_attempt = run_attempt("CMake build Release", [cmake, "--build", str(build_dir), "--config", "Release", "--parallel"], source)
            report.attempts.append(compile_attempt)
            exe = find_sccl_exe(source)
            if not exe:
                exe = find_sccl_exe(build_dir)
            if exe:
                report.sccl_exe = str(exe)
                if adopt:
                    report.adopted_to = str(adopt_exe(root, exe))
                report.ok = True
    elif not report.ok and report.cmake_lists and not cmake:
        report.attempts.append(BuildAttempt(name="CMake", command=[], cwd=str(source), exit_code=None, skipped_reason="CMakeLists.txt exists but cmake was not detected."))

    if report.ok:
        report.next_steps = [
            "Run: py -3 tools\\codered_sccl_easy_setup.py status --run-validator",
            "Run: related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat",
        ]
    else:
        if not report.rdr_ready_markers:
            report.warnings.append("This source folder did not show RDR markers like RDR_SCO/RDR_#SC/Red Dead Redemption.")
        report.warnings.append("SC-CL.exe was not produced. Check the build output log and install Visual Studio Build Tools/CMake if needed.")
        report.next_steps = [
            "Install Visual Studio Build Tools 2022 with Desktop development with C++ if MSBuild is missing.",
            "Install CMake if the source uses CMakeLists.txt.",
            "Run this helper again with --adopt after the build succeeds.",
            "If the repo only contains source and no build system, obtain a prebuilt SC-CL.exe matching this source family.",
        ]
    return report


def markdown(report: BuildReport) -> str:
    lines = [
        "# Code RED SC-CL Build From Source Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Result: **{'PASS' if report.ok else 'NEEDS BUILD'}**",
        f"Source: `{report.source}`",
        f"SC-CL.exe: `{report.sccl_exe}`",
        f"Adopted to: `{report.adopted_to}`",
        "",
        "## RDR Readiness Markers",
        "",
    ]
    lines.extend(f"- `{m}`" for m in report.rdr_ready_markers or ["none"])
    lines.extend([
        "",
        "## Build Systems",
        "",
        f"- MSBuild: `{report.msbuild}`",
        f"- CMake: `{report.cmake}`",
        f"- CMakeLists.txt: `{report.cmake_lists}`",
        "- Solutions:",
    ])
    lines.extend(f"  - `{s}`" for s in report.sln_files or ["none"])
    lines.extend(["", "## Attempts", ""])
    for attempt in report.attempts:
        lines.extend([
            f"### {attempt.name}",
            f"- cwd: `{attempt.cwd}`",
            f"- exit: `{attempt.exit_code}`",
            f"- skipped: `{attempt.skipped_reason}`",
            f"- command: `{ ' '.join(attempt.command) if attempt.command else '' }`",
            "",
        ])
        if attempt.stdout_tail:
            lines.extend(["stdout tail:", "```text", attempt.stdout_tail, "```", ""])
        if attempt.stderr_tail:
            lines.extend(["stderr tail:", "```text", attempt.stderr_tail, "```", ""])
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in report.warnings)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {s}" for s in report.next_steps)
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, report: BuildReport) -> None:
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, markdown(report))
    # A plain output log is useful for quick review.
    lines = []
    for attempt in report.attempts:
        lines.append(f"## {attempt.name} exit={attempt.exit_code} skipped={attempt.skipped_reason}")
        lines.append("COMMAND: " + " ".join(attempt.command))
        lines.append("STDOUT:\n" + attempt.stdout_tail)
        lines.append("STDERR:\n" + attempt.stderr_tail)
    write_text(root / BUILD_LOG, "\n\n".join(lines) + "\n")
    write_text(root / PASS_LOG,
        "# Code RED SC-CL Build From Source Lane Pass\n\n"
        "Added guided source-build/adopt helper for SC-CL-master.\n\n"
        f"Report: `{REPORT_MD.as_posix()}`\n",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build or adopt SC-CL.exe from a local SC-CL-master source folder.")
    p.add_argument("--root", default=None)
    p.add_argument("--source", default=None, help="Path to SC-CL-master. Defaults to common Code RED locations.")
    p.add_argument("--adopt", action="store_true", help="Copy found/built SC-CL.exe into the Code RED build kit.")
    p.add_argument("--no-build", action="store_true", help="Only probe; do not run MSBuild/CMake.")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = root_from_arg(args.root)
    source = Path(args.source).resolve() if args.source else default_source(root)
    report = build(root, source, adopt=args.adopt, no_build=args.no_build)
    write_outputs(root, report)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
