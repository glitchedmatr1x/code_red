#!/usr/bin/env python3
"""Probe the copied MP-injected content.rpf build.

This tool targets the copied archive produced by
`tools/codered_content_rpf_mp_injector.py`:

    build/content_mp_singleplayer/content_mp_singleplayer.rpf

It does not mutate the archive. It parses the rebuilt RPF6 TOC, verifies the
injected multiplayer script tree, optionally extracts selected plain CSC payloads
from the copied archive, and scans for freemode/MP/menu/XLive gating signals so
next passes can focus on runtime activation instead of blind content injection.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"
DEFAULT_ARCHIVE = ROOT / "build" / "content_mp_singleplayer" / "content_mp_singleplayer.rpf"
DEFAULT_MANIFEST = ROOT / "logs" / "content_rpf_mp_singleplayer_injection" / "content_rpf_mp_inject_manifest.json"
DEFAULT_OUT = ROOT / "logs" / "content_mp_singleplayer_build_probe"
SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}
STRING_RE = re.compile(rb"[\x20-\x7e]{4,220}")
SIGNAL_PATTERNS: dict[str, list[str]] = {
    "freemode": [r"freemode", r"free[_ -]?mode"],
    "mp_network": [r"\bmp_", r"\bnet_", r"network", r"session", r"lobby", r"matchmaking", r"host", r"client"],
    "xlive_systemlink": [r"xlive", r"xbox", r"systemlink", r"system_link", r"signin", r"signed", r"profile", r"online"],
    "menu_ui": [r"menu", r"frontend", r"flash", r"ui", r"pause", r"mainmenu", r"button"],
    "spawn_flow": [r"spawn", r"respawn", r"safe_spawn", r"weapon_spawn", r"start_pos"],
    "team_mode": [r"team", r"coop", r"co-op", r"teamwin", r"teamlose", r"teamdef"],
    "graveyard_overrun": [r"graveyard", r"gy_", r"overrun", r"wave", r"zombie", r"undead", r"sudden_death"],
    "script_bootstrap": [r"init", r"startup", r"main", r"load", r"register", r"script"],
}
PATH_GATE_WORDS = ("menu", "frontend", "flash", "ui", "xlive", "xbox", "network", "multiplayer", "mp", "syslink", "systemlink", "signin")


@dataclass
class EntrySummary:
    path: str
    extension: str
    size: int
    offset: int
    is_resource: bool
    category: str


@dataclass
class SignalHit:
    path: str
    category: str
    value: str
    context: str
    offset: int | None


def load_backend() -> Any:
    spec = importlib.util.spec_from_file_location("codered_workbench_backend", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def clean_text(value: bytes | str, limit: int = 260) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", "ignore")
    else:
        text = value
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()[:limit]


def categories_for(text: str) -> list[str]:
    return [category for category, patterns in SIGNAL_PATTERNS.items() if any(re.search(pattern, text, re.I) for pattern in patterns)]


def entry_size(ent: dict[str, Any]) -> int:
    for key in ("size", "size_in_archive", "size_in_memory", "flag1"):
        value = ent.get(key)
        if isinstance(value, int) and value > 0:
            return int(value)
    return 0


def entry_offset(ent: dict[str, Any]) -> int:
    value = ent.get("offset")
    return int(value) if isinstance(value, int) else 0


def read_entry_bytes(archive: Path, ent: dict[str, Any], limit: int = 4 * 1024 * 1024) -> bytes:
    offset = entry_offset(ent)
    size = entry_size(ent)
    if offset <= 0 or size <= 0:
        return b""
    size = min(size, limit)
    with archive.open("rb") as fh:
        fh.seek(offset)
        return fh.read(size)


def classify_entry(path: str) -> str:
    low = path.lower()
    if "/multiplayer/" in low and Path(low).suffix == ".csc":
        return "mp_csc"
    if "/multiplayer/" in low:
        return "mp_resource"
    if any(word in low for word in PATH_GATE_WORDS):
        return "possible_gate_resource"
    return "other"


def collect_entries(info: dict[str, Any]) -> list[EntrySummary]:
    out: list[EntrySummary] = []
    for ent in info.get("entries", []):
        if ent.get("type") != "file":
            continue
        path = str(ent.get("path") or ent.get("name") or "")
        if not path:
            continue
        out.append(
            EntrySummary(
                path=path,
                extension=Path(path.lower()).suffix,
                size=entry_size(ent),
                offset=entry_offset(ent),
                is_resource=bool(ent.get("is_resource")),
                category=classify_entry(path),
            )
        )
    return sorted(out, key=lambda item: item.path.lower())


def scan_payload(path: str, data: bytes) -> list[SignalHit]:
    hits: list[SignalHit] = []
    seen: set[tuple[str, str]] = set()
    for match in STRING_RE.finditer(data):
        value = clean_text(match.group(0), 220)
        cats = categories_for(value)
        if not cats:
            continue
        ctx = clean_text(data[max(0, match.start() - 96):min(len(data), match.end() + 96)])
        for cat in cats:
            key = (cat, value.lower())
            if key in seen:
                continue
            seen.add(key)
            hits.append(SignalHit(path, cat, value, ctx, match.start()))
    return hits


def should_extract(entry: EntrySummary, extract_all_mp_csc: bool) -> bool:
    low = entry.path.lower()
    if extract_all_mp_csc and entry.category == "mp_csc":
        return True
    return any(token in low for token in ("freemode.csc", "network", "session", "menu", "startup", "init")) and entry.extension in SCRIPT_EXTS


def probe_archive(archive: Path, manifest_path: Path, out_dir: Path, extract_all_mp_csc: bool) -> dict[str, Any]:
    wb = load_backend()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"Not a parseable RPF6 archive: {archive}")
    out_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = out_dir / "extracted_signals"
    extract_dir.mkdir(parents=True, exist_ok=True)

    entries = collect_entries(info)
    mp_entries = [entry for entry in entries if entry.category in {"mp_csc", "mp_resource"}]
    mp_csc_entries = [entry for entry in entries if entry.category == "mp_csc"]
    release_mp_csc = [entry for entry in mp_csc_entries if "/content/release/multiplayer/" in entry.path.lower()]
    release64_mp_csc = [entry for entry in mp_csc_entries if "/content/release64/multiplayer/" in entry.path.lower()]
    gate_entries = [entry for entry in entries if entry.category == "possible_gate_resource"]
    freemode_entries = [entry for entry in mp_csc_entries if Path(entry.path.lower()).name == "freemode.csc"]

    hits: list[SignalHit] = []
    extracted_rows: list[dict[str, Any]] = []
    archive_bytes = archive.read_bytes()
    for entry in entries:
        if not should_extract(entry, extract_all_mp_csc):
            continue
        ent = next((raw for raw in info.get("entries", []) if str(raw.get("path") or raw.get("name") or "") == entry.path), None)
        if ent is None:
            continue
        data = read_entry_bytes(archive, ent)
        if not data:
            continue
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", entry.path.strip("/\\"))[:180]
        target = extract_dir / safe_name
        target.write_bytes(data)
        extracted_rows.append({"path": entry.path, "output": str(target), "size": len(data), "sha1": sha1_bytes(data)})
        hits.extend(scan_payload(entry.path, data))

    # Whole-archive string pass catches visible stringtable/menu references even when a specific file is compressed.
    visible_archive_hits: list[SignalHit] = []
    for match in STRING_RE.finditer(archive_bytes):
        value = clean_text(match.group(0), 220)
        cats = categories_for(value)
        if not cats:
            continue
        if not any(key in value.lower() for key in ("freemode", "multiplayer", "mp_", "xlive", "system", "menu", "network", "session", "lobby")):
            continue
        ctx = clean_text(archive_bytes[max(0, match.start() - 96):min(len(archive_bytes), match.end() + 96)])
        for cat in cats:
            visible_archive_hits.append(SignalHit("<archive-visible-strings>", cat, value, ctx, match.start()))
            if len(visible_archive_hits) >= 400:
                break
        if len(visible_archive_hits) >= 400:
            break

    manifest = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            manifest = {"error": str(exc), "path": str(manifest_path)}

    category_counts = Counter(entry.category for entry in entries)
    signal_counts = Counter(hit.category for hit in hits + visible_archive_hits)
    by_folder: dict[str, int] = defaultdict(int)
    for entry in mp_entries:
        parts = entry.path.split("/multiplayer/", 1)
        folder = "multiplayer/root"
        if len(parts) == 2 and "/" in parts[1]:
            folder = parts[1].split("/", 1)[0]
        by_folder[folder] += 1

    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "archive": str(archive),
        "manifest": str(manifest_path) if manifest_path.exists() else "",
        "parse_ok": True,
        "entry_count": info.get("entry_count"),
        "file_entry_count": len(entries),
        "mp_entry_count": len(mp_entries),
        "mp_csc_count": len(mp_csc_entries),
        "release_mp_csc_count": len(release_mp_csc),
        "release64_mp_csc_count": len(release64_mp_csc),
        "freemode_csc_count": len(freemode_entries),
        "gate_candidate_entry_count": len(gate_entries),
        "extracted_signal_file_count": len(extracted_rows),
        "payload_signal_hit_count": len(hits),
        "archive_visible_signal_hit_count": len(visible_archive_hits),
        "entry_category_counts": dict(category_counts),
        "signal_category_counts": dict(signal_counts),
        "mp_entries_by_folder": dict(sorted(by_folder.items())),
        "status": "mp_build_archive_has_freemode_csc" if freemode_entries else "mp_build_archive_missing_freemode_csc",
        "next_likely_targets": [
            "menu/frontend/flash UI gating" if gate_entries else "find menu/frontend/flash UI resources",
            "XLive/System Link/sign-in gate" if signal_counts.get("xlive_systemlink", 0) else "search external executable/scripts for XLive/System Link gates",
            "script startup/bootstrap route for freemode.csc" if freemode_entries else "restore freemode.csc injection",
        ],
    }

    (out_dir / "mp_build_probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "mp_build_probe_entries.json").write_text(json.dumps([asdict(e) for e in entries], indent=2), encoding="utf-8")
    (out_dir / "mp_build_probe_mp_entries.json").write_text(json.dumps([asdict(e) for e in mp_entries], indent=2), encoding="utf-8")
    (out_dir / "mp_build_probe_gate_candidates.json").write_text(json.dumps([asdict(e) for e in gate_entries], indent=2), encoding="utf-8")
    (out_dir / "mp_build_probe_extracted.json").write_text(json.dumps(extracted_rows, indent=2), encoding="utf-8")
    (out_dir / "mp_build_probe_payload_hits.json").write_text(json.dumps([asdict(h) for h in hits], indent=2), encoding="utf-8")
    (out_dir / "mp_build_probe_archive_visible_hits.json").write_text(json.dumps([asdict(h) for h in visible_archive_hits], indent=2), encoding="utf-8")
    if manifest is not None:
        (out_dir / "mp_build_probe_input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with (out_dir / "mp_build_probe_mp_entries.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "extension", "size", "offset", "is_resource", "category"])
        writer.writeheader()
        for entry in mp_entries:
            writer.writerow(asdict(entry))

    lines = [
        "# Code RED MP Build Probe",
        "",
        f"Generated: {summary['generated_at']}",
        f"Archive: `{archive}`",
        f"Parse OK: {summary['parse_ok']}",
        f"Entries: {summary['entry_count']}",
        f"MP entries: {summary['mp_entry_count']}",
        f"MP CSC entries: {summary['mp_csc_count']}",
        f"Release MP CSC: {summary['release_mp_csc_count']}",
        f"Release64 MP CSC: {summary['release64_mp_csc_count']}",
        f"Freemode CSC entries: {summary['freemode_csc_count']}",
        f"Gate candidate entries: {summary['gate_candidate_entry_count']}",
        f"Payload signal hits: {summary['payload_signal_hit_count']}",
        f"Visible archive signal hits: {summary['archive_visible_signal_hit_count']}",
        f"Status: `{summary['status']}`",
        "",
        "## Signal categories",
    ]
    for category, count in sorted(signal_counts.items()):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Freemode entries"])
    for entry in freemode_entries:
        lines.append(f"- `{entry.path}` size={entry.size} offset={entry.offset}")
    if not freemode_entries:
        lines.append("- No `freemode.csc` entries found.")
    lines.extend(["", "## Gate candidate paths"])
    for entry in gate_entries[:120]:
        lines.append(f"- `{entry.path}`")
    if not gate_entries:
        lines.append("- No obvious menu/UI/XLive gate candidate paths found from TOC names.")
    lines.extend(["", "## Next likely targets"])
    for target in summary["next_likely_targets"]:
        lines.append(f"- {target}")
    (out_dir / "mp_build_probe_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe the copied MP-injected content.rpf build.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--extract-all-mp-csc", action="store_true", help="Extract every MP .csc payload from the copied archive for local inspection.")
    args = parser.parse_args(argv)
    if not args.archive.exists():
        raise SystemExit(f"Archive not found: {args.archive}")
    summary = probe_archive(args.archive, args.manifest, args.out, args.extract_all_mp_csc)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("freemode_csc_count", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
