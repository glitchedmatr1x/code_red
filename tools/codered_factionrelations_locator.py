#!/usr/bin/env python3
"""Locate real faction relations resources in a local Code RED workspace.

Local-only locator. It filters out Code RED rosters, logs, workspace mirrors,
and generated reports so the next pass can focus on actual loose game resources.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

VERSION = "1.0.0-factionrelations-locator"
OUT_DIR = Path("scratch/faction_wars/factionrelations_locator")
REPORT_MD = OUT_DIR / "REAL_FACTIONRELATIONS_CANDIDATES.md"
REPORT_JSON = OUT_DIR / "real_factionrelations_candidates.json"
REPORT_CSV = OUT_DIR / "real_factionrelations_candidates.csv"

SUFFIXES = {".xml", ".ini", ".cfg", ".txt", ".csv", ".json", ".md"}
SKIP_DIRS = {".git", "__pycache__", "build", "dist", "staged_resources", "patched_resources", "codered_backups"}
NOISE_PARTS = (
    "related_apps/codered_script_workshop/workspace/",
    "scratch/",
    "logs/",
    "data/codered/rosters/",
    "data/codered/faction_wars_",
    "npc_roster",
    "actor_enum_map",
    "ai_behavior_actions",
    "native",
    "tool",
)
TERMS = (
    "factionrelations", "faction_relations", "factionrelation", "faction relation",
    "relationship", "relation", "lawman", "lawmen", "sheriff", "marshal", "gang",
    "bandit", "bandito", "criminal", "hostile", "enemy",
)
STRONG_FILE_RE = re.compile(r"faction.*relation|relation.*faction|factions?[_-]?relations?", re.IGNORECASE)


@dataclass
class Candidate:
    score: int
    path: str
    suffix: str
    size: int
    terms: list[str]
    excerpt: str


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


def is_noise(rel: str) -> bool:
    low = rel.replace("\\", "/").lower()
    return any(part in low for part in NOISE_PARTS)


def read_text(path: Path, limit: int = 3_000_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
        for name in filenames:
            path = Path(current) / name
            if path.suffix.lower() in SUFFIXES:
                yield path


def score_file(root: Path, path: Path) -> Candidate | None:
    rel = rel_to(path, root)
    if is_noise(rel):
        return None
    text = read_text(path)
    low = (rel + "\n" + text[:50000]).lower()
    hits = sorted({term for term in TERMS if term.lower() in low})
    if not hits and not STRONG_FILE_RE.search(rel):
        return None
    score = len(hits) * 20
    if STRONG_FILE_RE.search(rel):
        score += 200
    if path.suffix.lower() == ".xml":
        score += 100
    if "content" in rel.lower() or "tune" in rel.lower() or "game" in rel.lower():
        score += 50
    excerpt = ""
    for idx, line in enumerate(text.splitlines(), start=1):
        if any(term.lower() in line.lower() for term in hits[:5]):
            excerpt = f"L{idx}: {line.strip()[:240]}"
            break
    return Candidate(score, rel, path.suffix.lower(), path.stat().st_size, hits, excerpt)


def write_csv(path: Path, rows: Sequence[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["score", "path", "suffix", "size", "terms", "excerpt"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            d = asdict(row)
            d["terms"] = "|".join(row.terms)
            writer.writerow(d)


def build_md(root: Path, rows: Sequence[Candidate]) -> str:
    lines = [
        "# Real Faction Relations Candidates",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "This locator filters out Code RED rosters, generated reports, logs, Script Workshop mirrors, and native/tool files. Use this to find the actual loose faction relation resource before patching.",
        "",
        "| Rank | Score | Path | Terms | Excerpt |",
        "|---:|---:|---|---|---|",
    ]
    for i, row in enumerate(rows[:80], start=1):
        lines.append(f"| {i} | {row.score} | `{row.path}` | {', '.join(row.terms)} | {row.excerpt} |")
    if not rows:
        lines.extend([
            "",
            "No clean real factionrelations candidate found. The real file may still be packed in an RPF or named differently. Next search terms: `relationship`, `affinity`, `factions`, `lawman`, `bandito`, `criminal`.",
        ])
    return "\n".join(lines) + "\n"


def run(root: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    for path in iter_files(root):
        cand = score_file(root, path)
        if cand:
            rows.append(cand)
    rows.sort(key=lambda x: (x.score, x.path), reverse=True)
    out = root / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    (root / REPORT_JSON).write_text(json.dumps([asdict(x) for x in rows], indent=2), encoding="utf-8")
    write_csv(root / REPORT_CSV, rows)
    (root / REPORT_MD).write_text(build_md(root, rows), encoding="utf-8")
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Locate real faction relation loose resources.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else find_root()
    rows = run(root)
    print("# Code RED factionrelations locator")
    print("Candidates:", len(rows))
    print("Report:", (OUT_DIR / "REAL_FACTIONRELATIONS_CANDIDATES.md").as_posix())
    for i, row in enumerate(rows[:args.limit], start=1):
        print(f"{i:>3} {row.score:>5} {row.path}")
    return 0 if rows else 1

if __name__ == "__main__":
    raise SystemExit(main())
