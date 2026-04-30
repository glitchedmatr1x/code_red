#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

RPF6_AES_KEY = bytes([
    0xB7,0x62,0xDF,0xB6,0xE2,0xB2,0xC6,0xDE,0xAF,0x72,0x2A,0x32,0xD2,0xFB,0x6F,0x0C,
    0x98,0xA3,0x21,0x74,0x62,0xC9,0xC4,0xED,0xAD,0xAA,0x2E,0xD0,0xDD,0xF9,0x2F,0x10,
])
DEFAULT_KEYWORDS = [
    "spawn", "create", "vehicle", "wagon", "coach", "cart", "car", "playercar", "train",
    "driver", "passenger", "seat", "mount", "model", "hash", "native", "turret", "browning",
    "VEHICLE_", "TURRET_", "Vehicle_Generator", "car_gringo", "PlayerCar", "CarCrank",
    "Gen_Vehicle_Brain", "fbi", "companion", "posse", "coach", "wagonprison",
]
TOKEN_RE = re.compile(r"\b(?:VEHICLE|TURRET|BLIP|COMPANION)_[A-Za-z0-9_]+\b|\$\\Companion\\[A-Za-z0-9_]+", re.I)
ASCII_RE = re.compile(rb"[\x20-\x7E]{4,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7E]\x00){4,}")


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def rdr_hash(name: str) -> int:
    h = 0
    for ch in name.lower():
        a = (h + ord(ch)) & 0xFFFFFFFF
        b = (a + ((a << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h = (b ^ (b >> 6)) & 0xFFFFFFFF
    a = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    b = (a ^ (a >> 11)) & 0xFFFFFFFF
    return (b + ((b << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


def is_res(f1: int) -> bool:
    return (f1 & 0x80000000) != 0


def rtype(c: int) -> int:
    return c & 0xFF


def ent_off(c: int, res: bool) -> int:
    return ((c & 0x7FFFFF00) if res else (c & 0x7FFFFFFF)) * 8


@dataclass
class EntryRange:
    index: int
    name_hash: int
    name: str
    path: str
    ext: str
    offset: int
    size: int
    resource_type: int | None
    resource: bool


def try_rpf_entry_ranges(path: Path) -> list[EntryRange]:
    # Deliberately avoids debug-name AES decryption. Hash paths are enough to map offsets safely.
    data = path.read_bytes()
    if data[:4] != b"RPF6" or len(data) < 16:
        return []
    try:
        _, count, _debug_word, enc = struct.unpack(">4I", data[:16])
        if enc:
            # Encrypted TOCs need the full AES helper; raw scanning still works, so keep parser optional.
            return []
        toc_size = ((count * 20) + 15) & ~15
        toc = data[16:16 + toc_size]
        raw = []
        for i in range(count):
            a, b, c, d, e = struct.unpack(">5I", toc[i * 20:(i + 1) * 20])
            is_dir = ((c >> 24) & 0xFF) == 0x80
            if is_dir:
                raw.append(dict(i=i, h=a, t="dir", name="root" if a == 0 else f"0x{a:08X}", start=c & 0x7FFFFFFF, count=d & 0x0FFFFFFF))
            else:
                res = is_res(d)
                name = f"0x{a:08X}"
                raw.append(dict(i=i, h=a, t="file", name=name, size=b & 0x0FFFFFFF, off=ent_off(c, res), res=res, rt=rtype(c) if res else None))
        parents = [None] * len(raw)
        for x in raw:
            if x["t"] == "dir":
                for ci in range(x["start"], x["start"] + x["count"]):
                    if 0 <= ci < len(raw):
                        parents[ci] = x["i"]
        out = []
        for x in raw:
            if x["t"] != "file":
                continue
            parts = [x["name"]]
            p = parents[x["i"]]
            seen = set()
            while p is not None and p not in seen and 0 <= p < len(raw):
                seen.add(p)
                parts.append(raw[p]["name"])
                p = parents[p]
            pth = "/".join(reversed(parts))
            ext = "." + x["name"].lower().rsplit(".", 1)[-1] if "." in x["name"] else ""
            out.append(EntryRange(x["i"], x["h"], x["name"], pth, ext, x["off"], x["size"], x["rt"], x["res"]))
        return out
    except Exception:
        return []


def collect_inputs(items: Iterable[str]) -> list[Path]:
    out = []
    for item in items:
        p = Path(item)
        if p.is_dir():
            out.extend(sorted(q for q in p.rglob("*.rpf") if q.is_file()))
        elif p.exists():
            out.append(p)
    seen = set(); ret = []
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key); ret.append(p)
    return ret


def keyword_score(text: str, keywords: list[str]) -> tuple[int, list[str]]:
    low = text.lower()
    hits = [kw for kw in keywords if kw.lower() in low]
    score = len(hits)
    for kw in ("spawn", "create", "vehicle_generator", "playercar", "vehicle_", "turret_", "native", "driver", "seat", "fbi"):
        if kw in low:
            score += 3
    if "content\\scripting\\gringo" in low or "content/scripting/gringo" in low:
        score += 4
    return score, hits


def clean_context(data: bytes, off: int, radius: int = 128) -> str:
    a = max(0, off - radius); b = min(len(data), off + radius)
    raw = data[a:b].replace(b"\x00", b" ")
    return re.sub(r"\s+", " ", raw.decode("latin-1", "replace")).strip()[:320]


def find_entry_for_offset(ranges: list[EntryRange], off: int) -> EntryRange | None:
    # Ranges are few enough for linear lookup.
    for e in ranges:
        if e.offset <= off < e.offset + e.size:
            return e
    return None


def iter_strings(data: bytes, include_utf16: bool = True, max_strings: int = 500000):
    count = 0
    for m in ASCII_RE.finditer(data):
        yield m.start(), m.group(0).decode("latin-1", "replace"), "ascii"
        count += 1
        if count >= max_strings:
            return
    if include_utf16:
        for m in UTF16_RE.finditer(data):
            try:
                yield m.start(), m.group(0).decode("utf-16le", "replace"), "utf16le"
            except Exception:
                continue
            count += 1
            if count >= max_strings:
                return


def scan_file(path: Path, keywords: list[str], args: argparse.Namespace) -> tuple[list[dict], list[dict], list[dict], dict]:
    data = path.read_bytes()
    ranges = try_rpf_entry_ranges(path)
    string_rows: list[dict] = []
    token_rows: list[dict] = []
    cluster_counts: Counter[int] = Counter()
    token_seen = set()
    for off, text, encoding in iter_strings(data, include_utf16=not args.no_utf16, max_strings=args.max_strings):
        score, hits = keyword_score(text, keywords)
        token_text = text[:2000]
        has_token_prefix = any(prefix in token_text.upper() for prefix in ("VEHICLE_", "TURRET_", "BLIP_", "COMPANION_", "$\\COMPANION\\"))
        token_matches = list(TOKEN_RE.finditer(token_text)) if has_token_prefix else []
        if not score and not token_matches:
            continue
        ent = find_entry_for_offset(ranges, off)
        row_base = {
            "archive": path.name,
            "archive_path": str(path),
            "raw_offset": off,
            "raw_offset_hex": f"0x{off:08X}",
            "encoding": encoding,
            "entry_index": ent.index if ent else "",
            "entry_path": ent.path if ent else "",
            "entry_offset": ent.offset if ent else "",
            "entry_size": ent.size if ent else "",
            "resource_type": ent.resource_type if ent else "",
            "resource": ent.resource if ent else "",
        }
        if score:
            cluster_counts[off // args.cluster_size] += score
            string_rows.append({
                **row_base,
                "score": score,
                "keyword_hits": "|".join(hits),
                "text": text[:500],
                "context": clean_context(data, off),
            })
        for tm in token_matches:
            token = tm.group(0)
            key = (path.name, off, token.upper())
            if key in token_seen:
                continue
            token_seen.add(key)
            cluster_counts[off // args.cluster_size] += 4
            token_rows.append({**row_base, "token": token, "token_upper": token.upper(), "text": text[:500]})
    clusters = []
    for c, score in cluster_counts.most_common(200):
        off = c * args.cluster_size
        ent = find_entry_for_offset(ranges, off)
        clusters.append({
            "archive": path.name,
            "cluster_start": off,
            "cluster_start_hex": f"0x{off:08X}",
            "cluster_end": min(len(data), off + args.cluster_size),
            "score": score,
            "entry_index": ent.index if ent else "",
            "entry_path": ent.path if ent else "",
            "resource_type": ent.resource_type if ent else "",
            "context": clean_context(data, off, radius=256),
        })
    inv = {
        "archive": path.name,
        "archive_path": str(path),
        "size": len(data),
        "sha1": sha1(data),
        "rpf_entry_ranges": len(ranges),
        "string_hits": len(string_rows),
        "token_hits": len(token_rows),
        "cluster_hits": len(clusters),
    }
    return string_rows, token_rows, clusters, inv


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        if fields:
            w = csv.DictWriter(f, fields)
            w.writeheader(); w.writerows(rows)


def write_summary(outdir: Path, inventories: list[dict], strings: list[dict], tokens: list[dict], clusters: list[dict]) -> None:
    token_counts = Counter(t["token_upper"] for t in tokens)
    lines = [
        "# Code RED — Vehicle Spawn Research / Trainer-Style Runtime Path",
        "",
        "## Result",
        "",
        "This pass scans raw RPF/resource bytes for runtime-spawn clues. It does not patch any archive.",
        "",
        "## Archives scanned",
        "",
    ]
    for inv in inventories:
        lines.append(f"- `{inv['archive']}` — size {inv['size']:,}, string hits {inv['string_hits']}, token hits {inv['token_hits']}, clusters {inv['cluster_hits']}")
    lines += ["", "## Top clusters", ""]
    for c in clusters[:20]:
        lines.append(f"- score {c['score']:>4} | `{c['archive']}` | `{c['cluster_start_hex']}` | entry `{c.get('entry_path','')}`")
    lines += ["", "## Frequent vehicle/companion tokens", ""]
    for token, count in token_counts.most_common(40):
        lines.append(f"- `{token}` — {count}")
    lines += [
        "", "## Recommended direction", "",
        "1. Keep WSI edits limited to removing/clearing blocker props, because moving wagon-style physics records already crashed.",
        "2. Use `vehicle_spawn_strings.csv` and `vehicle_tokens.csv` to locate mission/gringo/native-style runtime spawn clues.",
        "3. Compare trainer spawn names against the `VEHICLE_*` tokens and `PlayerCar` / `Vehicle_Generator` / FBI strings found here.",
        "4. Next experiment should be script/runtime-oriented, not a wagon placement mutation.",
    ]
    (outdir / "trainer_spawn_research_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Code RED raw vehicle spawn research scanner")
    p.add_argument("inputs", nargs="+", help="RPF files or folders of RPF files")
    p.add_argument("--outdir", default="exports/vehicle_spawn_research")
    p.add_argument("--keyword", default="|".join(DEFAULT_KEYWORDS), help="Pipe-separated keyword list")
    p.add_argument("--cluster-size", type=int, default=4096)
    p.add_argument("--max-strings", type=int, default=500000)
    p.add_argument("--no-utf16", action="store_true")
    args = p.parse_args()
    keywords = [k.strip() for k in args.keyword.split("|") if k.strip()]
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    all_strings: list[dict] = []
    all_tokens: list[dict] = []
    all_clusters: list[dict] = []
    inventories: list[dict] = []
    for path in collect_inputs(args.inputs):
        print(f"Scanning {path.name}...")
        s, t, c, inv = scan_file(path, keywords, args)
        all_strings.extend(s); all_tokens.extend(t); all_clusters.extend(c); inventories.append(inv)
        print(f"  hits: strings={len(s)} tokens={len(t)} clusters={len(c)}")
    all_strings.sort(key=lambda r: r.get("score", 0), reverse=True)
    all_tokens.sort(key=lambda r: (r.get("token_upper", ""), r.get("archive", ""), r.get("raw_offset", 0)))
    all_clusters.sort(key=lambda r: r.get("score", 0), reverse=True)
    # Derived tables requested by the pass brief.
    candidate_scripts = [r for r in all_strings if any(k in str(r.get("text", "")).lower() for k in ("content\\scripting", "mission", "fbi", "gringo", "vehicle", "playercar"))]
    gringo_calls = [r for r in all_strings if "gringo" in str(r.get("text", "")).lower() or "vehicle_generator" in str(r.get("text", "")).lower() or "playercar" in str(r.get("text", "")).lower()]
    write_csv(outdir / "archive_inventory.csv", inventories)
    write_csv(outdir / "vehicle_spawn_strings.csv", all_strings)
    write_csv(outdir / "vehicle_tokens.csv", all_tokens)
    write_csv(outdir / "candidate_wsc_scripts.csv", candidate_scripts)
    write_csv(outdir / "gringo_vehicle_callsite_candidates.csv", gringo_calls)
    write_csv(outdir / "raw_context_clusters.csv", all_clusters)
    write_summary(outdir, inventories, all_strings, all_tokens, all_clusters)
    master = {
        "tool": "codered_vehicle_spawn_research.py",
        "mode": "raw RPF/resource string scan, read-only",
        "inputs": [str(p) for p in collect_inputs(args.inputs)],
        "counts": {
            "archives": len(inventories),
            "vehicle_spawn_strings": len(all_strings),
            "vehicle_tokens": len(all_tokens),
            "candidate_wsc_scripts": len(candidate_scripts),
            "gringo_vehicle_callsite_candidates": len(gringo_calls),
            "raw_context_clusters": len(all_clusters),
        },
        "outputs": {
            "archive_inventory": "archive_inventory.csv",
            "vehicle_spawn_strings": "vehicle_spawn_strings.csv",
            "vehicle_tokens": "vehicle_tokens.csv",
            "candidate_wsc_scripts": "candidate_wsc_scripts.csv",
            "gringo_vehicle_callsite_candidates": "gringo_vehicle_callsite_candidates.csv",
            "raw_context_clusters": "raw_context_clusters.csv",
            "summary": "trainer_spawn_research_summary.md",
        },
    }
    (outdir / "vehicle_spawn_research_master.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
    print(json.dumps(master, indent=2))


if __name__ == "__main__":
    main()
