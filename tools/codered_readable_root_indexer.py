#!/usr/bin/env python3
"""Build an AI-readable index for extracted RPF root folders.

The scanner is read-only against game data. It writes research artifacts under
Code_RED so later Code RED agents can jump directly to interesting readable
files, snippets, categories, and duplicate groups.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import string
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


CODE_RED_ROOT = Path(__file__).resolve().parents[1]
RED_DEAD_ROOT = CODE_RED_ROOT.parent
DEFAULT_OUT_DIR = CODE_RED_ROOT / "research - Scan" / "IMPORTANT_readable_root_index_2026-05-02"
DEFAULT_LOG_NOTE = CODE_RED_ROOT / "logs" / "IMPORTANT_CodeRED_Readable_Root_Index_2026-05-02.md"

TEXT_EXTS = {
    ".xml", ".txt", ".csv", ".cfg", ".ini", ".list", ".clist", ".xlist",
    ".tr", ".mtl", ".fx", ".weap", ".tune", ".cst", ".strtbl", ".stbl",
    ".cat", ".json", ".sc", ".dat",
}

STRING_SCAN_EXTS = {
    ".csc", ".wsc", ".cutbin", ".ctb", ".cft", ".cfd", ".ctd", ".cnm",
    ".csp", ".csg", ".cedt", ".cas", ".cvd", ".csf", ".sco", "",
}

CATEGORY_TERMS: dict[str, dict[str, int]] = {
    "vehicle_spawning": {
        "vehicle": 4, "spawn": 4, "vehiclespawn": 8, "spawn_vehicle": 8,
        "create_vehicle": 8, "vehicle_generator": 10, "gen_vehicle": 8,
        "playercar": 8, "car_gringo": 8, "car01x": 10, "truck01x": 10,
        "wagon": 4, "stagecoach": 4, "traincar": 6, "traffic": 5,
        "locset": 5, "template_vehicle": 8,
    },
    "npc_ai_factions": {
        "faction": 5, "factionrelations": 12, "lawenforcement": 8,
        "lawful": 5, "hostile": 4, "enemy": 3, "ally": 3, "friendly": 3,
        "companion": 6, "follow_actor": 8, "task_follow_actor": 9,
        "guard": 4, "posse": 5, "bounty": 4, "bandito": 5,
        "criminal": 5, "cattlerustler": 5, "indianraider": 5,
    },
    "gringos_scripts": {
        "gringo": 8, "gringores": 10, "multistagegringo": 9,
        "commonscripts": 5, "gringobrains": 6, "brain": 3,
        "use_gringo": 7, "gringoanim": 6,
    },
    "cutscenes_cameras": {
        "cutscene": 8, "cutbin": 8, "camera": 4, "cinematic": 5,
        "cinvehicle": 10, "intro_sequence": 7, "intro_01": 7,
        "subtitle": 4, "shot": 3, "cam": 3,
    },
    "strings_ui_text": {
        "stringtable": 8, "strings": 5, "strtbl": 6, "subtitle": 5,
        "actor_names": 6, "global.strtbl": 8, "hud": 3, "menu": 3,
        "frontend": 3,
    },
    "multiplayer_scripts": {
        "multiplayer": 9, "freemode": 10, "mp_idle": 10,
        "multiplayer_system_thread": 12, "multiplayer_update_thread": 12,
        "deathmatch": 8, "ctf": 7, "net": 3, "systemlink": 9,
        "session": 4,
    },
    "world_nav_placement": {
        "wilderness": 5, "placement": 5, "world": 3, "nav": 4,
        "wnm": 5, "terrain": 4, "region": 4, "sector": 3,
        "ambient": 4, "population": 5, "traffic": 5,
    },
    "model_resource_refs": {
        "fragment": 4, "texture": 3, "model": 3, ".wft": 8, ".wtd": 8,
        ".wedt": 8, ".wtb": 6, ".wsi": 8, ".wvd": 6,
    },
}

IMPORTANT_NAME_TERMS = (
    "factionrelations", "tasks.tr", "human_guard", "game_main", "squad",
    "vehicle_generator", "playercar", "car_gringo", "companion_brain",
    "freemode", "multiplayer_system_thread", "multiplayer_update_thread",
    "cinvehicle", "locset", "template_vehicle", "car01x", "truck01x",
)

PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")
TOKEN_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")


@dataclass
class RootInfo:
    root_id: str
    path: str
    file_count: int = 0
    readable_count: int = 0
    total_bytes: int = 0


@dataclass
class FileRow:
    root_id: str
    root_path: str
    relative_path: str
    absolute_path: str
    extension: str
    size: int
    sha1: str
    duplicate_of: str
    readable_mode: str
    categories: str
    important_score: int
    matched_terms: str
    snippet_count: int
    root_tag: str
    picked_tokens: str


@dataclass
class HitRow:
    root_id: str
    relative_path: str
    absolute_path: str
    category: str
    term: str
    line: int
    score: int
    snippet: str


def rel_to_base(path: Path) -> str:
    try:
        return str(path.relative_to(RED_DEAD_ROOT))
    except ValueError:
        return str(path)


def discover_roots(base: Path) -> list[Path]:
    roots: list[Path] = []
    for path in base.rglob("*"):
        if path.is_dir() and path.name.lower() == "root":
            if any(part in {".git", "__pycache__"} for part in path.parts):
                continue
            roots.append(path)
    return sorted(set(roots), key=lambda p: str(p).lower())


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def is_probably_text(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:8192]
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    if b"\x00" in sample:
        return False
    printable = set(bytes(string.printable, "ascii"))
    score = sum(1 for b in sample if b in printable or b in b"\r\n\t")
    return score / max(1, len(sample)) > 0.82


def decode_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def extract_strings(data: bytes, limit: int = 3000) -> list[str]:
    seen: set[str] = set()
    strings: list[str] = []
    for match in PRINTABLE_RE.finditer(data):
        value = match.group(0).decode("latin-1", "replace").strip()
        if value and value not in seen:
            seen.add(value)
            strings.append(value)
        if len(strings) >= limit:
            break
    return strings


def readable_payload(path: Path, data: bytes) -> tuple[str, str, list[str]]:
    ext = path.suffix.lower()
    if ext in TEXT_EXTS or is_probably_text(data):
        text = decode_text(data)
        return "text", text, []
    if ext in STRING_SCAN_EXTS:
        strings = extract_strings(data)
        if strings:
            return "strings", "\n".join(strings), strings
    return "binary_skip", "", []


def terms_for_text(text: str, rel: str) -> tuple[dict[str, int], dict[str, set[str]]]:
    haystack = f"{rel}\n{text[:500000]}".lower()
    scores: dict[str, int] = defaultdict(int)
    matched: dict[str, set[str]] = defaultdict(set)
    for category, weighted_terms in CATEGORY_TERMS.items():
        for term, weight in weighted_terms.items():
            if term.lower() in haystack:
                scores[category] += weight
                matched[category].add(term)
    return dict(scores), matched


def line_hits(text: str, rel: str, category_scores: dict[str, int], limit: int = 60) -> list[HitRow]:
    if not text or not category_scores:
        return []
    term_to_category: list[tuple[str, str, int]] = []
    for category in category_scores:
        for term, weight in CATEGORY_TERMS[category].items():
            term_to_category.append((term, category, weight))
    term_to_category.sort(key=lambda t: len(t[0]), reverse=True)
    pattern = re.compile("|".join(re.escape(t[0]) for t in term_to_category), re.I)
    weight_lookup = {(term.lower(), category): weight for term, category, weight in term_to_category}
    category_lookup: dict[str, list[str]] = defaultdict(list)
    for term, category, _weight in term_to_category:
        category_lookup[term.lower()].append(category)

    hits: list[HitRow] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        found = pattern.search(line)
        if not found:
            continue
        term = found.group(0)
        key = term.lower()
        categories = category_lookup.get(key, [])
        for category in categories[:2]:
            hits.append(
                HitRow("", rel, "", category, term, line_no,
                       weight_lookup.get((key, category), 1), line.strip()[:700])
            )
            if len(hits) >= limit:
                return hits
    return hits


def metadata_tokens(text: str) -> tuple[str, str]:
    root_tag = ""
    tag_match = re.search(r"<\s*([A-Za-z_][A-Za-z0-9_:-]*)\b", text[:4000])
    if tag_match:
        root_tag = tag_match.group(1)
    tokens = sorted({t for t in TOKEN_RE.findall(text[:250000]) if re.search(
        r"vehicle|spawn|gringo|cutscene|camera|faction|law|hostile|companion|multiplayer|freemode|wagon|train|car|truck|nav|terrain",
        t,
        re.I,
    )})
    return root_tag, "|".join(tokens[:80])


def score_file(rel: str, category_scores: dict[str, int], readable_mode: str, snippet_count: int) -> int:
    score = sum(category_scores.values()) + snippet_count
    rel_lower = rel.lower()
    for term in IMPORTANT_NAME_TERMS:
        if term in rel_lower:
            score += 25
    if readable_mode == "text":
        score += 3
    return score


def scan_roots(roots: list[Path]) -> dict:
    file_rows: list[FileRow] = []
    hit_rows: list[HitRow] = []
    root_infos: list[RootInfo] = []
    seen_sha1: dict[str, str] = {}
    category_counts: Counter[str] = Counter()
    extension_counts: Counter[str] = Counter()
    readable_modes: Counter[str] = Counter()
    duplicate_count = 0

    for idx, root in enumerate(roots, 1):
        root_id = f"root_{idx:02d}"
        info = RootInfo(root_id=root_id, path=str(root))
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()
                stat = path.stat()
            except OSError:
                continue
            info.file_count += 1
            info.total_bytes += stat.st_size
            ext = path.suffix.lower() or "<none>"
            extension_counts[ext] += 1
            rel = str(path.relative_to(root))
            mode, text, strings = readable_payload(path, data)
            readable_modes[mode] += 1
            if mode == "binary_skip":
                continue
            info.readable_count += 1
            digest = sha1_bytes(data)
            duplicate_of = seen_sha1.get(digest, "")
            if duplicate_of:
                duplicate_count += 1
            else:
                seen_sha1[digest] = f"{root_id}:{rel}"
            category_scores, matched = terms_for_text(text, rel)
            for category in category_scores:
                category_counts[category] += 1
            hits = line_hits(text, rel, category_scores)
            for hit in hits:
                hit.root_id = root_id
                hit.absolute_path = str(path)
                hit_rows.append(hit)
            root_tag, picked_tokens = metadata_tokens(text)
            score = score_file(rel, category_scores, mode, len(hits))
            file_rows.append(
                FileRow(
                    root_id=root_id,
                    root_path=str(root),
                    relative_path=rel,
                    absolute_path=str(path),
                    extension=ext,
                    size=stat.st_size,
                    sha1=digest,
                    duplicate_of=duplicate_of,
                    readable_mode=mode,
                    categories=";".join(sorted(category_scores)),
                    important_score=score,
                    matched_terms=";".join(sorted({t for terms in matched.values() for t in terms})),
                    snippet_count=len(hits),
                    root_tag=root_tag,
                    picked_tokens=picked_tokens,
                )
            )
        root_infos.append(info)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base": str(RED_DEAD_ROOT),
        "roots": [asdict(info) for info in root_infos],
        "summary": {
            "root_count": len(root_infos),
            "files_seen": sum(info.file_count for info in root_infos),
            "readable_files_indexed": len(file_rows),
            "interesting_files": sum(1 for row in file_rows if row.important_score > 0),
            "snippet_hits": len(hit_rows),
            "duplicate_readable_files": duplicate_count,
            "category_counts": dict(category_counts.most_common()),
            "extension_counts": dict(extension_counts.most_common()),
            "readable_modes": dict(readable_modes.most_common()),
        },
        "files": [asdict(row) for row in sorted(file_rows, key=lambda r: (-r.important_score, r.relative_path.lower()))],
        "hits": [asdict(row) for row in sorted(hit_rows, key=lambda r: (r.category, r.relative_path.lower(), r.line))],
    }


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# IMPORTANT - Readable Extracted RPF Root Index",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Why This Matters",
        "",
        "This is the current AI-readable entry point for readable files found in extracted `root` folders under the Red Dead workspace. Use it before broad manual searching.",
        "",
        "## Roots Scanned",
        "",
    ]
    for root in report["roots"]:
        lines.append(f"- `{root['root_id']}` `{root['path']}` - files: {root['file_count']}, readable indexed: {root['readable_count']}")
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Root folders scanned: {summary['root_count']}",
        f"- Files seen: {summary['files_seen']}",
        f"- Readable files indexed: {summary['readable_files_indexed']}",
        f"- Interesting files: {summary['interesting_files']}",
        f"- Snippet hits: {summary['snippet_hits']}",
        f"- Duplicate readable files: {summary['duplicate_readable_files']}",
        f"- Category counts: `{json.dumps(summary['category_counts'], sort_keys=True)}`",
        "",
        "## Highest Priority Files",
        "",
    ])
    important = [row for row in report["files"] if row["important_score"] > 0][:80]
    for row in important:
        cats = row["categories"] or "uncategorized"
        terms = row["matched_terms"][:120]
        lines.append(f"- score {row['important_score']:>3} `{row['root_id']}:{row['relative_path']}` [{cats}] terms: {terms}")
    lines.extend([
        "",
        "## AI Lookup Files",
        "",
        "- `ai_readable_root_index.md` - this important human/AI entry point.",
        "- `ai_readable_root_index.json` - full structured index without full file bodies.",
        "- `root_manifest.csv` - roots scanned and readable counts.",
        "- `file_index.csv` - every readable indexed file, duplicate marker, score, categories, tokens.",
        "- `important_files.csv` - high-score files sorted for quick triage.",
        "- `snippet_hits.csv` - line/string snippets by category and term.",
        "- `categories/*.csv` - per-category file slices.",
        "",
        "## Category Guidance",
        "",
        "- `vehicle_spawning`: vehicle templates, locsets, traffic, car/truck/wagon/train leads.",
        "- `npc_ai_factions`: factions, hostility, lawmen, gangs, companion/follow behavior.",
        "- `gringos_scripts`: gringo scripts/resources and interaction brain leads.",
        "- `cutscenes_cameras`: cutscene bins, cinematic camera files, vehicle camera shots.",
        "- `strings_ui_text`: stringtables, subtitles, UI/menu text, actor names.",
        "- `multiplayer_scripts`: freemode, MP threads, session/system-link-adjacent leads.",
        "- `world_nav_placement`: nav, terrain, region, placement, ambient/population leads.",
        "- `model_resource_refs`: readable references to models/textures/fragments/resources.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(report: dict, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "ai_readable_root_index.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (outdir / "ai_readable_root_index.md").write_text(render_markdown(report), encoding="utf-8")

    write_csv(outdir / "root_manifest.csv", report["roots"], ["root_id", "path", "file_count", "readable_count", "total_bytes"])
    file_fields = list(FileRow.__dataclass_fields__.keys())
    hit_fields = list(HitRow.__dataclass_fields__.keys())
    write_csv(outdir / "file_index.csv", report["files"], file_fields)
    write_csv(outdir / "snippet_hits.csv", report["hits"], hit_fields)
    write_csv(outdir / "important_files.csv", [r for r in report["files"] if r["important_score"] > 0], file_fields)

    categories_dir = outdir / "categories"
    categories_dir.mkdir(exist_ok=True)
    for category in CATEGORY_TERMS:
        rows = [row for row in report["files"] if category in row["categories"].split(";")]
        write_csv(categories_dir / f"{category}.csv", rows, file_fields)
    write_csv(
        outdir / "category_counts.csv",
        [{"category": k, "count": v} for k, v in report["summary"]["category_counts"].items()],
        ["category", "count"],
    )
    write_csv(
        outdir / "extension_counts.csv",
        [{"extension": k, "count": v} for k, v in report["summary"]["extension_counts"].items()],
        ["extension", "count"],
    )


def write_log_note(report: dict, log_note: Path, outdir: Path) -> None:
    summary = report["summary"]
    lines = [
        "# IMPORTANT - CodeRED Readable Root Index",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "This pass scanned every discovered extracted `root` folder under the Red Dead workspace and indexed readable/text-bearing files for AI lookup.",
        "",
        "## Output",
        "",
        f"- Main report: `research - Scan/{outdir.name}/ai_readable_root_index.md`",
        f"- File index: `research - Scan/{outdir.name}/file_index.csv`",
        f"- Important files: `research - Scan/{outdir.name}/important_files.csv`",
        f"- Snippet hits: `research - Scan/{outdir.name}/snippet_hits.csv`",
        "",
        "## Counts",
        "",
        f"- Roots scanned: {summary['root_count']}",
        f"- Files seen: {summary['files_seen']}",
        f"- Readable indexed: {summary['readable_files_indexed']}",
        f"- Interesting files: {summary['interesting_files']}",
        f"- Snippet hits: {summary['snippet_hits']}",
        "",
        "## Important Categories",
        "",
    ]
    for category, count in summary["category_counts"].items():
        lines.append(f"- `{category}`: {count}")
    log_note.parent.mkdir(parents=True, exist_ok=True)
    log_note.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Index readable files from every extracted RPF root folder.")
    parser.add_argument("--base", type=Path, default=RED_DEAD_ROOT)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--log-note", type=Path, default=DEFAULT_LOG_NOTE)
    parser.add_argument("--root", action="append", type=Path, help="Specific root folder. Can be passed multiple times.")
    args = parser.parse_args()

    roots = args.root or discover_roots(args.base)
    roots = [root.resolve() for root in roots if root.exists()]
    if not roots:
        raise SystemExit("No root folders found")
    report = scan_roots(roots)
    write_outputs(report, args.outdir)
    write_log_note(report, args.log_note, args.outdir)
    print(f"Roots scanned: {report['summary']['root_count']}")
    print(f"Files seen: {report['summary']['files_seen']}")
    print(f"Readable indexed: {report['summary']['readable_files_indexed']}")
    print(f"Interesting files: {report['summary']['interesting_files']}")
    print(f"Snippet hits: {report['summary']['snippet_hits']}")
    print(f"Output: {args.outdir}")
    print(f"Log note: {args.log_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
