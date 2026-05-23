#!/usr/bin/env python3
"""
Code RED Navres BattleSet Scanner
Read-only scanner for navres.rpf battle/combat/nav placement clues.
Designed to avoid the deep-scan/export-candidates hang by doing a streaming raw scan first.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DEFAULT_TERMS = [
    "battle", "battleset", "battle_set", "battle set", "combat",
    "squad", "cover", "defend", "volume", "beacon", "ambient",
    "event", "placement", "nav", "navres", "zone", "spawn",
    "encounter", "roadblock", "gang", "army", "law", "shoot",
]

PRINTABLE = set(range(32, 127)) | {9, 10, 13}


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest().upper()


def ascii_sanitize(b: bytes) -> str:
    s = []
    for c in b:
        if c in PRINTABLE:
            s.append(chr(c))
        else:
            s.append(".")
    return "".join(s)


def make_patterns(terms: List[str]) -> List[Tuple[str, bytes, str]]:
    pats: List[Tuple[str, bytes, str]] = []
    seen = set()
    for t in terms:
        t = t.strip()
        if not t:
            continue
        key = t.lower()
        if (key, "ascii") not in seen:
            pats.append((t, t.encode("ascii", errors="ignore").lower(), "ascii"))
            seen.add((key, "ascii"))
        # UTF-16LE loose string form for resources that use wide strings.
        wide = t.encode("utf-16le", errors="ignore").lower()
        if (key, "utf16le") not in seen:
            pats.append((t, wide, "utf16le"))
            seen.add((key, "utf16le"))
    return pats


def streaming_scan(path: Path, out_dir: Path, terms: List[str], max_hits_per_term: int, context: int, chunk_mb: int, progress: bool) -> Dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    size = path.stat().st_size
    chunk_size = max(1, chunk_mb) * 1024 * 1024
    overlap = max(4096, context * 4, max((len(t.encode('utf-16le')) for t in terms), default=32) + context)
    pats = make_patterns(terms)
    hit_counts: Dict[str, int] = {f"{term}:{enc}": 0 for term, _p, enc in pats}
    total_hits = 0
    rows = []
    started = time.time()

    hits_csv = out_dir / "navres_battleset_string_hits.csv"
    with path.open("rb") as f, hits_csv.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["offset_dec", "offset_hex", "term", "encoding", "context_ascii", "context_hex"])
        writer.writeheader()
        pos = 0
        prev = b""
        last_progress = 0.0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            block_start = pos - len(prev)
            block = prev + chunk
            block_lower = block.lower()

            for term, pat, enc in pats:
                if not pat:
                    continue
                key = f"{term}:{enc}"
                if hit_counts.get(key, 0) >= max_hits_per_term:
                    continue
                start = 0
                while hit_counts.get(key, 0) < max_hits_per_term:
                    i = block_lower.find(pat, start)
                    if i < 0:
                        break
                    abs_off = block_start + i
                    # Avoid duplicate hits caused by overlap.
                    if abs_off >= pos or pos == 0:
                        c0 = max(0, i - context)
                        c1 = min(len(block), i + len(pat) + context)
                        ctx = block[c0:c1]
                        row = {
                            "offset_dec": abs_off,
                            "offset_hex": f"0x{abs_off:X}",
                            "term": term,
                            "encoding": enc,
                            "context_ascii": ascii_sanitize(ctx),
                            "context_hex": ctx[:256].hex(" ").upper(),
                        }
                        writer.writerow(row)
                        hit_counts[key] = hit_counts.get(key, 0) + 1
                        total_hits += 1
                    start = i + 1

            pos += len(chunk)
            prev = block[-overlap:]
            now = time.time()
            if progress and now - last_progress >= 1.0:
                last_progress = now
                pct = (pos / size * 100.0) if size else 100.0
                print(f"scanned {pos/1048576:.1f}/{size/1048576:.1f} MB ({pct:.1f}%) | hits={total_hits}", flush=True)

    # Summarize term counts, collapse enc variants.
    collapsed: Dict[str, int] = {}
    for k, v in hit_counts.items():
        term, enc = k.rsplit(":", 1)
        collapsed[term] = collapsed.get(term, 0) + v

    top_terms = sorted(collapsed.items(), key=lambda kv: (-kv[1], kv[0]))
    report = {
        "status": "complete",
        "mode": "quick-scan",
        "rpf": str(path),
        "size": size,
        "size_mb": round(size/1048576, 3),
        "sha256": sha256_file(path),
        "out_dir": str(out_dir),
        "hits_csv": str(hits_csv),
        "total_hits_capped": total_hits,
        "max_hits_per_term_per_encoding": max_hits_per_term,
        "top_terms": [{"term": t, "hits": c} for t, c in top_terms if c],
        "elapsed_sec": round(time.time() - started, 3),
    }
    (out_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = ["# Code RED Navres BattleSet Scan", "", f"RPF: `{path}`", f"Size: {report['size_mb']} MB", f"SHA256: `{report['sha256']}`", "", "## Hit summary", ""]
    if report["top_terms"]:
        for item in report["top_terms"]:
            md.append(f"- {item['term']}: {item['hits']}")
    else:
        md.append("No raw string hits found. The data may be compressed/encrypted inside resources; use rsc-index next.")
    md += ["", f"CSV: `{hits_csv}`", "", "## Next", "", "Review contexts around `battleset`, `battle`, `cover`, `defend`, `placement`, and `event` before any patching."]
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")
    return report


def rsc_index(path: Path, out_dir: Path, context: int, progress: bool, chunk_mb: int) -> Dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    size = path.stat().st_size
    chunk_size = max(1, chunk_mb) * 1024 * 1024
    magic = b"RSC\x85"
    offsets: List[int] = []
    started = time.time()
    idx_csv = out_dir / "rsc85_offsets.csv"
    with path.open("rb") as f, idx_csv.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["offset_dec", "offset_hex", "header_hex", "context_ascii"])
        writer.writeheader()
        pos = 0
        prev = b""
        last_progress = 0.0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            block_start = pos - len(prev)
            block = prev + chunk
            start = 0
            while True:
                i = block.find(magic, start)
                if i < 0:
                    break
                abs_off = block_start + i
                if abs_off >= pos or pos == 0:
                    offsets.append(abs_off)
                    c0 = max(0, i - context)
                    c1 = min(len(block), i + 64 + context)
                    ctx = block[c0:c1]
                    writer.writerow({
                        "offset_dec": abs_off,
                        "offset_hex": f"0x{abs_off:X}",
                        "header_hex": block[i:i+64].hex(" ").upper(),
                        "context_ascii": ascii_sanitize(ctx),
                    })
                start = i + 1
            pos += len(chunk)
            prev = block[-64:]
            now = time.time()
            if progress and now - last_progress >= 1.0:
                last_progress = now
                pct = (pos / size * 100.0) if size else 100.0
                print(f"scanned {pos/1048576:.1f}/{size/1048576:.1f} MB ({pct:.1f}%) | RSC85={len(offsets)}", flush=True)
    report = {
        "status": "complete",
        "mode": "rsc-index",
        "rpf": str(path),
        "size": size,
        "size_mb": round(size/1048576, 3),
        "sha256": sha256_file(path),
        "out_dir": str(out_dir),
        "rsc85_count": len(offsets),
        "rsc85_csv": str(idx_csv),
        "first_offsets_hex": [f"0x{x:X}" for x in offsets[:25]],
        "elapsed_sec": round(time.time() - started, 3),
    }
    (out_dir / "rsc85_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def cmd_status(args) -> int:
    report = {
        "tool": "Code RED Navres BattleSet Scanner",
        "version": "1.0-readonly-progress",
        "cwd": os.getcwd(),
        "default_terms": DEFAULT_TERMS,
        "notes": [
            "Read-only scanner; does not patch or extract by default.",
            "Use this before the full Content_RPF_DeepScan on navres.rpf because export-candidates can appear stuck.",
            "quick-scan streams the RPF and prints progress.",
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


def cmd_quick_scan(args) -> int:
    path = Path(args.rpf)
    if not path.exists():
        print(json.dumps({"status": "error", "error": f"RPF not found: {path}"}, indent=2))
        return 2
    terms = args.terms or DEFAULT_TERMS
    report = streaming_scan(path, Path(args.out), terms, args.max_hits_per_term, args.context, args.chunk_mb, not args.no_progress)
    print(json.dumps(report, indent=2))
    return 0


def cmd_rsc_index(args) -> int:
    path = Path(args.rpf)
    if not path.exists():
        print(json.dumps({"status": "error", "error": f"RPF not found: {path}"}, indent=2))
        return 2
    report = rsc_index(path, Path(args.out), args.context, not args.no_progress, args.chunk_mb)
    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Code RED navres.rpf battle/battleset read-only scanner")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("status")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("quick-scan")
    sp.add_argument("--rpf", required=True)
    sp.add_argument("--out", default="logs/navres_battleset_scan")
    sp.add_argument("--terms", nargs="*", default=None)
    sp.add_argument("--max-hits-per-term", type=int, default=200)
    sp.add_argument("--context", type=int, default=96)
    sp.add_argument("--chunk-mb", type=int, default=16)
    sp.add_argument("--no-progress", action="store_true")
    sp.set_defaults(func=cmd_quick_scan)

    sp = sub.add_parser("rsc-index")
    sp.add_argument("--rpf", required=True)
    sp.add_argument("--out", default="logs/navres_battleset_scan")
    sp.add_argument("--context", type=int, default=64)
    sp.add_argument("--chunk-mb", type=int, default=32)
    sp.add_argument("--no-progress", action="store_true")
    sp.set_defaults(func=cmd_rsc_index)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
