#!/usr/bin/env python3
"""Code RED repo doctor.

Audits generated clutter and known active paths without moving or deleting anything.
This is the safe first step before deeper repo consolidation.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.0.0-repo-consolidation-pass1"
REPORT_PATH = Path("logs/CodeRED_Repo_Doctor_Report.json")

ACTIVE_ROOT_FILES = [
    "Run_CodeRED_AI_Menu_Setup.bat",
    "Run_CodeRED_Build_Assistant.bat",
]

ACTIVE_PATHS = [
    "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp",
    "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.ini",
    "tools/codered_build_assistant.py",
    "tools/codered_actor_enum_tool.py",
    "tools/codered_ai_menu_layout_patch.py",
    "data/codered/actor_enum_map.csv",
    "data/codered/npc_roster.txt",
]

GENERATED_PATTERNS = [
    "logs/CodeRED_Actor_Enum_Validation_Report.json",
    "logs/CodeRED_Build_Assistant_last.log",
    "logs/CodeRED_Build_Assistant_last_report.json",
    "logs/external_patch_status.json",
    "tools/logs/CodeRED_Actor_Enum_Validation_Report.json",
    "data/codered/npc_roster_safe_verified.txt",
]

GENERATED_DIRS = [
    "related_apps/Code_RED_ScriptHookRDR_AI_Menu/build",
    "__pycache__",
]

@dataclass
class RepoDoctorReport:
    version: str
    project_root: str
    active_present: list[str] = field(default_factory=list)
    active_missing: list[str] = field(default_factory=list)
    generated_present: list[str] = field(default_factory=list)
    generated_dirs_present: list[str] = field(default_factory=list)
    related_apps_dirs: list[str] = field(default_factory=list)
    log_file_count: int = 0
    notes: list[str] = field(default_factory=list)


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def audit(root: Path) -> RepoDoctorReport:
    root = root.resolve()
    report = RepoDoctorReport(VERSION, str(root))

    for item in ACTIVE_ROOT_FILES + ACTIVE_PATHS:
        path = root / item
        if path.exists():
            report.active_present.append(item)
        else:
            report.active_missing.append(item)

    for item in GENERATED_PATTERNS:
        path = root / item
        if path.exists():
            report.generated_present.append(item)

    for item in GENERATED_DIRS:
        path = root / item
        if path.exists():
            report.generated_dirs_present.append(item)

    related = root / "related_apps"
    if related.exists():
        report.related_apps_dirs = sorted(p.name for p in related.iterdir() if p.is_dir())

    logs = root / "logs"
    if logs.exists():
        report.log_file_count = sum(1 for p in logs.rglob("*") if p.is_file())

    if report.active_missing:
        report.notes.append("One or more active CodeRED ASI/setup files are missing.")
    if report.generated_present or report.generated_dirs_present:
        report.notes.append("Generated local outputs are present and should not be committed.")
    if len(report.related_apps_dirs) > 8:
        report.notes.append("related_apps has many lanes; archive pass recommended after manifest review.")
    if report.log_file_count > 25:
        report.notes.append("logs folder is large; curated index/archive split recommended.")
    return report


def write_report(report: RepoDoctorReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")


def print_report(report: RepoDoctorReport) -> None:
    print(f"CodeRED Repo Doctor {report.version}")
    print(f"Project: {report.project_root}")
    print(f"Active present: {len(report.active_present)}")
    print(f"Active missing: {len(report.active_missing)}")
    print(f"Generated files present: {len(report.generated_present)}")
    print(f"Generated dirs present: {len(report.generated_dirs_present)}")
    print(f"related_apps dirs: {len(report.related_apps_dirs)}")
    print(f"logs file count: {report.log_file_count}")
    if report.active_missing:
        print("\nMissing active files:")
        for item in report.active_missing:
            print(f"  - {item}")
    if report.generated_present:
        print("\nGenerated files present:")
        for item in report.generated_present:
            print(f"  - {item}")
    if report.generated_dirs_present:
        print("\nGenerated dirs present:")
        for item in report.generated_dirs_present:
            print(f"  - {item}")
    if report.notes:
        print("\nNotes:")
        for note in report.notes:
            print(f"  - {note}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Code RED repo structure without deleting anything.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    root = args.project_root.resolve()
    report = audit(root)
    write_report(report, root / args.report)
    print_report(report)
    print(f"\nReport: {args.report}")
    return 1 if report.active_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
