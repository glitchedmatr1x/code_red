#!/usr/bin/env python3
"""Build the first Code RED Faction Wars staged patch plan.

This does not mutate game archives. It reads the actionable target shortlist,
selects real local tune/content/world-resource candidates, copies them into a
scratch staging folder, and writes a conservative FW-1 patch plan.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

VERSION = "1.0.0-fw1-staged-builder"
ACTIONABLE_CSV = Path("data/codered/faction_wars_actionable_targets.csv")
STAGE_ROOT = Path("scratch/faction_wars/fw1")
STAGED_RESOURCES = STAGE_ROOT / "staged_resources"
MANIFEST_JSON = STAGE_ROOT / "fw1_staged_manifest.json"
MANIFEST_CSV = STAGE_ROOT / "fw1_staged_manifest.csv"
PLAN_MD = STAGE_ROOT / "FW1_PATCH_PLAN.md"
NEXT_STEPS = STAGE_ROOT / "NEXT_STEPS.txt"
REPORT_JSON = Path("logs/CodeRED_Faction_Wars_FW1_Builder_Report.json")
REPORT_MD = Path("logs/CodeRED_Faction_Wars_FW1_Builder_Report.md")

PATCHABLE_SUFFIXES = {".xml", ".ini", ".json", ".csv", ".txt", ".md"}
PREFERRED_PATCH_SUFFIXES = {".xml", ".ini", ".json"}

PATCHABLE_PATH_HINTS = (
    "research/modified_xml/",
    "research/tune - ",
    "research/codered_cutscene_placement_pass15_build/reports/",
    "research/codered_refgroup",
    "research/15_",
    "research/car_truck_inventory/",
    "research/blackwater_wsi_gringo_correlation_outputs/",
    "research/blackwater_host_placement_resolver_outputs/",
    "docs/",
)

REJECT_PATH_HINTS = (
    "tools/",
    "scratch/script_workshop_pipeline/",
    "scratch/script_workshop_compile/",
    "related_apps/codered_script_workshop/workspace/",
    "related_apps/code_red_sccl_attempt_bundle_v1/",
    "related_apps/code_red_scripthookrdr_ai_menu/",
    "research/faction_wars/fw_actionable_targets.md",
    "research/faction_wars/fw_target_plan.md",
    "research/important_readable_root_index_2026-05-02/",
    "research/menu resources/natives.h",
    "data/codered/",
    "logs/",
)

FW1_STRONG_HINTS = (
    "placementglobals",
    "rival_gang",
    "all_towns_active",
    "stronger npc",
    "template_base_human",
    "components.xml",
    "actions_templates.xml",
    "max render and spawns",
    "refgroup",
    "population",
    "blackwater",
    "tune",
    "lasso",
    "hogtie",
    "sheriff",
    "law",
    "gang",
)


@dataclass
class FW1Candidate:
    source_path: str
    staged_path: str
    phase: str
    category: str
    actionable_score: int
    raw_score: int
    priority: int
    sha1: str
    size: int
    reason: str
    regions: str = ""
    high_value_terms: str = ""


@dataclass
class FW1Report:
    version: str
    generated_utc: str
    root: str
    input_rows: int
    staged_count: int
    rejected_missing: int
    rejected_noise: int
    outputs: dict[str, str]
    staged: list[dict] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__).resolve()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "main.py").exists() and (candidate / "python_workbench.py").exists():
            return candidate
    return Path.cwd().resolve()


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def int_field(row: dict[str, str], key: str) -> int:
    try:
        return int(str(row.get(key, "0")).strip() or "0")
    except ValueError:
        return 0


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(root: Path) -> list[dict[str, str]]:
    path = root / ACTIONABLE_CSV
    if not path.exists():
        raise FileNotFoundError(f"Missing actionable targets: {path}. Run tools/codered_faction_wars_actionable_targets.py first.")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def path_blob(row: dict[str, str]) -> str:
    return " ".join(str(row.get(key, "")) for key in ("path", "phase", "category", "regions", "groups", "high_value_terms")).replace("\\", "/").lower()


def is_noise_path(rel: str) -> bool:
    low = rel.replace("\\", "/").lower()
    return any(hint in low for hint in REJECT_PATH_HINTS)


def looks_patchable(rel: str, path: Path) -> bool:
    low = rel.replace("\\", "/").lower()
    if path.suffix.lower() not in PATCHABLE_SUFFIXES:
        return False
    if is_noise_path(rel):
        return False
    if any(hint in low for hint in PATCHABLE_PATH_HINTS):
        return True
    return path.suffix.lower() in PREFERRED_PATCH_SUFFIXES and low.startswith("research/")


def priority_for(row: dict[str, str], path: Path) -> tuple[int, str]:
    blob = path_blob(row)
    priority = int_field(row, "actionable_score")
    reasons: list[str] = []
    if path.suffix.lower() in PREFERRED_PATCH_SUFFIXES:
        priority += 500
        reasons.append("preferred patchable suffix")
    if row.get("phase", "").startswith("FW-1"):
        priority += 300
        reasons.append("FW-1 phase")
    if row.get("category") == "tune/template pressure":
        priority += 250
        reasons.append("tune/template pressure")
    if "placementglobals" in blob or "rival_gang" in blob:
        priority += 1000
        reasons.append("rival gang placement candidate")
    if "stronger npc" in blob or "template_base_human" in blob:
        priority += 700
        reasons.append("NPC template pressure candidate")
    for hint in FW1_STRONG_HINTS:
        if hint in blob:
            priority += 60
    return priority, "; ".join(reasons) if reasons else "ranked by actionable target score"


def stage_candidates(root: Path, rows: Sequence[dict[str, str]], limit: int) -> tuple[list[FW1Candidate], int, int]:
    staged: list[FW1Candidate] = []
    rejected_missing = 0
    rejected_noise = 0
    ranked: list[tuple[int, str, dict[str, str], Path, str]] = []
    for row in rows:
        rel = str(row.get("path", "")).replace("\\", "/")
        if not rel:
            rejected_noise += 1
            continue
        source = root / rel
        if not source.exists() or not source.is_file():
            rejected_missing += 1
            continue
        if not looks_patchable(rel, source):
            rejected_noise += 1
            continue
        priority, reason = priority_for(row, source)
        ranked.append((priority, rel, row, source, reason))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

    if STAGED_RESOURCES.exists():
        shutil.rmtree(root / STAGE_ROOT)
    (root / STAGED_RESOURCES).mkdir(parents=True, exist_ok=True)

    for priority, rel, row, source, reason in ranked[:limit]:
        staged_rel = STAGED_RESOURCES / rel
        staged_path = root / staged_rel
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, staged_path)
        staged.append(
            FW1Candidate(
                source_path=rel,
                staged_path=rel_to(staged_path, root),
                phase=row.get("phase", ""),
                category=row.get("category", ""),
                actionable_score=int_field(row, "actionable_score"),
                raw_score=int_field(row, "score"),
                priority=priority,
                sha1=sha1_file(source),
                size=source.stat().st_size,
                reason=reason,
                regions=row.get("regions", ""),
                high_value_terms=row.get("high_value_terms", ""),
            )
        )
    return staged, rejected_missing, rejected_noise


def write_manifest_csv(path: Path, staged: Sequence[FW1Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["priority", "phase", "category", "source_path", "staged_path", "actionable_score", "raw_score", "sha1", "size", "reason", "regions", "high_value_terms"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in staged:
            row = asdict(item)
            writer.writerow({field: row.get(field, "") for field in fields})


def build_plan(staged: Sequence[FW1Candidate]) -> str:
    lines = [
        "# Code RED Faction Wars FW-1 Patch Plan",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "## Safety rule",
        "",
        "This pass only stages local candidate resources. It does not patch source RPF archives, does not install scripts, and does not use the AI menu/native spawn lane.",
        "",
        "## Recommended first patch",
        "",
    ]
    if staged:
        first = staged[0]
        lines.extend([
            f"Start with: `{first.source_path}`",
            "",
            f"Reason: {first.reason}",
            "",
            "Patch only this one candidate first, then run copied-archive proof and reopen verification before touching any second file.",
        ])
    else:
        lines.append("No local patchable FW-1 candidates were staged. Re-run the broad/actionable scans or stage tune/content RPF research first.")
    lines.extend([
        "",
        "## Staged candidates",
        "",
        "| Rank | Priority | Phase | Category | Source | Staged copy | Reason |",
        "|---:|---:|---|---|---|---|---|",
    ])
    for index, item in enumerate(staged, start=1):
        lines.append(
            f"| {index} | {item.priority} | {item.phase} | {item.category} | `{item.source_path}` | `{item.staged_path}` | {item.reason} |"
        )
    lines.extend([
        "",
        "## Manual patch checklist",
        "",
        "1. Open the staged copy, not the source file.",
        "2. Make one conservative faction-war pressure change.",
        "3. Record exact fields/values changed in this plan or a new report.",
        "4. Use copied-archive RPF patch proof only after the staged file is reviewed.",
        "5. Reopen/verify the copied archive before install.",
        "6. Do not combine FW-1 with menu/native spawn changes.",
    ])
    return "\n".join(lines) + "\n"


def build_report_markdown(report: FW1Report) -> str:
    lines = [
        "# Code RED Faction Wars FW-1 Builder Report",
        "",
        f"Generated: `{report.generated_utc}`",
        f"Version: `{report.version}`",
        "",
        "## Summary",
        "",
        f"- Input rows: `{report.input_rows}`",
        f"- Staged candidates: `{report.staged_count}`",
        f"- Rejected missing local files: `{report.rejected_missing}`",
        f"- Rejected noise/non-patchable files: `{report.rejected_noise}`",
        "",
        "## Outputs",
        "",
    ]
    for label, path in report.outputs.items():
        lines.append(f"- {label}: `{path}`")
    lines.extend(["", "## Top staged", "", "| Priority | Source | Reason |", "|---:|---|---|"])
    for item in report.staged[:15]:
        lines.append(f"| {item['priority']} | `{item['source_path']}` | {item['reason']} |")
    return "\n".join(lines) + "\n"


def run(root: Path, limit: int) -> FW1Report:
    root = root.resolve()
    rows = load_rows(root)
    staged, rejected_missing, rejected_noise = stage_candidates(root, rows, limit)

    stage_root = root / STAGE_ROOT
    stage_root.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST_JSON).write_text(json.dumps([asdict(item) for item in staged], indent=2), encoding="utf-8")
    write_manifest_csv(root / MANIFEST_CSV, staged)
    (root / PLAN_MD).write_text(build_plan(staged), encoding="utf-8")
    (root / NEXT_STEPS).write_text(
        "Open scratch/faction_wars/fw1/FW1_PATCH_PLAN.md\n"
        "Patch only the first staged candidate first.\n"
        "Use copied-archive proof before install.\n",
        encoding="utf-8",
    )

    report = FW1Report(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        input_rows=len(rows),
        staged_count=len(staged),
        rejected_missing=rejected_missing,
        rejected_noise=rejected_noise,
        outputs={
            "stage_root": rel_to(stage_root, root),
            "plan": rel_to(root / PLAN_MD, root),
            "manifest_json": rel_to(root / MANIFEST_JSON, root),
            "manifest_csv": rel_to(root / MANIFEST_CSV, root),
            "next_steps": rel_to(root / NEXT_STEPS, root),
            "report_json": rel_to(root / REPORT_JSON, root),
            "report_markdown": rel_to(root / REPORT_MD, root),
        },
        staged=[asdict(item) for item in staged[:25]],
    )
    (root / REPORT_JSON).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT_JSON).write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    (root / REPORT_MD).write_text(build_report_markdown(report), encoding="utf-8")
    return report


def print_report(report: FW1Report) -> None:
    print("# Code RED Faction Wars FW-1 Builder")
    print()
    print(f"Input rows: {report.input_rows}")
    print(f"Staged candidates: {report.staged_count}")
    print(f"Rejected missing: {report.rejected_missing}")
    print(f"Rejected noise/non-patchable: {report.rejected_noise}")
    print()
    print(f"{'Rank':>4}  {'Priority':>8}  Source")
    print("-" * 120)
    for index, item in enumerate(report.staged[:15], start=1):
        print(f"{index:>4}  {item['priority']:>8}  {item['source_path']}")
    print()
    print("Review:", report.outputs["plan"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build staged FW-1 faction-war patch plan.")
    parser.add_argument("--root", type=Path, default=None, help="Code RED root folder")
    parser.add_argument("--limit", type=int, default=12, help="Number of candidates to stage")
    parser.add_argument("--json", action="store_true", help="Print report JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else find_repo_root()
    report = run(root, max(1, args.limit))
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print_report(report)
    return 0 if report.staged_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
