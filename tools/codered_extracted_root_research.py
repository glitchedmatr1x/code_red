#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import string
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


CODE_RED_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = CODE_RED_ROOT.parent / "game" / "BACKUP BEFORE MODDING" / "rdr1" / "mods" / "root"
DEFAULT_OUT_DIR = CODE_RED_ROOT / "logs" / "extracted_root_research"

TEXT_EXTS = {
    ".xml",
    ".txt",
    ".csv",
    ".clist",
    ".xlist",
    ".list",
    ".cfg",
    ".mtl",
    ".fx",
    ".tune",
    ".weap",
    ".tr",
    ".cst",
    ".strtbl",
    ".stbl",
}

STRING_EXTS = {".cst", ".strtbl", ".stbl", ".txt", ".clist", ".xlist"}

CATEGORY_PATTERNS = {
    "vehicle_spawning": [
        "vehicle",
        "spawn",
        "traffic",
        "car",
        "truck",
        "wagon",
        "stagecoach",
        "train",
        "passenger",
        "locset",
        "template_vehicle",
        "gen_vehicle",
        "vehicle_generator",
        "ambient",
        "beacon",
    ],
    "cutscenes": [
        "cutscene",
        "cutbin",
        "cinematic",
        "cinvehicle",
        "camera",
        "intro_sequence",
        "intro_01",
    ],
    "gringos": [
        "gringo",
        "gringores",
        "commonscripts",
        "gringobrains",
        "multistagegringo",
    ],
    "strings": [
        "stringtable",
        "strings",
        "subtitle",
        "actor_names",
        "gringos-",
        "global.strtbl",
        ".cst",
        ".strtbl",
        ".stbl",
    ],
}

CONTENT_PATTERNS = sorted(
    set(
        CATEGORY_PATTERNS["vehicle_spawning"]
        + CATEGORY_PATTERNS["cutscenes"]
        + CATEGORY_PATTERNS["gringos"]
        + [
            "car01x",
            "truck01x",
            "locset_car01",
            "locset_truck01",
            "template_vehiclecar01",
            "template_vehicletruck01",
            "create_vehicle",
            "spawn_vehicle",
            "vehiclemodel",
            "vehiclespawn",
            "traincar",
        ]
    ),
    key=len,
    reverse=True,
)

ACTOR_ATTR_RE = re.compile(r'<actor\s+([^>]+)>', re.I)
ATTR_RE = re.compile(r'([A-Za-z0-9_:-]+)="([^"]*)"')
PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")


@dataclass
class FileFinding:
    categories: list[str]
    path: str
    relative_path: str
    name: str
    extension: str
    size: int
    sha1: str
    match_reasons: list[str]
    matched_terms: list[str]
    line_hits: list[dict]
    strings_sample: list[str]
    metadata: dict


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_probably_text(data: bytes) -> bool:
    if not data:
        return True
    if b"\x00" in data[:4096] and not data[:4096].startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    printable = set(bytes(string.printable, "ascii"))
    sample = data[:4096]
    score = sum(1 for b in sample if b in printable or b in b"\r\n\t")
    return score / max(1, len(sample)) > 0.80


def decode_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def extract_ascii_strings(data: bytes, limit: int = 80) -> list[str]:
    sample: list[str] = []
    seen: set[str] = set()
    for match in PRINTABLE_RE.finditer(data):
        text = match.group(0).decode("latin-1", "replace").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        sample.append(text)
        if len(sample) >= limit:
            break
    return sample


def categorize(path: Path, rel: str, data: bytes | None, text: str | None) -> tuple[list[str], list[str], list[str]]:
    rel_lower = rel.lower()
    name_lower = path.name.lower()
    path_parts = [part.lower() for part in path.parts]
    is_stringtable = "stringtable" in path_parts or path.suffix.lower() in {".cst", ".strtbl", ".stbl"}

    haystacks = [rel_lower, name_lower]
    if text:
        # String tables are useful as string assets, but their full text is too
        # broad for category matching and makes every generic word look relevant.
        haystacks.append("" if is_stringtable else text[:250000].lower())
    combined = "\n".join(haystacks)
    categories: set[str] = set()
    reasons: list[str] = []
    terms: set[str] = set()

    for category, pats in CATEGORY_PATTERNS.items():
        for pat in pats:
            if pat.lower() in combined:
                categories.add(category)
                terms.add(pat)
                reasons.append(f"{category}:{pat}")

    suffix = path.suffix.lower()
    if suffix in STRING_EXTS or "stringtable" in path_parts:
        categories.add("strings")
        reasons.append("strings:string_extension_or_folder")
    if (
        "camera" in path_parts
        or "cutscene" in path_parts
        or suffix == ".cutbin"
        or any(term in rel_lower for term in ("cutscene", "cinvehicle", "cinematic", "intro_sequence", "intro_01"))
    ):
        categories.add("cutscenes")
        reasons.append("cutscenes:strong_path_or_extension")
    elif "cutscenes" in categories and not any(
        term in combined for term in ("cutscene", "cinvehicle", "cinematic", "intro_sequence", "intro_01")
    ):
        categories.discard("cutscenes")
        reasons = [r for r in reasons if not r.startswith("cutscenes:")]
    if "gringo" in combined or "gringores" in path_parts:
        categories.add("gringos")
        reasons.append("gringos:path_or_name")
    if suffix in {".cft", ".cfd", ".ctd", ".cnm"} and any(t in combined for t in ("car", "truck", "wagon", "train", "vehicle")):
        categories.add("vehicle_spawning")
        reasons.append("vehicle_spawning:model_or_nav_resource_name")

    return sorted(categories), sorted(set(reasons)), sorted(terms)


