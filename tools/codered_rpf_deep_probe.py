#!/usr/bin/env python3
"""Code RED RPF deep probe for init/SCO/WSV/MP signals.

Read-only scanner for RPF-like archives. It does not decrypt, decompress, compile,
or mutate scripts. It searches raw/visible resource regions for file-like names,
init markers, script markers, WSV markers, RSC blocks, and multiplayer/zombie keys.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SCRIPT_EXTS = {".sco", ".wsc", ".xsc", ".wsv"}
WATCH_EXTS = sorted(SCRIPT_EXTS | {".csv", ".xml", ".strtbl", ".txt", ".ini", ".dat", ".wtd", ".wtx", ".wft", ".wvd", ".rpf"})
KEYWORDS = [
    "init", "startup", "script", "sco", "wsc", "xsc", "wsv",
    "mp_", "multiplayer", "network", "net_", "freemode", "coop", "co_",
    "grave", "graveyard", "wave", "zombie", "overrun", "rotation", "team",
]
FILE_RE = re.compile(
    rb"[A-Za-z0-9_$@][A-Za-z0-9_ .$@/\\\-]{0,180}\.(?:"
    + b"|".join(re.escape(ext.lstrip(".").encode("ascii")) for ext in WATCH_EXTS)
    + rb")",
    re.IGNORECASE,
)
ASCII_RE = re.compile(rb"[\x20-\x7e]{4,240}")


@dataclass
class Hit:
    offset: int
    kind: str
    value: str
    category: str
    context: str


def _decode_ascii(raw: bytes) -> str:
    return raw.decode("utf-8", "ignore").strip("\x00\r\n\t ")


def _context(blob: bytes, offset: int, size: int = 96) -> str:
    start = max(0, offset - size)
    end = min(len(blob), offset + size)
    text = blob[start:end].replace(b"\x00", b" ")
    return re.sub(r"\s+", " ", _decode_ascii(text))[:240]


def _category(value: str) -> str:
    low = value.lower()
    ext = Path(low).suffix
    if ext in SCRIPT_EXTS or any(k in low for k in (".sco", ".wsc", ".xsc", ".wsv")):
        return "script"
    if "init" in low:
        return "init"
    if any(k in low for k in ("mp_", "multiplayer", "net_", "network", "freemode", "coop", "co_")):
        return "multiplayer"
    if any(k in low for k in ("zombie", "grave", "graveyard", "wave", "overrun")):
        return "undead_mp"
    if ext in {".csv", ".strtbl", ".txt", ".ini", ".xml", ".dat"}:
        return "data_text"
    return "resource"


def find_rsc_blocks(blob: bytes) -> list[dict[str, int | str]]:
    blocks = []
    pos = 0
    while True:
        pos = blob.find(b"RSC", pos)
        if pos < 0:
            break
        blocks.append({"offset": pos, "magic_preview_hex": blob[pos:pos + 16].hex()})
        pos += 3
    return blocks


def iter_file_hits(blob: bytes, limit: int) -> Iterable[Hit]:
    seen: set[tuple[int, str]] = set()
    for match in FILE_RE.finditer(blob):
        value = _decode_ascii(match.group(0)).replace("\\", "/")
        if not value:
            continue
        key = (match.start(), value.lower())
        if key in seen:
            continue
        seen.add(key)
        yield Hit(match.start(), "file_like", value, _category(value), _context(blob, match.start()))
        if len(seen) >= limit:
            return


def iter_keyword_hits(blob: bytes, limit: int) -> Iterable[Hit]:
    seen: set[tuple[int, str]] = set()
    for match in ASCII_RE.finditer(blob):
        value = _decode_ascii(match.group(0))
        low = value.lower()
        if not any(k in low for k in KEYWORDS):
            continue
        if len(value) < 5 and not any(k in low for k in ("sco", "wsv", "mp_")):
            continue
        key = (match.start(), value.lower())
        if key in seen:
            continue
        seen.add(key)
        yield Hit(match.start(), "keyword_string", value, _category(value), _context(blob, match.start()))
        if len(seen) >= limit:
            return


def probe(path: Path, out_dir: Path, limit: int = 5000) -> dict:
    blob = path.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    hits: list[Hit] = []
    hits.extend(iter_file_hits(blob, limit))
    if len(hits) < limit:
        hits.extend(iter_keyword_hits(blob, limit - len(hits)))

    deduped: list[Hit] = []
    seen_values: set[tuple[str, str]] = set()
    for hit in sorted(hits, key=lambda h: h.offset):
        key = (hit.category, hit.value.lower())
        if key in seen_values:
            continue
        seen_values.add(key)
        deduped.append(hit)

    rsc_blocks = find_rsc_blocks(blob)
    category_counts = Counter(hit.category for hit in deduped)
    ext_counts = Counter(Path(hit.value.lower()).suffix for hit in deduped if Path(hit.value.lower()).suffix)

    summary = {
        "archive": str(path),
        "size_bytes": len(blob),
        "header_ascii": _decode_ascii(blob[:4]),
        "is_rpf6": blob[:4].upper().startswith(b"RPF6"),
        "rsc_block_count": len(rsc_blocks),
        "hit_count": len(deduped),
        "category_counts": dict(category_counts),
        "extension_counts": dict(ext_counts),
        "important_categories": {
            "init": [asdict(h) for h in deduped if h.category == "init"][:200],
            "script": [asdict(h) for h in deduped if h.category == "script"][:200],
            "multiplayer": [asdict(h) for h in deduped if h.category == "multiplayer"][:300],
            "undead_mp": [asdict(h) for h in deduped if h.category == "undead_mp"][:300],
        },
    }

    (out_dir / "rpf_deep_probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "rpf_rsc_blocks.json").write_text(json.dumps(rsc_blocks, indent=2), encoding="utf-8")
    with (out_dir / "rpf_deep_probe_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["offset", "kind", "category", "value", "context"])
        writer.writeheader()
        for hit in deduped:
            writer.writerow(asdict(hit))

    lines = [
        "# Code RED RPF Deep Probe",
        "",
        f"Archive: `{path}`",
        f"Size: {len(blob):,} bytes",
        f"Header: `{_decode_ascii(blob[:4])}`",
        f"RPF6: {summary['is_rpf6']}",
        f"RSC blocks: {len(rsc_blocks):,}",
        f"Unique hits: {len(deduped):,}",
        "",
        "## Category counts",
    ]
    for name, count in sorted(category_counts.items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Init hits"])
    for hit in [h for h in deduped if h.category == "init"][:50]:
        lines.append(f"- `{hit.value}` @ {hit.offset}")
    lines.extend(["", "## Script / SCO / WSV hits"])
    for hit in [h for h in deduped if h.category == "script"][:80]:
        lines.append(f"- `{hit.value}` @ {hit.offset}")
    lines.extend(["", "## Multiplayer / Undead MP highlights"])
    for hit in [h for h in deduped if h.category in {"multiplayer", "undead_mp"}][:120]:
        lines.append(f"- `{hit.value}` @ {hit.offset}")
    (out_dir / "rpf_deep_probe_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED RPF deep probe for init/SCO/WSV/MP signals")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args(argv)
    out = args.out or Path(f"Code_RED_RPF_Deep_Probe_{args.archive.stem}")
    summary = probe(args.archive, out, limit=args.limit)
    print(json.dumps({k: summary[k] for k in ("archive", "size_bytes", "is_rpf6", "rsc_block_count", "hit_count", "category_counts", "extension_counts")}, indent=2))
    return 0 if summary.get("is_rpf6") else 1


if __name__ == "__main__":
    raise SystemExit(main())
