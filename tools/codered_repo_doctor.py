#!/usr/bin/env python3
"""Code RED repo doctor.

Audits active paths and generated clutter without deleting anything.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.1.0-main-safe"
REPORT_PATH = Path("logs/CodeRED_Repo_Doctor_Report.json")

ACTIVE_FILES = [
    "Run_Code_RED.bat",
    "Run_CodeRED_AI_Menu_Setup.bat",
    "Run_CodeRED_Build_Assistant.bat",
    "main.py",
    "python_workbench.py",
    "requirements.txt",
    "tools/codered_build_assistant.py",
    "tools/codered_actor_enum_tool.py",
    "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp",
    "related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.ini",
    "related_apps/CodeRED_Tuner/run_CodeRED_Tuner.bat",
    "related_apps/CodeRED_Tuner/run_CodeRed_Arcade.bat",
    "data/codered/actor_enum_map.csv",
    "data/codered/npc_roster.txt",
]

CRITICAL_DIR_NAMES = [
    "data",
    "logs",
    "related_apps",
    "tools",
]

BAD_RENAME_HINTS = [
    "data - Important",
    "logs - Organize",
    "related_apps - Combine",
    "tools - Implement",
]

GENERATED_PATTERNS = [
    "logs/CodeRED_Build_Assistant_last.log",
    "logs/CodeRED_Build_Assistant_last_report.json",
    "logs/CodeRED_Repo_Doctor_Report.json",
    "__pycache__",
]


@dataclass
class RepoDoctorReport:
    version: str
    project_root: str
    active_present: list[str] = field(default_factory=list)
    active_missing: list[str] = field(default_factory=list)
    critical_dirs_present: list[str] = field(default_factory=list)
    critical_dirs_missing: list[str] = field(default_factory=list)
    renamed_folder_risks: list[str] = field(default_factory=list)
    generated_present: list[str] = field(default_factory=list)
    related_apps_dirs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def audit(root: Path) -> RepoDoctorReport:
    root = root.resolve()
    report = RepoDoctorReport(VERSION, str(root))
    for item in ACTIVE_FILES:
        if (root / item).exists():
            report.active_present.append(item)
        else:
            report.active_missing.append(item)
    for item in CRITICAL_DIR_NAMES:
        if (root / item).is_dir():
            report.critical_dirs_present.append(item)
        else:
            report.critical_dirs_missing.append(item)
    for item in BAD_RENAME_HINTS:
        if (root / item).exists():
            report.renamed_folder_risks.append(item)
    for item in GENERATED_PATTERNS:
        if (root / item).exists():
            report.generated_present.append(item)
    related = root / "related_apps"
    if related.exists():
        report.related_apps_dirs = sorted(path.name for path in related.iterdir() if path.is_dir())
    if report.active_missing:
        report.notes.append("One or more expected active Code RED files are missing.")
    if report.critical_dirs_missing:
        report.notes.append("Critical runtime folder names must be restored before packaging.")
    if report.renamed_folder_risks:
        report.notes.append("Cleanup label folders were detected; active folders should keep original names.")
    if len(report.related_apps_dirs) > 20:
        report.notes.append("related_apps is large; archive only after a no-regression manifest review.")
    return report


def print_report(report: RepoDoctorReport) -> None:
    print(f"Code RED Repo Doctor {report.version}")
    print(f"Project: {report.project_root}")
    print(f"Active present: {len(report.active_present)}")
    print(f"Active missing: {len(report.active_missing)}")
    print(f"Critical dirs missing: {len(report.critical_dirs_missing)}")
    print(f"Renamed-folder risks: {len(report.renamed_folder_risks)}")
    print(f"Generated local outputs present: {len(report.generated_present)}")
    if report.active_missing:
        print("\nMissing active files:")
        for item in report.active_missing:
            print(f"  - {item}")
    if report.renamed_folder_risks:
        print("\nRename risks:")
        for item in report.renamed_folder_risks:
            print(f"  - {item}")
    if report.notes:
        print("\nNotes:")
        for note in report.notes:
            print(f"  - {note}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Code RED repo structure without changing files.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    root = args.project_root.resolve()
    report = audit(root)
    out = root / args.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    print_report(report)
    print(f"\nReport: {args.report}")
    return 1 if report.active_missing or report.critical_dirs_missing or report.renamed_folder_risks else 0


if __name__ == "__main__":
    raise SystemExit(main())