def line_hits(text: str, limit: int = 25) -> list[dict]:
    if not text:
        return []
    pattern = re.compile("|".join(re.escape(term) for term in CONTENT_PATTERNS), re.I)
    hits: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if pattern.search(line):
            hits.append({"line": line_no, "text": line.strip()[:500]})
            if len(hits) >= limit:
                break
    return hits


def parse_attrs(attr_text: str) -> dict:
    return {key: value for key, value in ATTR_RE.findall(attr_text)}


def xml_metadata(text: str) -> dict:
    metadata: dict = {}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        actor = ACTOR_ATTR_RE.search(text)
        if actor:
            metadata["actor"] = parse_attrs(actor.group(1))
        values = {}
        for key in (
            "VehicleType",
            "LocationSetName",
            "VehicleFaction",
            "m_CinematicShotList",
            "m_BoomCameraTuningName",
            "m_GameCameraPassengerArcOverrideName",
        ):
            vals = re.findall(rf"<{re.escape(key)}\b([^>]*)/?>", text, re.I)
            if vals:
                values[key] = [parse_attrs(v) or v.strip() for v in vals]
        if values:
            metadata["picked_values"] = values
        return metadata

    metadata["root_tag"] = root.tag
    if root.tag == "actor":
        metadata["actor"] = dict(root.attrib)
    picked: dict[str, list] = defaultdict(list)
    names: set[str] = set()
    locators: set[str] = set()
    for elem in root.iter():
        if elem.tag in {
            "VehicleType",
            "LocationSetName",
            "VehicleFaction",
            "m_CinematicShotList",
            "m_BoomCameraTuningName",
            "m_GameCameraPassengerArcOverrideName",
            "m_GameCameraPassengerHolsteredArcOverrideName",
            "m_GameCameraPassengerZoomArcOverrideName",
            "Mass",
            "MaxHorsePower",
            "HighGearMPH",
            "SSSValue",
            "SSSThreshold",
            "AutoReverseSpeed",
        }:
            picked[elem.tag].append(dict(elem.attrib) if elem.attrib else (elem.text or "").strip())
        if elem.tag == "Name" and (elem.text or "").strip():
            names.add((elem.text or "").strip())
        if elem.tag in {"AttachmentLocator", "Target"} and (elem.text or "").strip():
            locators.add((elem.text or "").strip())
    if picked:
        metadata["picked_values"] = dict(picked)
    if names:
        metadata["names"] = sorted(names)[:80]
    if locators:
        metadata["locators"] = sorted(locators)[:80]
    return metadata


