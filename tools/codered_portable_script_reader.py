#!/usr/bin/env python3
"""Code RED Portable Script Reader.

Read-first, dependency-free script/resource signal scanner for RDR research.

This is not a bytecode decompiler and it does not patch archives. It reads loose
files that were already extracted by Code RED, MagicRDR, SC-CL tooling, or any
other safe extraction lane. It is intended to be portable enough to copy beside
an extracted folder and run with stock Python 3.10+.

Primary use cases:
- find auth/session/freeroam/loading/save/profile signals in extracted scripts
- separate current content evidence from stale/alternate extracted folders
- inspect SCXML/XML/text directly and compiled script resources by mined strings
- produce JSON/CSV/Markdown reports for Code RED follow-up passes

Example:
    python tools/codered_portable_script_reader.py --source logs/magic_rdr_extract --out logs/portable_script_reader

Focused freeroam pass:
    python tools/codered_portable_script_reader.py --source game --out logs/freeroam_reader --profile freeroam
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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}
TEXT_EXTS = {".xml", ".sc", ".txt", ".csv", ".json", ".md", ".log", ".ini", ".cfg", ".dat", ".strtbl"}
DEFAULT_EXTS = SCRIPT_EXTS | TEXT_EXTS | {""}
SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", "build", "dist", "node_modules", ".vs", ".vscode"}

FREEROAM_TERMS = [
    "authenticate", "authentication", "auth", "login", "profile", "ticket", "token", "entitlement", "license",
    "session", "lobby", "host", "client", "join", "leave", "requestjoin", "request_join",
    "freemode", "free_mode", "free-roam", "free_roam", "freeroam", "free roam", "multi_free_roam",
    "multiplayer", "startmultiplayer", "triggermultiplayerload", "startgamewish", "setgamewish",
    "netmachine", "netsessionobject", "hudsceneonline", "readyforinvite", "startonline", "nm_joinprocess",
    "init", "frontend", "loading", "loadscreen", "loading_screen", "safe_spawn", "safespawn", "spawn", "respawn",
    "checkpoint", "save", "gamesave", "savegame", "autosave", "storage",
    "population", "inventory", "dlc_inventory", "bonuspack", "zombiepack", "ultimate", "mooutfitspack",
    "graveyard", "overrun", "wave", "undead", "coffin", "landgrab", "posse",
]

DLC_TERMS = [
    "bonuspack", "bonuspack1", "bonuspack2", "bonuspack3", "zombiepack", "ultimate", "mooutfitspack",
    "init_bonuspack", "init_zombiepack", "init_ultimate", "init_mooutfitspack",
    "graveyard", "coffin", "overrun", "undead", "landgrab", "dlc", "dlc_inventory", "inventory",
    "mp_", "playlist", "gametype", "activity", "minigame", "challenge", "actionarea", "action_area",
]

PATH_ROLE_HINTS = [
    (re.compile(r"ui[/\\]net[/\\]taskmachine", re.I), "ui_runtime_bridge"),
    (re.compile(r"hudsceneonline", re.I), "online_hud_scene"),
    (re.compile(r"plaympconf", re.I), "mp_auth_confirmation_ui"),
    (re.compile(r"pausemenu[/\\]lobby", re.I), "lobby_menu"),
    (re.compile(r"savegame", re.I), "save_profile_ui"),
    (re.compile(r"init[/\\]inventory", re.I), "inventory_manifest"),
    (re.compile(r"release64[/\\]init", re.I), "runtime_init_script"),
    (re.compile(r"dlc[/\\].*init_", re.I), "dlc_init_script"),
    (re.compile(r"zombiepack[/\\]mp[/\\]mp_graveyard", re.I), "zombie_mp_graveyard_activity"),
    (re.compile(r"zombiepack[/\\]mp[/\\]regions", re.I), "zombie_mp_region_activity"),
    (re.compile(r"gringo", re.I), "gringo_script_or_resource"),
    (re.compile(r"socialclub", re.I), "socialclub_or_online_ui"),
]


@dataclass
class StringHit:
    term: str
    offset: int
    line: int | None
    context: str


@dataclass
class FileReport:
    path: str
    relative_path: str
    extension: str
    size: int
    sha1_prefix: str
    kind: str
    role_hints: list[str]
    encoding_mode: str
    string_count: int
    term_hits: list[StringHit] = field(default_factory=list)
    score: int = 0
    confidence: str = "low"
    notes: list[str] = field(default_factory=list)


def normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def lower_path(path: str) -> str:
    return normalize_slashes(path).lower()


def sha1_prefix(path: Path, limit: int = 32 * 1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        remaining = limit
        while remaining > 0:
            chunk = fh.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()[:16]


def safe_relpath(path: Path, root: Path) -> str:
    try:
        return normalize_slashes(str(path.relative_to(root)))
    except ValueError:
        return normalize_slashes(str(path))


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def iter_candidate_files(sources: Sequence[Path], include_exts: set[str], max_file_bytes: int) -> Iterable[tuple[Path, Path]]:
    for source in sources:
        root = source if source.is_dir() else source.parent
        if not source.exists():
            continue
        if source.is_file():
            paths = [source]
        else:
            paths = [p for p in source.rglob("*") if p.is_file()]
        for path in paths:
            if should_skip(path):
                continue
            ext = path.suffix.lower()
            if ext not in include_exts:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > max_file_bytes:
                continue
            yield root, path


def classify_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in SCRIPT_EXTS:
        return "compiled_or_script_resource"
    if ext in TEXT_EXTS:
        if ext == ".xml" or path.name.lower().endswith(".sc.xml"):
            return "scxml_or_xml_text"
        if ext == ".strtbl":
            return "string_table_or_text_resource"
        return "text_resource"
    return "unknown_or_hash_named_resource"


def role_hints_for(rel: str) -> list[str]:
    hints = []
    for pattern, role in PATH_ROLE_HINTS:
        if pattern.search(rel):
            hints.append(role)
    return hints


def printable_ascii_strings(data: bytes, min_len: int = 4) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    start: int | None = None
    buf = bytearray()
    for idx, byte in enumerate(data):
        if 32 <= byte <= 126 or byte in (9,):
            if start is None:
                start = idx
            buf.append(byte)
        else:
            if start is not None and len(buf) >= min_len:
                out.append((start, buf.decode("latin-1", errors="ignore")))
            start = None
            buf.clear()
    if start is not None and len(buf) >= min_len:
        out.append((start, buf.decode("latin-1", errors="ignore")))
    return out


def printable_utf16le_strings(data: bytes, min_chars: int = 4) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    start: int | None = None
    chars: list[str] = []
    for idx in range(0, len(data) - 1, 2):
        lo = data[idx]
        hi = data[idx + 1]
        if hi == 0 and (32 <= lo <= 126 or lo in (9,)):
            if start is None:
                start = idx
            chars.append(chr(lo))
        else:
            if start is not None and len(chars) >= min_chars:
                out.append((start, "".join(chars)))
            start = None
            chars = []
    if start is not None and len(chars) >= min_chars:
        out.append((start, "".join(chars)))
    return out


def read_text_or_strings(path: Path) -> tuple[str, list[tuple[int, str]], str]:
    data = path.read_bytes()
    ext = path.suffix.lower()
    if ext in TEXT_EXTS or path.name.lower().endswith(".sc.xml"):
        for enc in ("utf-8", "utf-16-le", "latin-1"):
            try:
                text = data.decode(enc)
                # Avoid treating arbitrary binary as UTF-16 just because it decodes.
                if enc == "utf-16-le" and "\x00" in text[:200]:
                    continue
                return text, offset_lines_from_text(text), enc
            except UnicodeDecodeError:
                continue
    strings = printable_ascii_strings(data)
    strings.extend(printable_utf16le_strings(data))
    strings.sort(key=lambda pair: pair[0])
    return "\n".join(text for _, text in strings), strings, "mined_strings"


def offset_lines_from_text(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines():
        out.append((offset, line))
        offset += len(line) + 1
    if not out and text:
        out.append((0, text))
    return out


def clean_context(value: str, max_len: int) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_len:
        return value
    half = max_len // 2
    return value[:half].rstrip() + " ... " + value[-half:].lstrip()


def find_term_hits(text_items: list[tuple[int, str]], terms: Sequence[str], context_chars: int, max_hits_per_file: int) -> list[StringHit]:
    hits: list[StringHit] = []
    lower_terms = [(term, term.lower()) for term in terms if term]
    seen: set[tuple[str, int]] = set()
    running_line = 0
    for offset, item in text_items:
        running_line += 1
        low = item.lower()
        for term, low_term in lower_terms:
            start = 0
            while True:
                idx = low.find(low_term, start)
                if idx < 0:
                    break
                abs_offset = offset + idx
                key = (low_term, abs_offset)
                if key not in seen:
                    seen.add(key)
                    ctx_start = max(0, idx - context_chars)
                    ctx_end = min(len(item), idx + len(term) + context_chars)
                    hits.append(StringHit(term=term, offset=abs_offset, line=running_line, context=clean_context(item[ctx_start:ctx_end], context_chars * 2 + 80)))
                    if len(hits) >= max_hits_per_file:
                        return hits
                start = idx + max(1, len(low_term))
    return hits


def confidence_from(score: int, hit_count: int, role_hints: list[str]) -> str:
    if score >= 30 or (hit_count >= 8 and role_hints):
        return "high"
    if score >= 12 or hit_count >= 3:
        return "medium"
    return "low"


def score_file(rel: str, hits: list[StringHit], role_hints: list[str]) -> int:
    score = len(hits)
    low_rel = lower_path(rel)
    if role_hints:
        score += 4 * len(role_hints)
    for bonus in ("taskmachine", "hudsceneonline", "plaympconf", "lobby", "init", "inventory", "bonuspack", "zombiepack"):
        if bonus in low_rel:
            score += 3
    for hit in hits:
        t = hit.term.lower()
        if t in {"triggermultiplayerload", "startmultiplayer", "requestjoin", "startgamewish", "setgamewish", "netmachine", "multi_free_roam"}:
            score += 5
        elif t in {"authenticate", "session", "lobby", "host", "client", "loading", "safe_spawn", "spawn", "savegame"}:
            score += 2
    return score


def analyze_file(path: Path, root: Path, terms: Sequence[str], context_chars: int, max_hits_per_file: int) -> FileReport:
    rel = safe_relpath(path, root)
    size = path.stat().st_size
    kind = classify_kind(path)
    hints = role_hints_for(rel)
    notes: list[str] = []
    try:
        text, text_items, encoding_mode = read_text_or_strings(path)
        hits = find_term_hits(text_items, terms, context_chars, max_hits_per_file)
        string_count = len(text_items)
    except Exception as exc:
        encoding_mode = "read_failed"
        hits = []
        string_count = 0
        notes.append(f"read failed: {type(exc).__name__}: {exc}")
    digest = ""
    try:
        digest = sha1_prefix(path)
    except Exception as exc:
        notes.append(f"sha1 failed: {type(exc).__name__}: {exc}")
    score = score_file(rel, hits, hints)
    confidence = confidence_from(score, len(hits), hints)
    if kind == "compiled_or_script_resource" and encoding_mode == "mined_strings":
        notes.append("compiled/script resource inspected by string mining only; this is not decompilation")
    if path.suffix.lower() == ".strtbl":
        notes.append("string table treated as text/strings; verify encoding before semantic conclusions")
    return FileReport(
        path=normalize_slashes(str(path)),
        relative_path=rel,
        extension=path.suffix.lower(),
        size=size,
        sha1_prefix=digest,
        kind=kind,
        role_hints=hints,
        encoding_mode=encoding_mode,
        string_count=string_count,
        term_hits=hits,
        score=score,
        confidence=confidence,
        notes=notes,
    )


def build_terms(profile: str, extra_terms: Sequence[str]) -> list[str]:
    terms: list[str] = []
    if profile in {"freeroam", "all"}:
        terms.extend(FREEROAM_TERMS)
    if profile in {"dlc", "all"}:
        terms.extend(DLC_TERMS)
    if profile == "basic":
        terms.extend(["init", "session", "loading", "spawn", "save", "profile"])
    terms.extend(extra_terms)
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        clean = term.strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return deduped


def load_terms_from_file(path: Path | None) -> list[str]:
    if not path:
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        out.append(clean)
    return out


def write_reports(out_dir: Path, reports: list[FileReport], terms: list[str], sources: Sequence[Path], args: argparse.Namespace) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_sorted = sorted(reports, key=lambda r: (-r.score, -len(r.term_hits), r.relative_path.lower()))
    hits_flat: list[dict] = []
    for report in reports_sorted:
        for hit in report.term_hits:
            row = asdict(hit)
            row.update({
                "file": report.relative_path,
                "path": report.path,
                "kind": report.kind,
                "role_hints": ";".join(report.role_hints),
                "score": report.score,
                "confidence": report.confidence,
            })
            hits_flat.append(row)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tool": "codered_portable_script_reader.py",
        "sources": [normalize_slashes(str(s)) for s in sources],
        "profile": args.profile,
        "terms": terms,
        "file_count": len(reports_sorted),
        "files_with_hits": sum(1 for r in reports_sorted if r.term_hits),
        "total_hits": len(hits_flat),
        "max_file_mb": args.max_file_mb,
        "note": "Read-first signal scanner only; compiled scripts are mined for strings and are not decompiled.",
    }
    (out_dir / "portable_script_reader_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "portable_script_reader_files.json").write_text(json.dumps([asdict(r) for r in reports_sorted], indent=2), encoding="utf-8")
    (out_dir / "portable_script_reader_hits.json").write_text(json.dumps(hits_flat, indent=2), encoding="utf-8")
    with (out_dir / "portable_script_reader_files.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "relative_path", "extension", "size", "sha1_prefix", "kind", "role_hints", "encoding_mode",
            "string_count", "hit_count", "score", "confidence", "notes",
        ])
        writer.writeheader()
        for report in reports_sorted:
            writer.writerow({
                "relative_path": report.relative_path,
                "extension": report.extension,
                "size": report.size,
                "sha1_prefix": report.sha1_prefix,
                "kind": report.kind,
                "role_hints": ";".join(report.role_hints),
                "encoding_mode": report.encoding_mode,
                "string_count": report.string_count,
                "hit_count": len(report.term_hits),
                "score": report.score,
                "confidence": report.confidence,
                "notes": "; ".join(report.notes),
            })
    with (out_dir / "portable_script_reader_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "term", "offset", "line", "context", "kind", "role_hints", "score", "confidence", "path"])
        writer.writeheader()
        for row in hits_flat:
            writer.writerow(row)
    md = [
        "# Code RED Portable Script Reader Report",
        "",
        f"Generated: {summary['generated_at']}",
        f"Profile: `{args.profile}`",
        f"Sources: {', '.join('`' + normalize_slashes(str(s)) + '`' for s in sources)}",
        f"Files scanned: {summary['file_count']}",
        f"Files with hits: {summary['files_with_hits']}",
        f"Total hits: {summary['total_hits']}",
        "",
        "This is a read-first string/signal report. Compiled script resources are not decompiled.",
        "",
        "## Highest scoring files",
    ]
    for report in reports_sorted[:50]:
        if not report.term_hits and report.score <= 0:
            continue
        roles = ", ".join(report.role_hints) if report.role_hints else "no path-role hint"
        md.append(f"- `{report.relative_path}` — score={report.score}, hits={len(report.term_hits)}, confidence={report.confidence}, role={roles}")
        for hit in report.term_hits[:5]:
            md.append(f"  - `{hit.term}` @ {hit.offset}: {hit.context}")
    if not any(r.term_hits for r in reports_sorted):
        md.append("- No term hits found. Try --profile all, --term, or --extensions to widen the scan.")
    md.extend(["", "## Output files", "", "- `portable_script_reader_summary.json`", "- `portable_script_reader_files.json`", "- `portable_script_reader_hits.json`", "- `portable_script_reader_files.csv`", "- `portable_script_reader_hits.csv`"])
    (out_dir / "portable_script_reader_report.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_extensions(values: Sequence[str]) -> set[str]:
    if not values:
        return set(DEFAULT_EXTS)
    out: set[str] = set()
    for value in values:
        for part in value.split(","):
            clean = part.strip().lower()
            if not clean:
                continue
            if clean == "none":
                out.add("")
            elif clean.startswith("."):
                out.add(clean)
            else:
                out.add("." + clean)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable read-first RDR script/resource signal scanner")
    parser.add_argument("--source", action="append", type=Path, default=[], help="Extracted folder or loose file to scan. Can be repeated.")
    parser.add_argument("--out", type=Path, default=Path("logs/portable_script_reader"), help="Output folder for reports.")
    parser.add_argument("--profile", choices=["freeroam", "dlc", "all", "basic"], default="freeroam", help="Built-in term profile.")
    parser.add_argument("--term", action="append", default=[], help="Extra search term. Can be repeated or comma-separated.")
    parser.add_argument("--terms-file", type=Path, default=None, help="Optional newline-separated search term file.")
    parser.add_argument("--extensions", action="append", default=[], help="Extensions to include, comma-separated. Use 'none' for hash/no-extension files.")
    parser.add_argument("--max-file-mb", type=int, default=32, help="Skip files larger than this many MB.")
    parser.add_argument("--context", type=int, default=96, help="Context chars around each hit.")
    parser.add_argument("--max-hits-per-file", type=int, default=200, help="Prevent huge output from one noisy file.")
    args = parser.parse_args(argv)

    sources = args.source or [Path.cwd()]
    missing = [str(s) for s in sources if not s.exists()]
    if missing:
        print(json.dumps({"ok": False, "missing_sources": missing}, indent=2), file=sys.stderr)
        return 2
    extra_terms: list[str] = []
    for item in args.term:
        extra_terms.extend(part.strip() for part in item.split(",") if part.strip())
    extra_terms.extend(load_terms_from_file(args.terms_file))
    terms = build_terms(args.profile, extra_terms)
    include_exts = parse_extensions(args.extensions)
    max_file_bytes = max(1, args.max_file_mb) * 1024 * 1024
    reports: list[FileReport] = []
    for root, path in iter_candidate_files(sources, include_exts, max_file_bytes):
        reports.append(analyze_file(path, root, terms, args.context, args.max_hits_per_file))
    summary = write_reports(args.out, reports, terms, sources, args)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
