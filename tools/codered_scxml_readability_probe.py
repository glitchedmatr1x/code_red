#!/usr/bin/env python3
"""Probe readability/decoding status of packed SC XML UI gate targets.

This read-only helper is the next pass after:

    tools/codered_mp_ui_gate_target_packer.py

It checks whether extracted `.sc.xml` UI/menu gate files are:
- directly readable XML/text;
- UTF-16 text/XML;
- zlib/gzip/lzma-compressed XML/text;
- binary/packed UI resources that need a Code RED/MagicRDR resource decoder;
- script binaries such as `.csc` that should go through Script Workshop instead.

It does not patch files or mutate archives.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import lzma
import math
import re
import time
import zlib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "logs" / "content_mp_ui_gate_target_pack" / "targets"
DEFAULT_MANIFEST = ROOT / "logs" / "content_mp_ui_gate_target_pack" / "mp_ui_gate_target_pack_manifest.json"
DEFAULT_OUT = ROOT / "logs" / "content_mp_scxml_readability_probe"
TEXT_EXTS = {".xml", ".txt", ".csv", ".strtbl", ".md", ".log", ".ini", ".dat"}
SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}
STRING_RE = re.compile(rb"[\x20-\x7e]{4,240}")
XML_HINT_RE = re.compile(r"<\s*(?:\?xml|root|screen|scene|menu|data|movie|object|item|entry|page|component|state|button|text|image|panel|list)\b", re.I)
MENU_HINTS = ("menu", "frontend", "pause", "lobby", "network", "system", "link", "xlive", "profile", "signin", "multiplayer", "freemode", "button", "playmp", "offline", "lan")


@dataclass
class DecodeAttempt:
    method: str
    ok: bool
    text_like: bool
    xml_like: bool
    size: int
    preview: str
    error: str = ""


@dataclass
class FileProbe:
    path: str
    extension: str
    size: int
    entropy_64k: float
    ascii_ratio_64k: float
    nul_ratio_64k: float
    header_hex: str
    classification: str
    recommendation: str
    best_method: str
    xml_like: bool
    text_like: bool
    menu_hint_count: int
    visible_strings: list[str]
    attempts: list[DecodeAttempt]


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def ratio_ascii(data: bytes) -> float:
    if not data:
        return 0.0
    return sum(1 for b in data if b in (9, 10, 13) or 32 <= b < 127) / len(data)


def ratio_nul(data: bytes) -> float:
    if not data:
        return 0.0
    return data.count(0) / len(data)


def clean_preview(text: str, limit: int = 420) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def is_text_like(text: str) -> bool:
    if not text:
        return False
    printable = sum(1 for ch in text[:4096] if ch in "\r\n\t" or 32 <= ord(ch) < 127)
    sample = min(len(text), 4096)
    return sample > 0 and printable / sample > 0.72


def is_xml_like(text: str) -> bool:
    if not text:
        return False
    sample = text[:8192]
    return bool(XML_HINT_RE.search(sample)) or ("<" in sample and ">" in sample and ("</" in sample or "/>" in sample))


def menu_hint_count(text: str) -> int:
    low = text.lower()
    return sum(low.count(hint) for hint in MENU_HINTS)


def decode_bytes(data: bytes, method: str) -> DecodeAttempt:
    try:
        if method == "utf-8":
            text = data.decode("utf-8", errors="replace")
        elif method == "latin-1":
            text = data.decode("latin-1", errors="replace")
        elif method == "utf-16-le":
            text = data.decode("utf-16-le", errors="replace")
        elif method == "utf-16-be":
            text = data.decode("utf-16-be", errors="replace")
        elif method == "gzip+utf-8":
            text = gzip.decompress(data).decode("utf-8", errors="replace")
        elif method == "zlib+utf-8":
            text = zlib.decompress(data).decode("utf-8", errors="replace")
        elif method == "zlib_raw+utf-8":
            text = zlib.decompress(data, -15).decode("utf-8", errors="replace")
        elif method == "lzma+utf-8":
            text = lzma.decompress(data).decode("utf-8", errors="replace")
        else:
            return DecodeAttempt(method, False, False, False, 0, "", "unknown method")
        return DecodeAttempt(method, True, is_text_like(text), is_xml_like(text), len(text), clean_preview(text), "")
    except Exception as exc:
        return DecodeAttempt(method, False, False, False, 0, "", str(exc))


def visible_strings(data: bytes, limit: int = 80) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in STRING_RE.finditer(data):
        value = match.group(0).decode("utf-8", "ignore").strip()
        if not value:
            continue
        low = value.lower()
        if any(hint in low for hint in MENU_HINTS) or len(values) < 12:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(value[:220])
            if len(values) >= limit:
                break
    return values


def is_script_path(path: Path) -> bool:
    return path.suffix.lower() in SCRIPT_EXTS


def classify(path: Path, data: bytes, attempts: list[DecodeAttempt]) -> tuple[str, str, str, bool, bool, int]:
    suffix = path.suffix.lower()
    best_xml = next((a for a in attempts if a.ok and a.xml_like), None)
    best_text = next((a for a in attempts if a.ok and a.text_like), None)
    best = best_xml or best_text or next((a for a in attempts if a.ok), None)
    best_method = best.method if best else "none"
    text_for_hints = best.preview if best else ""
    hints = menu_hint_count(text_for_hints + "\n" + "\n".join(visible_strings(data, 30)))
    if suffix in SCRIPT_EXTS:
        return (
            "script_binary",
            "Route through Script Workshop/decompile-template lane; do not treat as patchable SC XML.",
            best_method,
            False,
            False,
            hints,
        )
    if best_xml:
        return (
            "direct_or_decoded_xml",
            "Patch planning can inspect this as XML. Preserve original path and rebuild only copied archives/patch layers.",
            best_method,
            True,
            True,
            hints,
        )
    if best_text:
        return (
            "text_but_not_xml",
            "Readable text found, but not XML-shaped. Inspect for route labels/ids before patching.",
            best_method,
            False,
            True,
            hints,
        )
    head = data[:65536]
    if entropy(head) > 7.4 and ratio_ascii(head) < 0.50:
        return (
            "packed_or_binary_scxml",
            "Needs SC XML/UI resource decoder or MagicRDR/resource-viewer extraction before safe patching.",
            best_method,
            False,
            False,
            hints,
        )
    return (
        "unknown_binary_or_sparse_text",
        "Do not patch blindly. Compare with MagicRDR decoded output or add a format-specific decoder.",
        best_method,
        False,
        False,
        hints,
    )


def iter_target_files(source: Path) -> Iterable[Path]:
    if not source.exists():
        return []
    if source.is_file():
        return [source]
    return sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: str(p).lower())


def probe_file(path: Path) -> FileProbe:
    data = path.read_bytes()
    methods = ["utf-8", "utf-16-le", "utf-16-be", "gzip+utf-8", "zlib+utf-8", "zlib_raw+utf-8", "lzma+utf-8", "latin-1"]
    attempts = [decode_bytes(data, method) for method in methods]
    classification, recommendation, best_method, xml_like, text_like, hints = classify(path, data, attempts)
    head = data[:65536]
    return FileProbe(
        path=str(path),
        extension=path.suffix.lower(),
        size=len(data),
        entropy_64k=round(entropy(head), 4),
        ascii_ratio_64k=round(ratio_ascii(head), 4),
        nul_ratio_64k=round(ratio_nul(head), 4),
        header_hex=data[:32].hex(" "),
        classification=classification,
        recommendation=recommendation,
        best_method=best_method,
        xml_like=xml_like,
        text_like=text_like,
        menu_hint_count=hints,
        visible_strings=visible_strings(data),
        attempts=attempts,
    )


def load_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def write_outputs(out_dir: Path, source: Path, manifest_path: Path, probes: list[FileProbe]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_path)
    counts = Counter(p.classification for p in probes)
    ext_counts = Counter(p.extension for p in probes)
    readable_xml = [p for p in probes if p.classification == "direct_or_decoded_xml" and p.xml_like and p.extension not in SCRIPT_EXTS]
    packed = [p for p in probes if p.classification == "packed_or_binary_scxml"]
    scripts = [p for p in probes if p.classification == "script_binary"]
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(source),
        "manifest": str(manifest_path) if manifest_path.exists() else "",
        "target_file_count": len(probes),
        "manifest_count": len(manifest),
        "classification_counts": dict(counts),
        "extension_counts": dict(ext_counts),
        "readable_xml_count": len(readable_xml),
        "packed_or_binary_scxml_count": len(packed),
        "script_binary_count": len(scripts),
        "status": "direct_xml_available" if readable_xml else "decoder_needed_for_scxml_targets",
        "top_patchable_xml": [p.path for p in readable_xml[:20]],
        "top_decoder_needed": [p.path for p in packed[:20]],
        "script_binary_targets": [p.path for p in scripts[:20]],
        "next_actions": [
            "If readable XML exists, inspect route/button/menu ids before patch planning.",
            "If SC XML targets are packed/binary, restore or add an SC XML/UI resource decoder before patching.",
            "Keep freemode.csc in Script Workshop/decompiler lane; it is not directly patchable XML.",
            "Use copied archive/patch-layer output only; do not mutate live content.rpf.",
        ],
    }
    (out_dir / "scxml_readability_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "scxml_readability_files.json").write_text(json.dumps([asdict(p) for p in probes], indent=2), encoding="utf-8")
    with (out_dir / "scxml_readability_files.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = [
            "path", "extension", "size", "entropy_64k", "ascii_ratio_64k", "nul_ratio_64k", "header_hex",
            "classification", "recommendation", "best_method", "xml_like", "text_like", "menu_hint_count",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for probe in probes:
            row = asdict(probe)
            row.pop("visible_strings", None)
            row.pop("attempts", None)
            writer.writerow(row)
    lines = [
        "# Code RED SC XML Readability Probe",
        "",
        f"Generated: {summary['generated_at']}",
        f"Source: `{source}`",
        f"Target files: {len(probes)}",
        f"Status: `{summary['status']}`",
        "",
        "## Classification counts",
    ]
    for name, count in sorted(counts.items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Highest priority files"])
    priority_order = {"direct_or_decoded_xml": 0, "text_but_not_xml": 1, "packed_or_binary_scxml": 2, "script_binary": 3, "unknown_binary_or_sparse_text": 4}
    ranked = sorted(probes, key=lambda p: (priority_order.get(p.classification, 99), -p.menu_hint_count, -p.size))
    for probe in ranked[:40]:
        lines.append(f"- `{probe.path}` :: {probe.classification} via {probe.best_method} :: {probe.recommendation}")
    lines.extend(["", "## Next actions"])
    for action in summary["next_actions"]:
        lines.append(f"- {action}")
    (out_dir / "scxml_readability_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe SC XML target readability/decoder requirements.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"Source not found: {args.source}")
    files = list(iter_target_files(args.source))
    probes = [probe_file(path) for path in files]
    summary = write_outputs(args.out, args.source, args.manifest, probes)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