def script_metadata(text: str, strings_sample: list[str]) -> dict:
    metadata: dict = {}
    interesting = [s for s in strings_sample if re.search(r"vehicle|spawn|gringo|cutscene|car|truck|wagon|train", s, re.I)]
    if interesting:
        metadata["interesting_strings"] = interesting[:40]
    tokens = sorted(set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b", text[:300000])))
    selected = [t for t in tokens if re.search(r"vehicle|spawn|gringo|cutscene|camera|train|wagon|car|truck", t, re.I)]
    if selected:
        metadata["interesting_tokens"] = selected[:80]
    return metadata


def metadata_for(path: Path, text: str | None, strings_sample: list[str]) -> dict:
    suffix = path.suffix.lower()
    metadata: dict = {}
    if text and ("<" in text[:200] or suffix == ".xml"):
        metadata.update(xml_metadata(text))
    if text and (suffix in {".csc", ".wsc", ".txt", ".cst", ".strtbl", ".stbl"} or "scripting" in str(path).lower()):
        metadata.update(script_metadata(text, strings_sample))
    if suffix in {".cst", ".strtbl", ".stbl"}:
        metadata["string_sample_count"] = len(strings_sample)
        metadata["string_samples"] = strings_sample[:40]
    return metadata


def scan_root(root: Path) -> tuple[list[FileFinding], dict]:
    findings: list[FileFinding] = []
    ext_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    total_files = 0
    total_bytes = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        total_files += 1
        try:
            stat = path.stat()
            data = path.read_bytes()
        except OSError:
            continue
        total_bytes += stat.st_size
        ext_counts[path.suffix.lower() or "<none>"] += 1
        rel = str(path.relative_to(root))
        text = decode_text(data) if path.suffix.lower() in TEXT_EXTS or is_probably_text(data) else None
        strings_sample = extract_ascii_strings(data)
        categories, reasons, terms = categorize(path, rel, data, text)
        if not categories:
            continue
        for category in categories:
            category_counts[category] += 1
        findings.append(
            FileFinding(
                categories=categories,
                path=str(path),
                relative_path=rel,
                name=path.name,
                extension=path.suffix.lower() or "<none>",
                size=stat.st_size,
                sha1=hashlib.sha1(data).hexdigest(),
                match_reasons=reasons,
                matched_terms=terms,
                line_hits=line_hits(text or ""),
                strings_sample=strings_sample[:40],
                metadata=metadata_for(path, text, strings_sample),
            )
        )

    summary = {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "extension_counts": dict(ext_counts.most_common()),
        "category_counts": dict(category_counts.most_common()),
    }
    return sorted(findings, key=lambda f: (",".join(f.categories), f.relative_path.lower())), summary


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(report: dict) -> str:
    lines = [
        "# Extracted Root Research Inventory",
        "",
        f"Generated: {report['generated_at']}",
        f"Root: `{report['root']}`",
        "",
        "## Summary",
        "",
        f"- Files scanned: {report['summary']['total_files']}",
        f"- Matching files logged: {len(report['findings'])}",
        f"- Category counts: {json.dumps(report['summary']['category_counts'], sort_keys=True)}",
        "",
        "## Category Highlights",
        "",
    ]
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for row in report["findings"]:
        for category in row["categories"]:
            by_cat[category].append(row)
    for category in ("vehicle_spawning", "cutscenes", "gringos", "strings"):
        rows = by_cat.get(category, [])
        lines.append(f"### {category}")
        lines.append("")
        lines.append(f"- Matches: {len(rows)}")
        for row in rows[:30]:
            terms = ", ".join(row["matched_terms"][:5])
            lines.append(f"- `{row['relative_path']}` ({row['extension']}, {row['size']} bytes) terms: {terms}")
        lines.append("")
    lines.extend(
        [
            "## Output Files",
            "",
            "- `extracted_root_research.json`: full metadata with line hits and samples.",
            "- `extracted_root_findings.csv`: flat file-level inventory.",
            "- `category_counts.csv`: count by category.",
            "- `extension_counts.csv`: count by extension across the scanned root.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan an extracted RDR root folder for vehicle spawning, cutscenes, gringos, and strings research metadata.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Extracted root folder to scan.")
    parser.add_argument("--outdir", default=str(DEFAULT_OUT_DIR), help="Report output directory.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Root folder does not exist: {root}")
    findings, summary = scan_root(root)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "summary": summary,
        "findings": [asdict(f) for f in findings],
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "extracted_root_research.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (outdir / "extracted_root_research.md").write_text(render_markdown(report), encoding="utf-8")
    write_csv(
        outdir / "extracted_root_findings.csv",
        [
            {
                **asdict(f),
                "categories": ";".join(f.categories),
                "match_reasons": ";".join(f.match_reasons),
                "matched_terms": ";".join(f.matched_terms),
                "line_hits": json.dumps(f.line_hits, ensure_ascii=False),
                "strings_sample": json.dumps(f.strings_sample, ensure_ascii=False),
                "metadata": json.dumps(f.metadata, ensure_ascii=False),
            }
            for f in findings
        ],
        [
            "categories",
            "relative_path",
            "path",
            "name",
            "extension",
            "size",
            "sha1",
            "match_reasons",
            "matched_terms",
            "line_hits",
            "strings_sample",
            "metadata",
        ],
    )
    write_csv(
        outdir / "category_counts.csv",
        [{"category": k, "count": v} for k, v in summary["category_counts"].items()],
        ["category", "count"],
    )
    write_csv(
        outdir / "extension_counts.csv",
        [{"extension": k, "count": v} for k, v in summary["extension_counts"].items()],
        ["extension", "count"],
    )
    flat_rows = [
        {
            **asdict(f),
            "categories": ";".join(f.categories),
            "match_reasons": ";".join(f.match_reasons),
            "matched_terms": ";".join(f.matched_terms),
            "line_hits": json.dumps(f.line_hits, ensure_ascii=False),
            "strings_sample": json.dumps(f.strings_sample, ensure_ascii=False),
            "metadata": json.dumps(f.metadata, ensure_ascii=False),
        }
        for f in findings
    ]
    for category in ("vehicle_spawning", "cutscenes", "gringos", "strings"):
        write_csv(
            outdir / f"{category}_findings.csv",
            [row for row in flat_rows if category in row["categories"].split(";")],
            [
                "categories",
                "relative_path",
                "path",
                "name",
                "extension",
                "size",
                "sha1",
                "match_reasons",
                "matched_terms",
                "line_hits",
                "strings_sample",
                "metadata",
            ],
        )
    print(f"Wrote {outdir / 'extracted_root_research.json'}")
    print(f"Wrote {outdir / 'extracted_root_research.md'}")
    print(f"Wrote {outdir / 'extracted_root_findings.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
