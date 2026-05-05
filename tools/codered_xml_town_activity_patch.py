#!/usr/bin/env python3
"""Code RED XML town activity patcher.

Local-only. No GitHub, no script compiling, no ASI/menu spawning, no source RPF mutation.

This builds a patched candidate from the Code RED placementglobals XML by cloning
proven Code RED Blackwater/Thieves Landing event placement blocks across other
town regions while explicitly excluding MacFarlane's Ranch.

It writes output under:
  scratch/faction_wars/xml_town_activity_pass
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

VERSION = "1.0.0-town-activity-clone-pass"
DEFAULT_SOURCE = Path("research/modified_xml/placementglobals_15_50_rival_gang_towns.xml")
OUT_DIR = Path("scratch/faction_wars/xml_town_activity_pass")
OUT_XML = OUT_DIR / "placementglobals_all_towns_except_macfarlane.xml"
SOURCE_COPY = OUT_DIR / "source_original_copy.xml"
REPORT_MD = OUT_DIR / "TOWN_ACTIVITY_PATCH_REPORT.md"
REPORT_JSON = OUT_DIR / "town_activity_patch_report.json"
DIFF_TXT = OUT_DIR / "placementglobals_town_activity.diff.txt"

# Town labels to activate/extend. MacFarlane is intentionally absent.
ALL_TOWN_TARGETS = (
    "Armadillo",
    "Tumbleweed",
    "Chuparosa",
    "Escalera",
    "Manzanita",
    "Plainview",
    "Rathskeller Fork",
    "Ridgewood Farm",
    "Rio Bravo",
    "Gaptooth Ridge",
    "Fort Mercer",
    "Tall Trees",
    "Nuevo Paraiso",
)

# Higher chaos/robbery pressure should be kept to outlaw/frontier-heavy places.
OUTLAW_TOWN_TARGETS = (
    "Armadillo",
    "Tumbleweed",
    "Chuparosa",
    "Escalera",
    "Gaptooth Ridge",
    "Fort Mercer",
    "Rio Bravo",
)

MACFARLANE_PATTERNS = (
    "macfarlane",
    "macfarlanes",
    "macfarlane's",
    "mcfarlane",
)

TEMPLATES = {
    "main_roads": "CodeRED Blackwater Chaos Main Roads",
    "chaos_events": "CodeRed Thieves Landing Chaos Events",
    "posse_robbery": "CodeRed Thieves Landing Posse Robbery Events",
}


@dataclass
class CloneRecord:
    template_key: str
    template_name: str
    new_name: str
    town: str


@dataclass
class PatchReport:
    version: str
    generated_utc: str
    root: str
    source: str
    source_copy: str
    output_xml: str
    diff: str
    mode: str
    towns_targeted: list[str]
    outlaw_towns_targeted: list[str]
    clones_created: int
    clones: list[dict]
    existing_code_red_blocks: list[str]
    skipped_existing: list[str]
    macfarlane_excluded: bool
    validation: dict
    notes: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "main.py").exists() or (candidate / "python_workbench.py").exists() or (candidate / "research").exists():
            return candidate
    return here


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def has_macfarlane(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in MACFARLANE_PATTERNS)


def direct_name(item: ET.Element) -> str:
    name = item.find("Name")
    if name is None or name.text is None:
        return ""
    return name.text.strip()


def find_events(root: ET.Element) -> ET.Element:
    events = root.find("Events")
    if events is None:
        events = root.find(".//Events")
    if events is None:
        raise ValueError("Could not find <Events> in placementglobals XML")
    return events


def find_template_items(events: ET.Element) -> dict[str, ET.Element]:
    found: dict[str, ET.Element] = {}
    wanted = {key: normalize(value) for key, value in TEMPLATES.items()}
    for item in list(events):
        if item.tag != "Item":
            continue
        name = normalize(direct_name(item))
        for key, wanted_name in wanted.items():
            if name == wanted_name:
                found[key] = item
    missing = [TEMPLATES[key] for key in TEMPLATES if key not in found]
    if missing:
        raise ValueError("Missing template block(s): " + ", ".join(missing))
    return found


def all_existing_names(events: ET.Element) -> set[str]:
    names: set[str] = set()
    for item in list(events):
        if item.tag == "Item":
            name = direct_name(item)
            if name:
                names.add(normalize(name))
    return names


def rename_clone(element: ET.Element, new_name: str) -> ET.Element:
    cloned = copy.deepcopy(element)
    name = cloned.find("Name")
    if name is None:
        name = ET.Element("Name")
        cloned.insert(0, name)
    name.text = new_name
    return cloned


def plan_clones(mode: str) -> list[tuple[str, str, Iterable[str]]]:
    plan: list[tuple[str, str, Iterable[str]]] = []
    # Conservative: one proven main-road chaos block for every non-MacFarlane target.
    plan.append(("main_roads", "CodeRED {town} Chaos Main Roads", ALL_TOWN_TARGETS))
    if mode in {"balanced", "aggressive"}:
        plan.append(("chaos_events", "CodeRED {town} Chaos Events", OUTLAW_TOWN_TARGETS))
    if mode == "aggressive":
        plan.append(("posse_robbery", "CodeRED {town} Posse Robbery Events", OUTLAW_TOWN_TARGETS))
    return plan


def collect_code_red_blocks(events: ET.Element) -> list[str]:
    blocks: list[str] = []
    for item in list(events):
        if item.tag != "Item":
            continue
        name = direct_name(item)
        if "codered" in name.lower() or "code red" in name.lower():
            blocks.append(name)
    return blocks


def write_xml(tree: ET.ElementTree, path: Path) -> None:
    try:
        ET.indent(tree, space="  ")
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def make_diff(original: str, patched: str) -> str:
    original_lines = original.splitlines(keepends=True)
    patched_lines = patched.splitlines(keepends=True)
    return "".join(difflib.unified_diff(original_lines, patched_lines, fromfile="source", tofile="patched"))


def validate_output(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    validation = {
        "xml_parse_ok": False,
        "macfarlane_created": False,
        "town_name_counts": {},
    }
    ET.parse(path)
    validation["xml_parse_ok"] = True
    lower = text.lower()
    validation["macfarlane_created"] = "codered macfarlane" in lower or "codered mcfarlane" in lower
    for town in ALL_TOWN_TARGETS:
        validation["town_name_counts"][town] = lower.count(town.lower())
    return validation


def run(root: Path, source: Path, mode: str) -> PatchReport:
    root = root.resolve()
    source_path = source if source.is_absolute() else root / source
    if not source_path.exists():
        raise FileNotFoundError(f"Missing placementglobals XML: {source_path}")

    out_dir = root / OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    source_copy = root / SOURCE_COPY
    output_xml = root / OUT_XML
    diff_path = root / DIFF_TXT

    original_text = source_path.read_text(encoding="utf-8", errors="ignore")
    source_copy.write_text(original_text, encoding="utf-8")

    tree = ET.parse(source_path)
    root_el = tree.getroot()
    events = find_events(root_el)
    templates = find_template_items(events)
    existing_names = all_existing_names(events)
    existing_code_red_blocks = collect_code_red_blocks(events)

    clones: list[CloneRecord] = []
    skipped_existing: list[str] = []
    for template_key, name_pattern, towns in plan_clones(mode):
        template = templates[template_key]
        for town in towns:
            if has_macfarlane(town):
                continue
            new_name = name_pattern.format(town=town)
            if normalize(new_name) in existing_names:
                skipped_existing.append(new_name)
                continue
            events.append(rename_clone(template, new_name))
            existing_names.add(normalize(new_name))
            clones.append(CloneRecord(template_key, TEMPLATES[template_key], new_name, town))

    write_xml(tree, output_xml)
    patched_text = output_xml.read_text(encoding="utf-8", errors="ignore")
    diff_path.write_text(make_diff(original_text, patched_text), encoding="utf-8")
    validation = validate_output(output_xml)

    report = PatchReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        source=rel_to(source_path, root),
        source_copy=rel_to(source_copy, root),
        output_xml=rel_to(output_xml, root),
        diff=rel_to(diff_path, root),
        mode=mode,
        towns_targeted=list(ALL_TOWN_TARGETS),
        outlaw_towns_targeted=list(OUTLAW_TOWN_TARGETS),
        clones_created=len(clones),
        clones=[asdict(item) for item in clones],
        existing_code_red_blocks=existing_code_red_blocks,
        skipped_existing=skipped_existing,
        macfarlane_excluded=not validation.get("macfarlane_created", False),
        validation=validation,
        notes=[
            "Candidate only: source XML and RPF archives were not modified.",
            "MacFarlane's Ranch is intentionally excluded.",
            "This clones proven Code RED placement blocks; review the diff before archive patching.",
            "Use conservative first if balanced/aggressive feels too dense in game.",
        ],
    )
    (root / REPORT_JSON).write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    (root / REPORT_MD).write_text(build_markdown(report), encoding="utf-8")
    return report


def build_markdown(report: PatchReport) -> str:
    lines = [
        "# Code RED Town Activity XML Patch Report",
        "",
        f"Generated: `{report.generated_utc}`",
        f"Version: `{report.version}`",
        "",
        "## Summary",
        "",
        f"- Source: `{report.source}`",
        f"- Output XML: `{report.output_xml}`",
        f"- Diff: `{report.diff}`",
        f"- Mode: `{report.mode}`",
        f"- Clones created: `{report.clones_created}`",
        f"- MacFarlane excluded: `{report.macfarlane_excluded}`",
        "",
        "## Existing Code RED blocks found",
        "",
    ]
    for name in report.existing_code_red_blocks:
        lines.append(f"- {name}")
    lines.extend(["", "## New cloned town blocks", "", "| Town | New block | Template |", "|---|---|---|"])
    for item in report.clones:
        lines.append(f"| {item['town']} | `{item['new_name']}` | `{item['template_name']}` |")
    if report.skipped_existing:
        lines.extend(["", "## Skipped because already present", ""])
        lines.extend(f"- {name}" for name in report.skipped_existing)
    lines.extend([
        "",
        "## Validation",
        "",
        f"- XML parse OK: `{report.validation.get('xml_parse_ok')}`",
        f"- MacFarlane CodeRED block created: `{report.validation.get('macfarlane_created')}`",
        "",
        "## Next steps",
        "",
        "1. Open the diff and output XML.",
        "2. Do not install yet if the cloned blocks look too broad.",
        "3. Use copied-archive proof to patch the matching XML resource only after review.",
        "4. Test towns/roads before moving to behavior templates.",
    ])
    return "\n".join(lines) + "\n"


def print_report(report: PatchReport) -> None:
    print("# Code RED Town Activity XML Patch")
    print(f"Mode: {report.mode}")
    print(f"Clones created: {report.clones_created}")
    print(f"Output XML: {report.output_xml}")
    print(f"Diff: {report.diff}")
    print(f"Report: {rel_to(Path(report.root) / REPORT_MD, Path(report.root))}")
    print(f"MacFarlane excluded: {report.macfarlane_excluded}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clone proven Code RED town activity XML blocks across towns except MacFarlane.")
    parser.add_argument("--root", type=Path, default=None, help="Code_RED root folder. Defaults to current/repo root.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Placementglobals XML source path.")
    parser.add_argument("--mode", choices=("conservative", "balanced", "aggressive"), default="balanced", help="Clone intensity. Conservative = one main road block per town. Balanced adds chaos blocks for outlaw towns. Aggressive adds posse robbery clones too.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve() if args.root else find_root()
    report = run(root, args.source, args.mode)
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
