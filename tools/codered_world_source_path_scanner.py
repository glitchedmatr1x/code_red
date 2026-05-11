#!/usr/bin/env python3
"""
Code RED world/source-path scanner.

Scans raw files and zip-contained files for RDR/RAGE world-source path hints,
WSV/WSI markers, refGroups, territory paths, and developer-drive paths like:

  T:/rdr2/Art/Worlds/territory/shared/models/props/

This is a read-only scanner. It does not extract/modify RPF contents beyond reading
files from disk/zip entries.

Examples:
  py -3 tools\codered_world_source_path_scanner.py --source imports --source scratch --source game --out logs\world_source_path_scan
  py -3 tools\codered_world_source_path_scanner.py --source "D:\Games\Red Dead Redemption\Code_RED\game" --term "T:/rdr2/Art/Worlds/territory/shared/models/props/" --out logs\props_path_scan
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

DEFAULT_TERMS = [
    "T:/rdr2/Art/Worlds/territory/shared/models/props/",
    "T:/rdr2/Art/Worlds",
    "rdr2/Art/Worlds",
    "Art/Worlds/territory",
    "Worlds/territory/shared",
    "territory/shared/models/props",
    "shared/models/props",
    "models/props",
    "territory_swall",
    "territory",
    "refGroups",
    "refgroups",
    ".wsv",
    ".wsi",
    "wsv",
    "wsi",
]

DEFAULT_EXTENSIONS = {
    ".rpf", ".zip", ".txt", ".xml", ".csv", ".json", ".dat", ".ymt", ".ytyp", ".ymap",
    ".wsv", ".wsi", ".rsc", ".bin",
}

PRINTABLE = set(range(32, 127)) | {9, 10, 13}


@dataclass
class Hit:
    container: str
    entry: str
    term: str
    encoding: str
    offset: int
    file_size: int
    context: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Code RED/RDR files for world source-path hints and WSV/WSI markers.")
    parser.add_argument("--source", action="append", required=True, help="File or directory to scan. Can be repeated.")
    parser.add_argument("--term", action="append", default=[], help="Extra term to scan for. Can be repeated.")
    parser.add_argument("--out", default="logs/world_source_path_scan", help="Output directory.")
    parser.add_argument("--max-file-mb", type=int, default=512, help="Skip individual files larger than this size.")
    parser.add_argument("--context", type=int, default=96, help="Bytes of context on each side of a hit.")
    parser.add_argument("--all-extensions", action="store_true", help="Scan all file extensions instead of the default focused list.")
    return parser.parse_args()


def iter_files(paths: Iterable[Path], all_extensions: bool) -> Iterable[Path]:
    for source in paths:
        if source.is_file():
            yield source
        elif source.is_dir():
            for p in source.rglob("*"):
                if not p.is_file():
                    continue
                if all_extensions or p.suffix.lower() in DEFAULT_EXTENSIONS:
                    yield p


def make_needles(terms: list[str]) -> list[tuple[str, str, bytes]]:
    needles: list[tuple[str, str, bytes]] = []
    seen = set()
    for term in terms:
        if not term:
            continue
        variants = [
            (term, "ascii", term.encode("utf-8", errors="ignore")),
            (term, "utf16le", term.encode("utf-16le", errors="ignore")),
            (term, "utf16be", term.encode("utf-16be", errors="ignore")),
        ]
        for item in variants:
            key = (item[0].lower(), item[1])
            if item[2] and key not in seen:
                needles.append(item)
                seen.add(key)
    return needles


def printable_context(blob: bytes, offset: int, term_len: int, span: int) -> str:
    start = max(0, offset - span)
    end = min(len(blob), offset + term_len + span)
    chunk = blob[start:end]
    out_chars = []
    for b in chunk:
        if b in PRINTABLE:
            out_chars.append(chr(b))
        elif b == 0:
            out_chars.append("·")
        else:
            out_chars.append(".")
    text = "".join(out_chars)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:500]


def scan_blob(container: str, entry: str, blob: bytes, needles: list[tuple[str, str, bytes]], context: int) -> list[Hit]:
    hits: list[Hit] = []
    lower_blob = blob.lower()
    for term, enc, needle in needles:
        haystack = lower_blob if enc == "ascii" else blob
        target = needle.lower() if enc == "ascii" else needle
        start = 0
        while True:
            idx = haystack.find(target, start)
            if idx < 0:
                break
            hits.append(Hit(
                container=container,
                entry=entry,
                term=term,
                encoding=enc,
                offset=idx,
                file_size=len(blob),
                context=printable_context(blob, idx, len(needle), context),
            ))
            start = idx + max(1, len(target))
    return hits


def read_file(path: Path, max_bytes: int) -> bytes | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        return path.read_bytes()
    except OSError:
        return None


def scan_path(path: Path, needles: list[tuple[str, str, bytes]], max_bytes: int, context: int) -> list[Hit]:
    hits: list[Hit] = []
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    if info.is_dir() or info.file_size > max_bytes:
                        continue
                    try:
                        blob = zf.read(info.filename)
                    except Exception:
                        continue
                    hits.extend(scan_blob(str(path), info.filename, blob, needles, context))
        except zipfile.BadZipFile:
            blob = read_file(path, max_bytes)
            if blob is not None:
                hits.extend(scan_blob(str(path), "", blob, needles, context))
    else:
        blob = read_file(path, max_bytes)
        if blob is not None:
            hits.extend(scan_blob(str(path), "", blob, needles, context))
    return hits


def main() -> int:
    args = parse_args()
    sources = [Path(s) for s in args.source]
    missing = [str(s) for s in sources if not s.exists()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    terms = DEFAULT_TERMS + args.term
    needles = make_needles(terms)
    max_bytes = args.max_file_mb * 1024 * 1024

    files = list(iter_files(sources, args.all_extensions))
    hits: list[Hit] = []
    for file_path in files:
        hits.extend(scan_path(file_path, needles, max_bytes, args.context))

    summary = {
        "ok": not missing,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [str(s) for s in sources],
        "missing_sources": missing,
        "files_seen": len(files),
        "hits": len(hits),
        "terms": terms,
        "max_file_mb": args.max_file_mb,
        "note": "Read-only source-path/WSV/WSI marker scanner. It does not decompile or parse RPF file tables.",
    }

    (out_dir / "world_source_path_scan_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "world_source_path_scan_hits.json").write_text(json.dumps([asdict(h) for h in hits], indent=2), encoding="utf-8")

    with (out_dir / "world_source_path_scan_hits.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["container", "entry", "term", "encoding", "offset", "file_size", "context"])
        writer.writeheader()
        for h in hits:
            writer.writerow(asdict(h))

    md_lines = [
        "# Code RED World Source Path Scan",
        "",
        f"Generated: {summary['generated_at']}",
        f"Files seen: {summary['files_seen']}",
        f"Hits: {summary['hits']}",
        "",
        "## Top hits",
        "",
    ]
    for h in hits[:100]:
        where = h.container if not h.entry else f"{h.container} :: {h.entry}"
        md_lines.append(f"- `{h.term}` ({h.encoding}) at `{where}` offset `{h.offset}`")
        if h.context:
            md_lines.append(f"  - `{h.context}`")
    if not hits:
        md_lines.append("No hits found for the configured terms.")
    (out_dir / "world_source_path_scan_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
