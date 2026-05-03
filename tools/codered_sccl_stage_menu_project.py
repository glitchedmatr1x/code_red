#!/usr/bin/env python3
"""Stage Code RED's compiled menu as a real SC-CL project.

Why this exists:
Code RED's local compile-lab headers are static proof shims. They are useful for
name/shape validation, but SC-CL requires its real include kit, especially native
wrappers such as:

    extern _native32(0xE4DACF40) void _CLEAR_PRINTS()

This tool stages the Code RED menu source into the Bitbucket SC-CL bin/projects
layout and rewrites the include block to use the real SC-CL headers.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-sccl-stage-menu-project"
LAB = Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1")
SC_CL_SOURCE = Path("resources/SC-CL_bitbucket_source")
PROJECT_REL = Path("bin/projects/CodeREDMenu")
INCLUDE_REL = Path("bin/include")
REPORT_JSON = Path("logs/CodeRED_SCCL_Stage_Menu_Project_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Stage_Menu_Project_Report.md")
PASS_LOG = Path("logs/CodeRED_SCCL_Stage_Menu_Project_Lane_Pass_2026-05-03.md")

LOCAL_INCLUDE_RE = re.compile(r'^\s*#include\s+"\.\./include/[^\n]+"\s*$', re.MULTILINE)

REQUIRED_NATIVE_TOKENS = [
    "_CLEAR_PRINTS",
    "_PRINT_SUBTITLE",
    "_IS_KEY_PRESSED",
    "GET_PLAYER_ACTOR",
    "CREATE_LAYOUT",
    "CREATE_ACTOR_IN_LAYOUT",
    "SET_ACTOR_IN_VEHICLE",
    "SET_ACTOR_MAX_SPEED_ABSOLUTE",
    "WAIT",
]
REQUIRED_CONST_TOKENS = [
    "ACTOR_VEHICLE_Car01",
    "ACTOR_VEHICLE_Truck01",
]


@dataclass
class StageReport:
    version: str
    generated_utc: str
    root: str
    ok: bool
    lab_source: str
    staged_source: str | None = None
    sccl_source: str | None = None
    include_dir: str | None = None
    project_dir: str | None = None
    missing_files: list[str] = field(default_factory=list)
    missing_real_header_tokens: list[str] = field(default_factory=list)
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="ignore")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def find_sccl_source(root: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    for candidate in [root / SC_CL_SOURCE, root / "SC-CL-master"]:
        if (candidate / INCLUDE_REL / "RDR" / "natives32.h").exists():
            return candidate.resolve()
    return (root / SC_CL_SOURCE).resolve()


def real_header_blob(include_dir: Path) -> str:
    parts = []
    for rel_path in [
        "natives.h",
        "intrinsics.h",
        "types.h",
        "constants.h",
        "common.h",
        "RDR/natives32.h",
        "RDR/consts32.h",
    ]:
        path = include_dir / rel_path
        if path.exists():
            parts.append(read_text(path))
    return "\n".join(parts)


def transform_source(source: str) -> str:
    # Remove Code RED static-proof include shims and replace them with the real
    # SC-CL include kit style shown by MenuBase.c.
    source = LOCAL_INCLUDE_RE.sub("", source)
    source = source.replace('#include "../include/types.h"\n', "")
    source = source.replace('#include "../include/constants.h"\n', "")
    source = source.replace('#include "../include/intrinsics.h"\n', "")
    source = source.replace('#include "../include/natives.h"\n', "")
    source = source.replace('#include "../include/RDR/natives32.h"\n', "")
    source = source.replace('#include "../include/RDR/consts32.h"\n', "")
    real_includes = (
        '#include "natives.h"\n'
        '#include "intrinsics.h"\n'
        '#include "types.h"\n'
        '#include "constants.h"\n'
        '#include "common.h"\n\n'
    )
    if source.startswith("/*"):
        end = source.find("*/")
        if end != -1:
            return source[:end + 2] + "\n\n" + real_includes + source[end + 2:].lstrip()
    return real_includes + source.lstrip()


def stage(root: Path, sccl_source_arg: str | None) -> StageReport:
    root = root.resolve()
    lab_source = root / LAB / "src" / "main.c"
    sccl_source = find_sccl_source(root, sccl_source_arg)
    include_dir = sccl_source / INCLUDE_REL
    project_dir = sccl_source / PROJECT_REL
    staged_source = project_dir / "CodeREDMenu.c"

    report = StageReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        ok=False,
        lab_source=rel(lab_source, root),
        sccl_source=str(sccl_source),
        include_dir=str(include_dir),
        project_dir=str(project_dir),
        staged_source=str(staged_source),
    )

    required_files = [
        lab_source,
        include_dir / "natives.h",
        include_dir / "intrinsics.h",
        include_dir / "types.h",
        include_dir / "constants.h",
        include_dir / "common.h",
        include_dir / "RDR" / "natives32.h",
        include_dir / "RDR" / "consts32.h",
    ]
    report.missing_files = [str(p) for p in required_files if not p.exists()]
    if report.missing_files:
        report.warnings.append("Missing one or more real SC-CL include/source files. Stage aborted.")
        report.next_steps = [
            "Confirm resources\\SC-CL_bitbucket_source\\bin\\include exists and contains RDR\\natives32.h / consts32.h.",
            "Do not compile against Code RED's static proof headers.",
        ]
        write_outputs(root, report)
        return report

    header_blob = real_header_blob(include_dir)
    for token in REQUIRED_NATIVE_TOKENS + REQUIRED_CONST_TOKENS:
        if token not in header_blob:
            report.missing_real_header_tokens.append(token)
    if report.missing_real_header_tokens:
        report.warnings.append("The real SC-CL headers are missing tokens used by CodeREDMenu.c. Compile may fail until names are adjusted.")

    project_dir.mkdir(parents=True, exist_ok=True)
    staged = transform_source(read_text(lab_source))
    write_text(staged_source, staged)
    # Keep a source snapshot in the compile lab too for reviewability.
    mirror = root / LAB / "src" / "CodeREDMenu.sccl_project.c"
    write_text(mirror, staged)
    report.actions.append(f"Staged Code RED menu project source: {rel(staged_source, root)}")
    report.actions.append(f"Mirrored staged source for review: {rel(mirror, root)}")
    report.ok = not report.missing_real_header_tokens
    report.next_steps = [
        "Run: py -3 tools\\codered_sccl_safe_compile_probe.py --project codered_menu_v1 --timeout 30",
        "If the probe passes, verify output file hashes before any archive import.",
    ]
    write_outputs(root, report)
    return report


def markdown(report: StageReport) -> str:
    lines = [
        "# Code RED SC-CL Stage Menu Project Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Result: **{'PASS' if report.ok else 'NEEDS ATTENTION'}**",
        f"Lab source: `{report.lab_source}`",
        f"Staged source: `{report.staged_source}`",
        f"SC-CL source: `{report.sccl_source}`",
        f"Include dir: `{report.include_dir}`",
        f"Project dir: `{report.project_dir}`",
        "",
        "## Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in report.actions or ["No actions completed."])
    if report.missing_files:
        lines.extend(["", "## Missing Files", ""])
        lines.extend(f"- `{item}`" for item in report.missing_files)
    if report.missing_real_header_tokens:
        lines.extend(["", "## Missing Real Header Tokens", ""])
        lines.extend(f"- `{item}`" for item in report.missing_real_header_tokens)
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in report.warnings)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {item}" for item in report.next_steps)
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, report: StageReport) -> None:
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, markdown(report))
    write_text(root / PASS_LOG,
        "# Code RED SC-CL Stage Menu Project Lane Pass\n\n"
        "Added staging from Code RED's menu source into the real SC-CL bin/projects layout using bin/include.\n\n"
        f"Report: `{REPORT_MD.as_posix()}`\n",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stage Code RED menu as a real SC-CL bin/projects source.")
    p.add_argument("--root", default=None)
    p.add_argument("--sccl-source", default=None, help="Path to SC-CL Bitbucket/source folder containing bin/include")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = root_from_arg(args.root)
    report = stage(root, args.sccl_source)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
