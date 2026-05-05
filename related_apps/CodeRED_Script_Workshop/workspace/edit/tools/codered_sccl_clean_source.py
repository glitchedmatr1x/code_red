#!/usr/bin/env python3
"""Code RED SC-CL source cleanup helper.

CMake may refuse to configure old LLVM trees when generated in-source build
artifacts are present. This helper scans for the most common generated files
that trigger LLVM's "previous in-source build" guard and can quarantine them
instead of deleting them permanently.

Default mode is read-only. Use --apply to move suspicious generated files into a
quarantine folder under the SC-CL source tree.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-sccl-clean-source"
REPORT_JSON = Path("logs/CodeRED_SCCL_Clean_Source_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Clean_Source_Report.md")

SUSPICIOUS_RELATIVE = [
    "lib/Target/Hexagon/HexagonDepDecoders.inc",
    "include/llvm/Config/config.h",
    "include/llvm/Config/llvm-config.h",
    "include/llvm/Support/VCSRevision.h",
]
SUSPICIOUS_DIRS = ["CMakeFiles", "cmakefiles"]
SUSPICIOUS_FILES = ["CMakeCache.txt", "cmake_install.cmake", "Makefile", "build.ninja"]


@dataclass
class CleanReport:
    version: str
    generated_utc: str
    source: str
    apply: bool
    ok: bool
    quarantine: str
    suspicious_files: list[str] = field(default_factory=list)
    moved_files: list[str] = field(default_factory=list)
    suspicious_dirs: list[str] = field(default_factory=list)
    moved_dirs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def root_from_arg(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else Path(__file__).resolve().parents[1]


def default_source(root: Path) -> Path:
    for candidate in [
        root / "resources" / "SC-CL_bitbucket_source" / "llvm-14.0.0.src",
        root / "SC-CL-master" / "llvm-14.0.0.src",
        root / "resources" / "SC-CL-master" / "llvm-14.0.0.src",
    ]:
        if candidate.exists():
            return candidate
    return root / "SC-CL-master" / "llvm-14.0.0.src"


def rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return str(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="ignore")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def unique_target(quarantine: Path, relative: str) -> Path:
    target = quarantine / relative
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    for i in range(1, 1000):
        candidate = parent / f"{stem}.{i}{suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem}.overflow{suffix}"


def scan_source(source: Path) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    dirs: list[Path] = []
    for item in SUSPICIOUS_RELATIVE:
        p = source / item
        if p.exists() and p.is_file():
            files.append(p)
    for name in SUSPICIOUS_FILES:
        p = source / name
        if p.exists() and p.is_file():
            files.append(p)
    for name in SUSPICIOUS_DIRS:
        p = source / name
        if p.exists() and p.is_dir():
            dirs.append(p)
    return files, dirs


def clean(root: Path, source: Path, apply: bool) -> CleanReport:
    source = source.resolve()
    quarantine = source / "_codered_quarantine_in_source_build_artifacts"
    report = CleanReport(
        version=VERSION,
        generated_utc=utc_now(),
        source=str(source),
        apply=apply,
        ok=False,
        quarantine=str(quarantine),
    )
    if not source.exists():
        report.warnings.append(f"Source folder does not exist: {source}")
        report.next_steps = ["Pass --source pointing to llvm-14.0.0.src."]
        write_outputs(root, report)
        return report

    files, dirs = scan_source(source)
    report.suspicious_files = [rel(p, source) for p in files]
    report.suspicious_dirs = [rel(p, source) for p in dirs]

    if apply and (files or dirs):
        quarantine.mkdir(parents=True, exist_ok=True)
        for p in files:
            target = unique_target(quarantine, rel(p, source))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(target))
            report.moved_files.append(rel(target, source))
        for p in dirs:
            target = unique_target(quarantine, rel(p, source))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(target))
            report.moved_dirs.append(rel(target, source))

    report.ok = (not files and not dirs) or apply
    if files or dirs:
        if apply:
            report.warnings.append("Suspicious in-source build artifacts were moved to quarantine, not permanently deleted.")
        else:
            report.warnings.append("Suspicious in-source build artifacts found. Re-run with --apply to quarantine them.")
    report.next_steps = [
        "Use CMake 3.x if current CMake reports CMP0051 OLD behavior errors.",
        "Then run: py -3 tools\\codered_sccl_build_from_source.py --source \"D:\\Games\\Red Dead Redemption\\Code_RED\\SC-CL-master\" --adopt",
    ]
    write_outputs(root, report)
    return report


def markdown(report: CleanReport) -> str:
    lines = [
        "# Code RED SC-CL Source Cleanup Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Result: **{'PASS' if report.ok else 'NEEDS CLEANUP'}**",
        f"Source: `{report.source}`",
        f"Apply mode: `{report.apply}`",
        f"Quarantine: `{report.quarantine}`",
        "",
        "## Suspicious Files",
        "",
    ]
    lines.extend(f"- `{p}`" for p in report.suspicious_files or ["none"])
    lines.extend(["", "## Suspicious Directories", ""])
    lines.extend(f"- `{p}`" for p in report.suspicious_dirs or ["none"])
    if report.moved_files or report.moved_dirs:
        lines.extend(["", "## Moved To Quarantine", ""])
        lines.extend(f"- `{p}`" for p in report.moved_files + report.moved_dirs)
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in report.warnings)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {s}" for s in report.next_steps)
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, report: CleanReport) -> None:
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, markdown(report))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scan/quarantine SC-CL LLVM in-source build artifacts.")
    p.add_argument("--root", default=None)
    p.add_argument("--source", default=None, help="Path to llvm-14.0.0.src. Defaults to common Code RED locations.")
    p.add_argument("--apply", action="store_true", help="Move suspicious artifacts to quarantine.")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = root_from_arg(args.root)
    source = Path(args.source).resolve() if args.source else default_source(root)
    report = clean(root, source, apply=args.apply)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
