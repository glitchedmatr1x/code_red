#!/usr/bin/env python3
"""Probe packed/binary SC XML UI resources for likely decoder strategy.

This tool is read-only. It consumes the SC XML readability output and the packed
UI target folder, then compares readable XML targets against packed `.sc.xml`
targets. It tries safe transforms and fingerprints:

- magic/header bytes and repeated prefixes;
- endian integer hints;
- raw/zlib/gzip/lzma decompression at several offsets;
- XOR single-byte printable/XML-likeness probes;
- byte-swap and reverse probes;
- visible string density and UI/menu string hints.

It does not claim a full decoder unless a transformed payload becomes XML-like.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import lzma
import math
import re
import struct
import time
import zlib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "logs" / "content_mp_ui_gate_target_pack" / "targets"
DEFAULT_READABILITY = ROOT / "logs" / "content_mp_scxml_readability_probe" / "scxml_readability_files.json"
DEFAULT_OUT = ROOT / "logs" / "content_mp_scxml_decoder_probe"
SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}
STRING_RE = re.compile(rb"[\x20-\x7e]{4,240}")
XML_RE = re.compile(rb"<\s*(?:\?xml|root|screen|scene|menu|data|movie|object|item|entry|page|component|state|button|text|image|panel|list)\b", re.I)
MENU_HINTS = (b"menu", b"frontend", b"pause", b"lobby", b"network", b"system", b"link", b"xlive", b"profile", b"signin", b"multiplayer", b"freemode", b"button", b"playmp", b"offline", b"lan")


@dataclass
class TransformAttempt:
    method: str
    ok: bool
    xml_like: bool
    text_ratio: float
    menu_hints: int
    size: int
    preview: str
    error: str = ""


@dataclass
class DecoderProbe:
    path: str
    size: int
    header_hex: str
    extension: str
    readability_classification: str
    entropy_64k: float
    ascii_ratio_64k: float
    nul_ratio_64k: float
    first_u32_le: int | None
    first_u32_be: int | None
    visible_string_count: int
    menu_string_count: int
    repeated_header_group: str
    best_method: str
    best_xml_like: bool
    best_text_ratio: float
    recommendation: str
    attempts: list[TransformAttempt]
    sample_strings: list[str]


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def ascii_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    return sum(1 for b in data if b in (9, 10, 13) or 32 <= b < 127) / len(data)


def nul_ratio(data: bytes) -> float:
    return data.count(0) / len(data) if data else 0.0


def text_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    return sum(1 for b in data[:8192] if b in (9, 10, 13) or 32 <= b < 127) / min(len(data), 8192)


def clean_preview(data: bytes, limit: int = 320) -> str:
    text = data[:limit].decode("utf-8", "replace").replace("\x00", " ")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def menu_hint_count(data: bytes) -> int:
    low = data[:65536].lower()
    return sum(low.count(hint) for hint in MENU_HINTS)


def is_xml_like(data: bytes) -> bool:
    sample = data[:65536]
    return bool(XML_RE.search(sample)) or (b"<" in sample and b">" in sample and (b"</" in sample or b"/>" in sample))


def visible_strings(data: bytes, limit: int = 40) -> list[str]:
    values = []
    seen = set()
    for match in STRING_RE.finditer(data):
        value = match.group(0).decode("utf-8", "ignore").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(value[:220])
        if len(values) >= limit:
            break
    return values


def menu_strings(data: bytes, limit: int = 40) -> list[str]:
    out = []
    for value in visible_strings(data, 200):
        low = value.lower().encode("utf-8", "ignore")
        if any(h in low for h in MENU_HINTS):
            out.append(value)
            if len(out) >= limit:
                break
    return out


def attempt(method: str, data: bytes) -> TransformAttempt:
    try:
        if method == "identity":
            out = data
        elif method.startswith("zlib@"):
            off = int(method.split("@", 1)[1])
            out = zlib.decompress(data[off:])
        elif method.startswith("zlibraw@"):
            off = int(method.split("@", 1)[1])
            out = zlib.decompress(data[off:], -15)
        elif method.startswith("gzip@"):
            off = int(method.split("@", 1)[1])
            out = gzip.decompress(data[off:])
        elif method.startswith("lzma@"):
            off = int(method.split("@", 1)[1])
            out = lzma.decompress(data[off:])
        elif method == "byteswap16":
            out = bytearray(data)
            for i in range(0, len(out) - 1, 2):
                out[i], out[i + 1] = out[i + 1], out[i]
            out = bytes(out)
        elif method == "reverse":
            out = data[::-1]
        elif method.startswith("xor:"):
            key = int(method.split(":", 1)[1], 16)
            out = bytes(b ^ key for b in data)
        else:
            return TransformAttempt(method, False, False, 0.0, 0, 0, "", "unknown method")
        return TransformAttempt(method, True, is_xml_like(out), round(text_ratio(out), 4), menu_hint_count(out), len(out), clean_preview(out), "")
    except Exception as exc:
        return TransformAttempt(method, False, False, 0.0, 0, 0, "", str(exc))


def xor_candidates(data: bytes) -> list[int]:
    # Test likely keys derived from making first bytes become '<', '{', or ascii letters.
    if not data:
        return []
    keys = {data[0] ^ ord("<"), data[0] ^ ord("{"), data[0] ^ ord("A"), data[0] ^ ord("S")}
    # A few common toy obfuscation values. This is diagnostic only, not a decoder claim.
    keys.update({0xFF, 0xAA, 0x55, 0x80, 0x20})
    return sorted(k for k in keys if 0 <= k <= 255)


def load_readability(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    if isinstance(rows, list):
        for row in rows:
            p = str(row.get("path") or "")
            if p:
                out[Path(p).name.lower()] = row
    return out


def iter_files(source: Path) -> Iterable[Path]:
    if source.is_file():
        return [source]
    return sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: str(p).lower())


def probe_file(path: Path, readability: dict[str, dict]) -> DecoderProbe:
    data = path.read_bytes()
    head = data[:65536]
    methods = ["identity", "byteswap16", "reverse"]
    for off in (0, 2, 4, 8, 12, 16, 32):
        if off < len(data):
            methods.extend([f"zlib@{off}", f"zlibraw@{off}", f"gzip@{off}", f"lzma@{off}"])
    methods.extend([f"xor:{key:02x}" for key in xor_candidates(data[:256])])
    attempts = [attempt(method, data) for method in methods]
    best = sorted(attempts, key=lambda a: (a.xml_like, a.text_ratio, a.menu_hints, a.ok), reverse=True)[0] if attempts else TransformAttempt("none", False, False, 0, 0, 0, "")
    strings = visible_strings(data)
    mstrings = menu_strings(data)
    first_u32_le = struct.unpack_from("<I", data)[0] if len(data) >= 4 else None
    first_u32_be = struct.unpack_from(">I", data)[0] if len(data) >= 4 else None
    read_row = readability.get(path.name.lower(), {})
    classification = str(read_row.get("classification") or "unknown")
    suffix = path.suffix.lower()
    if suffix in SCRIPT_EXTS:
        recommendation = "script binary; keep in Script Workshop/decompiler lane"
    elif best.xml_like:
        recommendation = f"decoder candidate found via {best.method}; inspect transformed preview/output before patching"
    elif best.text_ratio > 0.70:
        recommendation = f"text-like transform via {best.method}, but not XML; inspect manually"
    elif classification == "packed_or_binary_scxml":
        recommendation = "packed/binary SC XML; likely needs dedicated SC UI decoder or MagicRDR resource-viewer export"
    else:
        recommendation = "unknown packed/binary target; compare against MagicRDR decoded output"
    return DecoderProbe(
        path=str(path),
        size=len(data),
        header_hex=data[:32].hex(" "),
        extension=suffix,
        readability_classification=classification,
        entropy_64k=round(entropy(head), 4),
        ascii_ratio_64k=round(ascii_ratio(head), 4),
        nul_ratio_64k=round(nul_ratio(head), 4),
        first_u32_le=first_u32_le,
        first_u32_be=first_u32_be,
        visible_string_count=len(strings),
        menu_string_count=len(mstrings),
        repeated_header_group=data[:8].hex(" "),
        best_method=best.method,
        best_xml_like=best.xml_like,
        best_text_ratio=best.text_ratio,
        recommendation=recommendation,
        attempts=attempts,
        sample_strings=(mstrings or strings)[:20],
    )


def write_outputs(out: Path, source: Path, probes: list[DecoderProbe]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    class_counts = Counter(p.readability_classification for p in probes)
    header_counts = Counter(p.repeated_header_group for p in probes)
    method_counts = Counter(p.best_method for p in probes)
    decoder_hits = [p for p in probes if p.best_xml_like]
    text_hits = [p for p in probes if not p.best_xml_like and p.best_text_ratio > 0.70]
    packed = [p for p in probes if p.readability_classification == "packed_or_binary_scxml"]
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(source),
        "file_count": len(probes),
        "classification_counts": dict(class_counts),
        "best_method_counts": dict(method_counts),
        "common_headers": dict(header_counts.most_common(20)),
        "decoder_xml_like_count": len(decoder_hits),
        "text_like_non_xml_count": len(text_hits),
        "packed_or_binary_scxml_count": len(packed),
        "status": "decoder_candidate_found" if decoder_hits else "dedicated_decoder_needed",
        "decoder_candidates": [asdict(p) for p in decoder_hits[:10]],
        "next_actions": [
            "If decoder_candidate_found, inspect the corresponding transform preview before implementing output extraction.",
            "If dedicated_decoder_needed, compare packed files against MagicRDR/resource-viewer decoded exports.",
            "Prioritize net_profile, lanmenu, networking, offlinemenu, plaympconf, and lobby/main.",
            "Do not patch packed SC XML until a decoder/export path is proven.",
        ],
    }
    (out / "scxml_decoder_probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "scxml_decoder_probe_files.json").write_text(json.dumps([asdict(p) for p in probes], indent=2), encoding="utf-8")
    with (out / "scxml_decoder_probe_files.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["path", "size", "header_hex", "extension", "readability_classification", "entropy_64k", "ascii_ratio_64k", "nul_ratio_64k", "first_u32_le", "first_u32_be", "visible_string_count", "menu_string_count", "repeated_header_group", "best_method", "best_xml_like", "best_text_ratio", "recommendation"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for p in probes:
            row = asdict(p)
            row.pop("attempts", None)
            row.pop("sample_strings", None)
            writer.writerow(row)
    lines = [
        "# Code RED SC XML Decoder Probe",
        "",
        f"Generated: {summary['generated_at']}",
        f"Source: `{source}`",
        f"Files: {len(probes)}",
        f"Status: `{summary['status']}`",
        "",
        "## Common headers",
    ]
    for header, count in header_counts.most_common(20):
        lines.append(f"- `{header}`: {count}")
    lines.extend(["", "## Priority decoder targets"])
    priority_tokens = ("net_profile", "lanmenu", "networking", "offlinemenu", "plaympconf", "lobby_main", "generalmenus")
    ranked = sorted(probes, key=lambda p: (not any(t in Path(p.path).name.lower() for t in priority_tokens), -p.best_text_ratio, -p.menu_string_count))
    for p in ranked[:35]:
        lines.append(f"- `{p.path}` :: {p.readability_classification} :: best={p.best_method} xml={p.best_xml_like} text={p.best_text_ratio} :: {p.recommendation}")
    lines.extend(["", "## Next actions"])
    for action in summary["next_actions"]:
        lines.append(f"- {action}")
    (out / "scxml_decoder_probe_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe packed SC XML targets for decoder strategy.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--readability", type=Path, default=DEFAULT_READABILITY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"Source not found: {args.source}")
    readability = load_readability(args.readability)
    probes = [probe_file(path, readability) for path in iter_files(args.source)]
    summary = write_outputs(args.out, args.source, probes)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
