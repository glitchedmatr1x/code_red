#!/usr/bin/env python3
"""Code RED SC-CL Build From Source helper.

Diagnostic-first builder for SC-CL. It is tuned for the upstream Bitbucket
SC-CL/LLVM layout and avoids stale/generated or example Visual Studio solutions.

Important behavior:
- Reuses/adopts SC-CL.exe when it already exists.
- Skips stale LLVM.sln files and example/test/Visual Studio extension solutions.
- Uses llvm-14.0.0.src as the clean CMake root when present.
- Adds the modern-CMake compatibility flag needed by old LLVM trees:
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5
- Builds SC-CL target first, then falls back to a Release build.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.2.0-sccl-cmake-policy-fix"
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
    skipped_solutions: list[dict[str, str]] = field(default_factory=list)
    cmake_lists: str | None = None
    cmake_source_used: str | None = None
    cmake_source_diagnostics: list[str] = field(default_factory=list)
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
        root / "resources" / "SC-CL_bitbucket_source",
        root / "SC-CL-master",
        root / "SC-CL",
        root / "resources" / "SC-CL-master",
        root / "resources" / "SC-CL",
        root / "related_apps" / "code_red_sccl_attempt_bundle_v1" / "SC-CL-master",
    ]:
        if candidate.exists():
            return candidate
    return root / "resources" / "SC-CL_bitbucket_source"


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def tail(text: str, limit: int = 6000) -> str:
    return text if len(text) <= limit else text[-limit:]


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
    markers: list[str] = []
    tokens = ["Red Dead Redemption", "RDR_SCO", "RDR_#SC", "XSC format", "CSC format", "SCO format"]
    files: list[Path] = []
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
        source / "sc-cl.exe",
        source / "sccl.exe",
        source / "bin" / "SC-CL.exe",
        source / "Release" / "SC-CL.exe",
        source / "x64" / "Release" / "SC-CL.exe",
        source / "build" / "Release" / "SC-CL.exe",
        source / "build" / "bin" / "Release" / "SC-CL.exe",
        source / "codered_build" / "Release" / "SC-CL.exe",
        source / "codered_build" / "bin" / "Release" / "SC-CL.exe",
        source / "llvm-14.0.0.src" / "MinSizeRel" / "bin" / "SC-CL.exe",
        source / "codered_llvm_build" / "Release" / "bin" / "SC-CL.exe",
        source / "codered_llvm_build" / "bin" / "Release" / "SC-CL.exe",
        source / "codered_llvm_build" / "tools" / "clang" / "tools" / "extra" / "SC-CL" / "Release" / "SC-CL.exe",
    ]
    for path in preferred:
        if path.exists():
            return path
    for path in source.rglob("*.exe"):
        if path.name.lower() in {"sc-cl.exe", "sccl.exe", "sc_cl.exe"}:
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


def solution_skip_reason(sln: Path, source: Path) -> str:
    name = sln.name.lower()
    path_text = str(sln).replace("\\", "/").lower()
    if name in {"menubase.sln", "test.sln"}:
        return "example/test solution, not SC-CL.exe"
    if "clang-format-vs" in path_text or "clang-tidy-vs" in path_text:
        return "Visual Studio extension solution, not SC-CL.exe"
    if name in {"clangformat.sln", "clangtidy.sln"}:
        return "Visual Studio extension solution, not SC-CL.exe"
    if name == "llvm.sln":
        zero = source / "ZERO_CHECK.vcxproj"
        text = read_text(zero)
        if zero.exists() and ("code_red_sccl_windows_build_kit_v1" in text or "output/SC-CL-master" in text or "output\\SC-CL-master" in text):
            return "stale generated LLVM.sln/ZERO_CHECK points at an old Code RED output path"
        return "generated LLVM solution; prefer clean CMake configure from llvm-14.0.0.src"
    return ""


def select_buildable_solutions(source: Path, report: BuildReport) -> list[Path]:
    slns = [p for p in source.rglob("*.sln")]
    report.sln_files = [str(p) for p in slns]
    buildable: list[Path] = []
    for sln in slns:
        reason = solution_skip_reason(sln, source)
        if reason:
            report.skipped_solutions.append({"solution": str(sln), "reason": reason})
        else:
            buildable.append(sln)
    # Only build solutions that explicitly look like the compiler solution.
    return [p for p in buildable if "sc-cl" in p.name.lower() or "sccl" in p.name.lower()]


def cmake_file_diagnostics(cmake_lists: Path) -> tuple[bool, str]:
    if not cmake_lists.exists():
        return False, "CMakeLists.txt not found"
    text = read_text(cmake_lists)
    has_project = re.search(r"(^|\n)\s*project\s*\(", text, re.IGNORECASE) is not None
    has_min = re.search(r"(^|\n)\s*cmake_minimum_required\s*\(", text, re.IGNORECASE) is not None
    uses_clang_tool_macro = "add_clang_executable" in text or "add_llvm_executable" in text
    if uses_clang_tool_macro and not has_project:
        return False, "CMakeLists.txt uses Clang/LLVM tool macros and is not a standalone top-level CMake root"
    if not has_project and not has_min:
        return False, "CMakeLists.txt has no project()/cmake_minimum_required(); likely a subdirectory recipe"
    return True, "appears to be a top-level CMake source root"


def select_cmake_source(source: Path, report: BuildReport) -> Path | None:
    root_cmake = source / "CMakeLists.txt"
    report.cmake_lists = str(root_cmake) if root_cmake.exists() else None
    llvm_src = source / "llvm-14.0.0.src"
    llvm_cmake = llvm_src / "CMakeLists.txt"
    if llvm_cmake.exists():
        ok, diag = cmake_file_diagnostics(llvm_cmake)
        report.cmake_source_diagnostics.append(f"{llvm_cmake}: {diag}")
        if ok:
            return llvm_src
    if root_cmake.exists():
        ok, diag = cmake_file_diagnostics(root_cmake)
        report.cmake_source_diagnostics.append(f"{root_cmake}: {diag}")
        if ok:
            return source
    if not llvm_cmake.exists():
        report.cmake_source_diagnostics.append(f"{llvm_cmake}: missing. A Clang tool-style SC-CL source needs the full LLVM source root or a prebuilt exe.")
    return None


def try_cmake_build(source_root: Path, source: Path, report: BuildReport, cmake: str, adopt: bool, root: Path) -> bool:
    build_dir = source / "codered_llvm_build" if source_root.name.lower().startswith("llvm") else source / "codered_build"
    configure_cmd = [
        cmake,
        "-S", str(source_root),
        "-B", str(build_dir),
        "-A", "x64",
        "-Thost=x64",
        "-DLLVM_TARGETS_TO_BUILD=X86",
        "-DLLVM_INCLUDE_TESTS=OFF",
        "-DLLVM_INCLUDE_BENCHMARKS=OFF",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
    ]
    configure = run_attempt("CMake configure clean LLVM source", configure_cmd, source)
    report.attempts.append(configure)
    if configure.exit_code != 0:
        return False

    target_names = ["SC-CL", "sc-cl", "sccl"]
    for target_name in target_names:
        target_cmd = [cmake, "--build", str(build_dir), "--config", "Release", "--target", target_name, "--parallel"]
        attempt = run_attempt(f"CMake build target {target_name}", target_cmd, source, timeout=1800)
        report.attempts.append(attempt)
        exe = find_sccl_exe(source) or find_sccl_exe(build_dir)
        if exe:
            report.sccl_exe = str(exe)
            if adopt:
                report.adopted_to = str(adopt_exe(root, exe))
            report.ok = True
            return True
        # If target name failed immediately, try the next spelling.
        if attempt.exit_code == 0:
            break

    full = run_attempt("CMake build Release", [cmake, "--build", str(build_dir), "--config", "Release", "--parallel"], source, timeout=3600)
    report.attempts.append(full)
    exe = find_sccl_exe(source) or find_sccl_exe(build_dir)
    if exe:
        report.sccl_exe = str(exe)
        if adopt:
            report.adopted_to = str(adopt_exe(root, exe))
        report.ok = True
        return True
    return False


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
        report.next_steps = ["Put SC-CL source in resources/SC-CL_bitbucket_source or pass --source with the real folder."]
        return report

    report.rdr_ready_markers = rdr_markers(source)
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
            "Run: py -3 tools\\codered_sccl_finalize_build.py --validate --compile-helper",
        ]
        return report

    buildable_solutions = select_buildable_solutions(source, report)
    cmake_source = select_cmake_source(source, report)
    report.cmake_source_used = str(cmake_source) if cmake_source else None

    if no_build:
        report.warnings.append("No SC-CL.exe found and --no-build was used.")
        report.next_steps = ["Run without --no-build to attempt the clean LLVM CMake build, or stage a prebuilt SC-CL.exe."]
        return report

    # Prefer clean CMake for LLVM-derived SC-CL. MSBuild is only used if an explicit SC-CL solution exists.
    if cmake_source and cmake:
        try_cmake_build(cmake_source, source, report, cmake, adopt, root)
    elif cmake_source and not cmake:
        report.attempts.append(BuildAttempt(name="CMake", command=[], cwd=str(source), exit_code=None, skipped_reason="CMake source exists but cmake was not detected"))

    if not report.ok and buildable_solutions and msbuild:
        sln = buildable_solutions[0]
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
    elif not report.ok and buildable_solutions and not msbuild:
        report.attempts.append(BuildAttempt(name="MSBuild", command=[], cwd=str(source), exit_code=None, skipped_reason="explicit SC-CL .sln exists but MSBuild was not detected"))

    if report.ok:
        report.next_steps = [
            "Run: py -3 tools\\codered_sccl_finalize_build.py --validate --compile-helper",
        ]
    else:
        if not report.rdr_ready_markers:
            report.warnings.append("This source folder did not show RDR markers like RDR_SCO/RDR_#SC/Red Dead Redemption.")
        if report.skipped_solutions:
            report.warnings.append("Generated/example/Visual Studio extension solutions were skipped; they are not SC-CL.exe build targets.")
        if not cmake_source:
            report.warnings.append("No standalone top-level CMake source root was found. Need llvm-14.0.0.src/CMakeLists.txt or a prebuilt exe.")
        report.warnings.append("SC-CL.exe was not produced. Review the CMake build output and the target list.")
        report.next_steps = [
            "Open logs\\CodeRED_SCCL_Build_From_Source_Output.txt and find the first CMake error after the policy fix.",
            "If configure succeeds but target SC-CL is unknown, build ALL_BUILD in Visual Studio from codered_llvm_build and then run the finalizer.",
            "After SC-CL.exe exists, run: py -3 tools\\codered_sccl_finalize_build.py --validate --compile-helper",
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
        f"- CMake source used: `{report.cmake_source_used}`",
        "- Solutions:",
    ])
    lines.extend(f"  - `{s}`" for s in report.sln_files or ["none"])
    if report.skipped_solutions:
        lines.extend(["", "## Skipped Solutions", ""])
        for item in report.skipped_solutions:
            lines.append(f"- `{item['solution']}` — {item['reason']}")
    if report.cmake_source_diagnostics:
        lines.extend(["", "## CMake Source Diagnostics", ""])
        lines.extend(f"- {item}" for item in report.cmake_source_diagnostics)
    lines.extend(["", "## Attempts", ""])
    for attempt in report.attempts:
        lines.extend([
            f"### {attempt.name}",
            f"- cwd: `{attempt.cwd}`",
            f"- exit: `{attempt.exit_code}`",
            f"- skipped: `{attempt.skipped_reason}`",
            f"- command: `{' '.join(attempt.command) if attempt.command else ''}`",
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
    lines = []
    for attempt in report.attempts:
        lines.append(f"## {attempt.name} exit={attempt.exit_code} skipped={attempt.skipped_reason}")
        lines.append("COMMAND: " + " ".join(attempt.command))
        lines.append("STDOUT:\n" + attempt.stdout_tail)
        lines.append("STDERR:\n" + attempt.stderr_tail)
    write_text(root / BUILD_LOG, "\n\n".join(lines) + "\n")
    write_text(root / PASS_LOG,
        "# Code RED SC-CL Build From Source Lane Pass\n\n"
        "Updated source-build helper to skip Visual Studio extension solutions and add the modern CMake policy compatibility flag.\n\n"
        f"Report: `{REPORT_MD.as_posix()}`\n",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build or adopt SC-CL.exe from a local SC-CL source folder.")
    p.add_argument("--root", default=None)
    p.add_argument("--source", default=None, help="Path to SC-CL source. Defaults to resources/SC-CL_bitbucket_source or SC-CL-master.")
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
