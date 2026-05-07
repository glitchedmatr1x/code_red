#!/usr/bin/env python3
"""Code RED Freemode / Init Inspector.

Read-only inspector for extracted init/script files and full-backend harness
outputs. It looks for freemode, MP, network, session, team, spawn, graveyard,
overrun, and bootstrap/init signals.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SCRIPT_EXTS = {".sco", ".wsc", ".xsc", ".wsv", ".txt", ".c", ".h", ".cpp", ".lua", ".scp", ".sc"}
CATEGORY_PATTERNS = {
    "freemode_literal": [r"\bfreemode\b", r"free[_ -]?mode"],
    "mp_network": [r"\bmp_", r"\bnet_", r"network", r"session", r"lobby", r"matchmaking", r"host", r"client"],
    "team_mode": [r"\bteam\b", r"teamwin", r"teamlose", r"teamdef", r"coop", r"co[_-]"],
    "spawn_flow": [r"spawn", r"respawn", r"safe_spawn", r"weapon_spawn", r"player_spawn", r"start_pos"],
    "graveyard_overrun": [r"graveyard", r"gy_", r"overrun", r"wave", r"sudden_death", r"zombie", r"undead"],
    "challenge_progression": [r"challenge", r"rank", r"xp", r"bonus", r"journal", r"progress", r"unlock"],
    "init_bootstrap": [r"\binit\b", r"startup", r"bootstrap", r"main", r"launch", r"load", r"register"],
}
STRING_RE = re.compile(rb"[\x20-\x7e]{4,220}")


@dataclass
class SignalHit:
    source: str
    origin: str
    category: str
    value: str
    context: str
    offset: int | None
    line: int | None


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def clean(text: str, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def categories_for(text: str) -> list[str]:
    return [cat for cat, patterns in CATEGORY_PATTERNS.items() if any(re.search(p, text, re.I) for p in patterns)]


def iter_script_files(roots: Iterable[Path]) -> Iterable[Path]:
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in files:
            if path.suffix.lower() not in SCRIPT_EXTS:
                continue
            key = str(path.resolve())
            if key not in seen:
                seen.add(key)
                yield path


def inspect_text(path: Path) -> list[SignalHit]:
    hits: list[SignalHit] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return hits
    for line_no, line in enumerate(lines, 1):
        cats = categories_for(line)
        for cat in cats:
            hits.append(SignalHit(str(path), "text_line", cat, line.strip()[:220], clean(line), None, line_no))
    return hits


def inspect_binary(path: Path) -> list[SignalHit]:
    hits: list[SignalHit] = []
    try:
        blob = path.read_bytes()
    except Exception:
        return hits
    for m in STRING_RE.finditer(blob):
        value = m.group(0).decode("utf-8", "ignore").strip("\x00\r\n\t ")
        cats = categories_for(value)
        if not cats:
            continue
        start = max(0, m.start() - 96)
        end = min(len(blob), m.end() + 96)
        ctx = clean(blob[start:end].replace(b"\x00", b" ").decode("utf-8", "ignore"))
        for cat in cats:
            hits.append(SignalHit(str(path), "binary_string", cat, value[:220], ctx, m.start(), None))
    return hits


def inspect_harness_json(harness_dir: Path) -> list[SignalHit]:
    hits: list[SignalHit] = []
    for name in (
        "full_backend_rpf6_harness_summary.json",
        "full_backend_rpf6_harness_hits.json",
        "full_backend_rpf6_harness_selected_hits.json",
        "full_backend_rpf6_harness_extracted_scripts.json",
        "full_backend_rpf6_harness_selected_scripts.json",
    ):
        path = harness_dir / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stack = [("root", data)]
        while stack:
            field, value = stack.pop()
            if isinstance(value, dict):
                stack.extend((f"{field}.{k}", v) for k, v in value.items())
            elif isinstance(value, list):
                stack.extend((f"{field}[{i}]", v) for i, v in enumerate(value))
            else:
                text = str(value)
                for cat in categories_for(text):
                    hits.append(SignalHit(str(path), "harness_json", cat, text[:220], clean(f"{field}: {text}"), None, None))
    return hits


def inspect(sources: list[Path], harnesses: list[Path]) -> tuple[list[SignalHit], list[dict]]:
    hits: list[SignalHit] = []
    files: list[dict] = []
    for path in iter_script_files(sources):
        try:
            blob = path.read_bytes()
        except Exception:
            blob = b""
        file_hits = inspect_text(path)
        if not file_hits:
            file_hits = inspect_binary(path)
        files.append({
            "path": str(path),
            "extension": path.suffix.lower(),
            "size": len(blob),
            "entropy_64k": round(entropy(blob[:65536]), 4),
            "init_named": "init" in path.name.lower(),
            "z_prefixed": path.stem.lower().startswith("z"),
            "hit_count": len(file_hits),
            "categories": sorted({h.category for h in file_hits}),
        })
        hits.extend(file_hits)
    for harness in harnesses:
        hits.extend(inspect_harness_json(harness))
    return hits, files


def write_outputs(out_dir: Path, hits: list[SignalHit], files: list[dict]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    category_counts = Counter(h.category for h in hits)
    source_counts = Counter(h.source for h in hits)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "file_count": len(files),
        "hit_count": len(hits),
        "category_counts": dict(category_counts),
        "source_hit_counts": dict(source_counts),
        "freemode_literal_count": category_counts.get("freemode_literal", 0),
        "mp_network_count": category_counts.get("mp_network", 0),
        "freemode_status": "literal_freemode_found" if category_counts.get("freemode_literal", 0) else "no_literal_freemode_found_check_mp_network_categories",
    }
    (out_dir / "freemode_init_inspector_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "freemode_init_inspector_files.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    (out_dir / "freemode_init_inspector_hits.json").write_text(json.dumps([asdict(h) for h in hits], indent=2), encoding="utf-8")
    with (out_dir / "freemode_init_inspector_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["source", "origin", "category", "value", "context", "offset", "line"])
        writer.writeheader()
        for hit in hits:
            writer.writerow(asdict(hit))
    lines = [
        "# Code RED Freemode / Init Inspector",
        "",
        f"Generated: {summary['generated_at']}",
        f"Files inspected: {summary['file_count']}",
        f"Signal hits: {summary['hit_count']}",
        f"Freemode literal hits: {summary['freemode_literal_count']}",
        f"MP/network hits: {summary['mp_network_count']}",
        f"Status: `{summary['freemode_status']}`",
        "",
        "## Category counts",
    ]
    for cat, count in sorted(category_counts.items()):
        lines.append(f"- {cat}: {count}")
    lines.extend(["", "## Strongest freemode / MP hints"])
    priority = [h for h in hits if h.category in {"freemode_literal", "mp_network", "init_bootstrap", "spawn_flow", "team_mode"}]
    for hit in priority[:200]:
        loc = f":{hit.line}" if hit.line else (f"@0x{hit.offset:x}" if hit.offset is not None else "")
        lines.append(f"- [{hit.category}] `{Path(hit.source).name}{loc}` `{hit.value}`")
    if not priority:
        lines.append("- No freemode/MP/init priority hits found in supplied files.")
    (out_dir / "freemode_init_inspector_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect extracted init scripts/harness output for freemode and MP signals")
    parser.add_argument("--source", action="append", type=Path, default=[], help="Extracted script/source folder or file. Can be repeated.")
    parser.add_argument("--harness", action="append", type=Path, default=[], help="Full backend harness output folder. Can be repeated.")
    parser.add_argument("--out", type=Path, default=Path("logs/freemode_init_inspector"))
    args = parser.parse_args(argv)
    hits, files = inspect(args.source, args.harness)
    summary = write_outputs(args.out, hits, files)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
