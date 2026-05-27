#!/usr/bin/env python3
"""Code RED MP runtime gate hunter.

This read-only tool looks for the next blockers after the copied MP content RPF
boots: menu/frontend/Flash gating, XLive/System Link/sign-in checks, session
routing, and script bootstrap references.

Typical flow:

    python tools/codered_mp_build_probe.py --extract-all-mp-csc
    python tools/codered_mp_gate_hunt.py \
      --source logs/content_mp_singleplayer_build_probe \
      --source logs/content_mp_singleplayer_build_probe/extracted_signals \
      --out logs/content_mp_gate_hunt

Optional broader scan:

    python tools/codered_mp_gate_hunt.py \
      --source logs/content_mp_singleplayer_build_probe \
      --source %RDR_GAME_DIR% \
      --out logs/content_mp_gate_hunt

It does not patch files, launch the game, or mutate archives.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = [
    ROOT / "logs" / "content_mp_singleplayer_build_probe",
    ROOT / "logs" / "content_mp_singleplayer_build_probe" / "extracted_signals",
    ROOT / "logs" / "freemode_csc_init_inspector",
]
DEFAULT_OUT = ROOT / "logs" / "content_mp_gate_hunt"
TEXT_EXTS = {".txt", ".csv", ".json", ".md", ".log", ".ini", ".xml"}
SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}
RESOURCE_EXTS = {".rpf", ".strtbl", ".wtd", ".wtx", ".swf", ".gfx", ".dat", ".bin", ".csc", ".sco", ".wsc", ".xsc", ".wsv"}
STRING_RE = re.compile(rb"[\x20-\x7e]{4,240}")

GATE_PATTERNS: dict[str, list[str]] = {
    "freemode_entry": [r"\bfreemode\b", r"free[_ -]?mode"],
    "multiplayer_menu": [r"multiplayer", r"multi[_ -]?player", r"mp_menu", r"menu_mp", r"frontend", r"mainmenu", r"pausemenu"],
    "xlive_gate": [r"xlive", r"x_live", r"live[_ -]?signin", r"signin", r"signed[_ -]?in", r"profile", r"gamertag", r"xbox"],
    "system_link_gate": [r"system[_ -]?link", r"syslink", r"lan", r"network[_ -]?session", r"private[_ -]?session"],
    "session_flow": [r"session", r"lobby", r"matchmaking", r"match[_ -]?make", r"join", r"host", r"client", r"peer", r"invite"],
    "script_bootstrap": [r"script", r"startup", r"bootstrap", r"register", r"load[_ -]?script", r"script[_ -]?loader", r"launch"],
    "spawn_enablement": [r"spawn", r"respawn", r"player[_ -]?spawn", r"safe[_ -]?spawn", r"weapon[_ -]?spawn"],
    "team_mode": [r"team", r"teamwin", r"teamlose", r"coop", r"co[_ -]?op", r"posse"],
    "graveyard_overrun": [r"graveyard", r"overrun", r"zombie", r"undead", r"wave", r"sudden[_ -]?death"],
    "ui_flash": [r"flash", r"scaleform", r"gfx", r"swf", r"button", r"label", r"frontend", r"hud", r"ui"],
}

CATEGORY_WEIGHTS = {
    "freemode_entry": 12,
    "multiplayer_menu": 10,
    "xlive_gate": 10,
    "system_link_gate": 9,
    "session_flow": 7,
    "script_bootstrap": 7,
    "ui_flash": 6,
    "spawn_enablement": 4,
    "team_mode": 3,
    "graveyard_overrun": 2,
}


@dataclass
class GateHit:
    path: str
    source_kind: str
    category: str
    value: str
    context: str
    offset: int | None
    line: int | None
    score: int


@dataclass
class FileScore:
    path: str
    extension: str
    source_kind: str
    size: int
    entropy_64k: float
    hit_count: int
    score: int
    categories: list[str]
    recommendation: str


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def clean(text: str | bytes, limit: int = 280) -> str:
    if isinstance(text, bytes):
        text = text.decode("utf-8", "ignore")
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()[:limit]


def categories_for(text: str) -> list[str]:
    return [category for category, patterns in GATE_PATTERNS.items() if any(re.search(pattern, text, re.I) for pattern in patterns)]


def iter_files(sources: Iterable[Path], max_bytes: int) -> Iterable[Path]:
    seen: set[str] = set()
    for source in sources:
        if not source.exists():
            continue
        files = [source] if source.is_file() else [p for p in source.rglob("*") if p.is_file()]
        for path in files:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            suffix = path.suffix.lower()
            if suffix not in TEXT_EXTS and suffix not in SCRIPT_EXTS and suffix not in RESOURCE_EXTS:
                continue
            try:
                if path.stat().st_size > max_bytes and suffix not in TEXT_EXTS:
                    continue
            except OSError:
                continue
            yield path


def source_kind(path: Path) -> str:
    low = str(path).lower().replace("\\", "/")
    if "/extracted_signals/" in low or path.suffix.lower() in SCRIPT_EXTS:
        return "script_or_extracted_payload"
    if "mp_build_probe" in low or path.suffix.lower() in {".json", ".csv", ".md", ".log"}:
        return "probe_or_report"
    if path.suffix.lower() in {".swf", ".gfx", ".wtd", ".wtx"}:
        return "ui_or_resource_candidate"
    if path.suffix.lower() == ".rpf":
        return "archive_candidate"
    return "file"


def inspect_text_file(path: Path) -> list[GateHit]:
    hits: list[GateHit] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return hits
    seen: set[tuple[str, str, int]] = set()
    for line_no, line in enumerate(lines, start=1):
        cats = categories_for(line)
        if not cats:
            continue
        context = clean(line)
        for cat in cats:
            key = (cat, context.lower(), line_no)
            if key in seen:
                continue
            seen.add(key)
            hits.append(GateHit(str(path), source_kind(path), cat, line.strip()[:240], context, None, line_no, CATEGORY_WEIGHTS.get(cat, 1)))
    return hits


def inspect_binary_strings(path: Path, max_read: int) -> list[GateHit]:
    hits: list[GateHit] = []
    try:
        data = path.read_bytes()[:max_read]
    except Exception:
        return hits
    seen: set[tuple[str, str]] = set()
    for match in STRING_RE.finditer(data):
        value = clean(match.group(0), 240)
        cats = categories_for(value)
        if not cats:
            continue
        context = clean(data[max(0, match.start() - 96):min(len(data), match.end() + 96)])
        for cat in cats:
            key = (cat, value.lower())
            if key in seen:
                continue
            seen.add(key)
            hits.append(GateHit(str(path), source_kind(path), cat, value, context, match.start(), None, CATEGORY_WEIGHTS.get(cat, 1)))
    return hits


def recommendation_for(categories: set[str]) -> str:
    if {"multiplayer_menu", "ui_flash"} & categories:
        return "inspect menu/frontend/UI gating; likely visibility or button route target"
    if {"xlive_gate", "system_link_gate"} & categories:
        return "inspect XLive/System Link/sign-in response gate before more content injection"
    if {"freemode_entry", "script_bootstrap", "session_flow"} & categories:
        return "inspect script startup/session route for freemode activation"
    if {"spawn_enablement", "team_mode"} & categories:
        return "use Menu Workshop or ScriptHook action to test runtime spawn/session actions"
    if "graveyard_overrun" in categories:
        return "MP/Undead mode content signal; lower priority unless targeting overrun directly"
    return "record as supporting signal"


def run_scan(sources: list[Path], out_dir: Path, max_file_bytes: int, max_read_bytes: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    hits: list[GateHit] = []
    file_scores: list[FileScore] = []
    for path in iter_files(sources, max_file_bytes):
        try:
            data_head = path.read_bytes()[:65536]
            size = path.stat().st_size
        except Exception:
            data_head = b""
            size = 0
        suffix = path.suffix.lower()
        if suffix in TEXT_EXTS:
            file_hits = inspect_text_file(path)
            if not file_hits:
                file_hits = inspect_binary_strings(path, max_read_bytes)
        else:
            file_hits = inspect_binary_strings(path, max_read_bytes)
        categories = sorted({hit.category for hit in file_hits})
        score = sum(hit.score for hit in file_hits)
        file_scores.append(
            FileScore(
                str(path),
                suffix,
                source_kind(path),
                size,
                round(entropy(data_head), 4),
                len(file_hits),
                score,
                categories,
                recommendation_for(set(categories)),
            )
        )
        hits.extend(file_hits)

    file_scores.sort(key=lambda row: (row.score, row.hit_count), reverse=True)
    hits.sort(key=lambda hit: (hit.score, hit.category), reverse=True)
    category_counts = Counter(hit.category for hit in hits)
    source_counts = Counter(hit.source_kind for hit in hits)
    recommendations = Counter(row.recommendation for row in file_scores if row.hit_count)
    strongest = [row for row in file_scores if row.hit_count][:50]

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": [str(s) for s in sources],
        "files_scanned": len(file_scores),
        "files_with_hits": sum(1 for row in file_scores if row.hit_count),
        "hit_count": len(hits),
        "category_counts": dict(category_counts),
        "source_kind_counts": dict(source_counts),
        "recommendation_counts": dict(recommendations),
        "top_recommendation": strongest[0].recommendation if strongest else "no gate signals found",
        "top_file": strongest[0].path if strongest else "",
        "next_actions": [
            "Open top menu/frontend/UI candidate files and look for MP button visibility gates.",
            "Search XLive/System Link/sign-in hits for branches that hide or disable multiplayer.",
            "Trace freemode/session/bootstrap hits to see what script or menu action should load freemode.csc.",
            "Use Menu Workshop for controlled runtime probes instead of more blind content injection.",
        ],
    }

    (out_dir / "mp_gate_hunt_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "mp_gate_hunt_hits.json").write_text(json.dumps([asdict(h) for h in hits], indent=2), encoding="utf-8")
    (out_dir / "mp_gate_hunt_file_scores.json").write_text(json.dumps([asdict(row) for row in file_scores], indent=2), encoding="utf-8")
    with (out_dir / "mp_gate_hunt_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "source_kind", "category", "value", "context", "offset", "line", "score"])
        writer.writeheader()
        for hit in hits:
            writer.writerow(asdict(hit))
    with (out_dir / "mp_gate_hunt_file_scores.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "extension", "source_kind", "size", "entropy_64k", "hit_count", "score", "categories", "recommendation"])
        writer.writeheader()
        for row in file_scores:
            item = asdict(row)
            item["categories"] = ";".join(row.categories)
            writer.writerow(item)

    lines = [
        "# Code RED MP Gate Hunt",
        "",
        f"Generated: {summary['generated_at']}",
        f"Files scanned: {summary['files_scanned']}",
        f"Files with hits: {summary['files_with_hits']}",
        f"Hits: {summary['hit_count']}",
        f"Top recommendation: `{summary['top_recommendation']}`",
        f"Top file: `{summary['top_file']}`",
        "",
        "## Category counts",
    ]
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Highest-ranked files"])
    for row in strongest[:30]:
        lines.append(f"- score={row.score} hits={row.hit_count} `{row.path}` :: {row.recommendation}")
    if not strongest:
        lines.append("- No gate candidates found in supplied sources.")
    lines.extend(["", "## Next actions"])
    for action in summary["next_actions"]:
        lines.append(f"- {action}")
    (out_dir / "mp_gate_hunt_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find likely MP runtime gates after copied content injection.")
    parser.add_argument("--source", action="append", type=Path, default=[], help="Folder/file to scan. Can be repeated.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-file-bytes", type=int, default=64 * 1024 * 1024, help="Skip non-text files larger than this.")
    parser.add_argument("--max-read-bytes", type=int, default=8 * 1024 * 1024, help="Max bytes to read per binary/resource file.")
    args = parser.parse_args(argv)
    sources = args.source or DEFAULT_SOURCES
    summary = run_scan(sources, args.out, args.max_file_bytes, args.max_read_bytes)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
