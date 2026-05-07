#!/usr/bin/env python3
"""Code RED MP menu/runtime gate probe.

This is the next pass after `codered_mp_build_probe.py` and
`codered_mp_gate_hunt.py`.

It focuses on real archive paths/resources instead of report files:
- parses the copied MP-injected content.rpf;
- ranks actual archive entries that look like menu/frontend/UI/XLive/System Link
  or freemode/session/bootstrap gates;
- optionally extracts/scans candidate payload bytes from the copied archive;
- writes a concise target list for the next patch or Menu Workshop runtime probe.

It is read-only and does not mutate archives.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
import importlib.util
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"
DEFAULT_ARCHIVE = ROOT / "build" / "content_mp_singleplayer" / "content.rpf"
DEFAULT_BUILD_PROBE = ROOT / "logs" / "content_mp_singleplayer_build_probe"
DEFAULT_GATE_HUNT = ROOT / "logs" / "content_mp_gate_hunt"
DEFAULT_OUT = ROOT / "logs" / "content_mp_menu_gate_probe"
STRING_RE = re.compile(rb"[\x20-\x7e]{4,240}")

GATE_PATTERNS: dict[str, list[str]] = {
    "freemode_entry": [r"\bfreemode\b", r"free[_ -]?mode"],
    "mp_script_tree": [r"/multiplayer/", r"\\multiplayer\\", r"\bmp_", r"multi[_ -]?player"],
    "menu_frontend": [r"menu", r"frontend", r"mainmenu", r"pausemenu", r"startmenu", r"button", r"label"],
    "ui_flash": [r"flash", r"scaleform", r"gfx", r"swf", r"hud", r"ui"],
    "xlive_gate": [r"xlive", r"x_live", r"xbox", r"signin", r"signed[_ -]?in", r"profile", r"gamertag", r"online"],
    "system_link_gate": [r"system[_ -]?link", r"syslink", r"lan", r"network[_ -]?session", r"private[_ -]?session"],
    "session_flow": [r"session", r"lobby", r"matchmaking", r"join", r"host", r"client", r"peer", r"invite"],
    "script_bootstrap": [r"startup", r"bootstrap", r"register", r"load[_ -]?script", r"script[_ -]?loader", r"launch", r"init"],
    "spawn_enablement": [r"spawn", r"respawn", r"player[_ -]?spawn", r"safe[_ -]?spawn", r"weapon[_ -]?spawn"],
    "graveyard_overrun": [r"graveyard", r"overrun", r"zombie", r"undead", r"wave", r"sudden[_ -]?death"],
}

CATEGORY_WEIGHTS = {
    "freemode_entry": 18,
    "menu_frontend": 16,
    "ui_flash": 14,
    "xlive_gate": 14,
    "system_link_gate": 13,
    "session_flow": 11,
    "script_bootstrap": 10,
    "mp_script_tree": 7,
    "spawn_enablement": 5,
    "graveyard_overrun": 2,
}

EXT_WEIGHTS = {
    ".csc": 10,
    ".sco": 10,
    ".wsc": 10,
    ".xsc": 10,
    ".wsv": 8,
    ".strtbl": 8,
    ".xml": 8,
    ".csv": 6,
    ".txt": 5,
    ".ini": 5,
    ".dat": 5,
    ".gfx": 5,
    ".swf": 5,
    ".wtd": 2,
    ".wtx": 2,
}

SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}
TEXTLIKE_EXTS = {".txt", ".csv", ".json", ".xml", ".ini", ".dat", ".strtbl", ".log", ".md"}


@dataclass
class ArchiveCandidate:
    path: str
    extension: str
    size: int
    offset: int
    is_resource: bool
    path_categories: list[str]
    payload_categories: list[str] = field(default_factory=list)
    visible_strings: list[str] = field(default_factory=list)
    entropy_64k: float = 0.0
    ascii_ratio_64k: float = 0.0
    score: int = 0
    recommendation: str = ""
    extraction_note: str = ""


@dataclass
class GateHit:
    path: str
    category: str
    value: str
    context: str
    offset: int | None
    source: str


def load_backend() -> Any:
    spec = importlib.util.spec_from_file_location("codered_workbench_backend", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def clean(value: str | bytes, limit: int = 280) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    return re.sub(r"\s+", " ", value.replace("\x00", " ")).strip()[:limit]


def categories_for(text: str) -> list[str]:
    return [cat for cat, patterns in GATE_PATTERNS.items() if any(re.search(p, text, re.I) for p in patterns)]


def entry_size(ent: dict[str, Any]) -> int:
    for key in ("size", "size_in_archive", "size_in_memory", "flag1"):
        value = ent.get(key)
        if isinstance(value, int) and value > 0:
            return int(value)
    return 0


def entry_offset(ent: dict[str, Any]) -> int:
    value = ent.get("offset")
    return int(value) if isinstance(value, int) else 0


def read_entry_bytes(archive: Path, ent: dict[str, Any], limit: int) -> bytes:
    offset = entry_offset(ent)
    size = entry_size(ent)
    if offset <= 0 or size <= 0:
        return b""
    with archive.open("rb") as fh:
        fh.seek(offset)
        return fh.read(min(size, limit))


def scan_payload(path: str, data: bytes, limit_hits: int = 40) -> tuple[list[GateHit], list[str]]:
    hits: list[GateHit] = []
    strings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for match in STRING_RE.finditer(data):
        value = clean(match.group(0), 240)
        cats = categories_for(value)
        if cats and len(strings) < limit_hits:
            strings.append(value)
        if not cats:
            continue
        ctx = clean(data[max(0, match.start() - 96):min(len(data), match.end() + 96)])
        for cat in cats:
            key = (cat, value.lower())
            if key in seen:
                continue
            seen.add(key)
            hits.append(GateHit(path, cat, value, ctx, match.start(), "payload"))
            if len(hits) >= limit_hits:
                return hits, strings
    return hits, strings


def recommendation_for(categories: set[str], extension: str, is_resource: bool) -> str:
    if {"menu_frontend", "ui_flash"} & categories:
        return "primary UI/menu gate candidate; inspect for hidden/disabled MP button or frontend route"
    if {"xlive_gate", "system_link_gate"} & categories:
        return "primary online/System Link gate candidate; inspect sign-in/session branch"
    if {"freemode_entry", "session_flow", "script_bootstrap"} & categories:
        return "freemode/session bootstrap candidate; inspect runtime script load route"
    if extension in SCRIPT_EXTS and "mp_script_tree" in categories:
        return "MP script candidate; use Menu Workshop/ScriptHook probe to test addressability"
    if is_resource:
        return "resource payload may need decompression/viewer before patch target can be confirmed"
    return "supporting signal; keep for cross-reference"


def candidate_score(path: str, extension: str, categories: Iterable[str], is_resource: bool) -> int:
    cats = set(categories)
    score = EXT_WEIGHTS.get(extension, 0) + sum(CATEGORY_WEIGHTS.get(cat, 0) for cat in cats)
    low = path.lower()
    if "freemode" in low:
        score += 18
    if "frontend" in low or "menu" in low:
        score += 12
    if "multiplayer" in low:
        score += 8
    if is_resource:
        score -= 2
    return score


def load_prior_report_paths(build_probe_dir: Path, gate_hunt_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = {"build_probe_summary": None, "gate_hunt_summary": None, "prior_top_files": []}
    for key, path in {
        "build_probe_summary": build_probe_dir / "mp_build_probe_summary.json",
        "gate_hunt_summary": gate_hunt_dir / "mp_gate_hunt_summary.json",
    }.items():
        if path.exists():
            try:
                data[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                data[key] = {"error": str(exc), "path": str(path)}
    scores = gate_hunt_dir / "mp_gate_hunt_file_scores.json"
    if scores.exists():
        try:
            rows = json.loads(scores.read_text(encoding="utf-8"))
            data["prior_top_files"] = rows[:25]
        except Exception:
            pass
    return data


def parse_archive_candidates(archive: Path, read_payloads: bool, max_read_bytes: int) -> tuple[list[ArchiveCandidate], list[GateHit], dict[str, Any]]:
    wb = load_backend()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"Not a parseable RPF6 archive: {archive}")

    raw_entries = [ent for ent in info.get("entries", []) if ent.get("type") == "file"]
    candidates: list[ArchiveCandidate] = []
    hits: list[GateHit] = []
    for ent in raw_entries:
        path = str(ent.get("path") or ent.get("name") or "")
        if not path:
            continue
        extension = Path(path.lower()).suffix
        path_cats = categories_for(path)
        is_script_mp = extension in SCRIPT_EXTS and "/multiplayer/" in path.lower()
        is_possible_menu_resource = bool(path_cats) or any(token in path.lower() for token in ("menu", "frontend", "flash", "ui", "xlive", "system", "session", "multiplayer", "freemode"))
        if not is_script_mp and not is_possible_menu_resource:
            continue
        size = entry_size(ent)
        offset = entry_offset(ent)
        is_resource = bool(ent.get("is_resource"))
        cand = ArchiveCandidate(
            path=path,
            extension=extension,
            size=size,
            offset=offset,
            is_resource=is_resource,
            path_categories=path_cats,
            score=candidate_score(path, extension, path_cats, is_resource),
            recommendation=recommendation_for(set(path_cats), extension, is_resource),
        )
        if read_payloads and size > 0 and offset > 0:
            data = read_entry_bytes(archive, ent, max_read_bytes)
            cand.entropy_64k = round(entropy(data[:65536]), 4)
            cand.ascii_ratio_64k = round(ascii_ratio(data[:65536]), 4)
            if data:
                payload_hits, visible = scan_payload(path, data)
                hits.extend(payload_hits)
                cand.visible_strings = visible[:20]
                cand.payload_categories = sorted({hit.category for hit in payload_hits})
                all_cats = set(cand.path_categories) | set(cand.payload_categories)
                cand.score = candidate_score(path, extension, all_cats, is_resource) + len(payload_hits)
                cand.recommendation = recommendation_for(all_cats, extension, is_resource)
                if cand.entropy_64k > 7.5 and cand.ascii_ratio_64k < 0.25:
                    cand.extraction_note = "high-entropy/resource-like payload; may need resource decompression or viewer"
                elif visible:
                    cand.extraction_note = "payload has visible strings"
                else:
                    cand.extraction_note = "no visible gate strings in bounded payload scan"
        candidates.append(cand)

    candidates.sort(key=lambda c: (c.score, c.size), reverse=True)
    meta = {
        "entry_count": info.get("entry_count"),
        "file_entry_count": len(raw_entries),
        "candidate_count": len(candidates),
    }
    return candidates, hits, meta


def write_outputs(out_dir: Path, archive: Path, candidates: list[ArchiveCandidate], hits: list[GateHit], meta: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    category_counts = Counter(cat for cand in candidates for cat in (set(cand.path_categories) | set(cand.payload_categories)))
    rec_counts = Counter(cand.recommendation for cand in candidates)
    top = candidates[:40]
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "archive": str(archive),
        "parse_meta": meta,
        "candidate_count": len(candidates),
        "payload_hit_count": len(hits),
        "category_counts": dict(category_counts),
        "recommendation_counts": dict(rec_counts),
        "top_candidate": asdict(top[0]) if top else None,
        "top_recommendation": top[0].recommendation if top else "no target candidates found",
        "next_actions": [
            "Inspect top menu/frontend/UI candidates first; these are the likely hidden MP button or route files.",
            "Inspect XLive/System Link candidates for branches that return false/offline and hide multiplayer.",
            "Use Menu Workshop/ScriptHook to create a controlled runtime probe for freemode.csc instead of more content injection.",
            "If a top target is high-entropy/resource-like, route it through the resource viewer/decompressor before patching.",
        ],
    }
    (out_dir / "mp_menu_gate_probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "mp_menu_gate_probe_candidates.json").write_text(json.dumps([asdict(c) for c in candidates], indent=2), encoding="utf-8")
    (out_dir / "mp_menu_gate_probe_payload_hits.json").write_text(json.dumps([asdict(h) for h in hits], indent=2), encoding="utf-8")
    (out_dir / "mp_menu_gate_probe_prior_context.json").write_text(json.dumps(prior, indent=2), encoding="utf-8")
    with (out_dir / "mp_menu_gate_probe_candidates.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = [
            "path", "extension", "size", "offset", "is_resource", "path_categories", "payload_categories",
            "entropy_64k", "ascii_ratio_64k", "score", "recommendation", "extraction_note",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for cand in candidates:
            row = asdict(cand)
            row["path_categories"] = ";".join(cand.path_categories)
            row["payload_categories"] = ";".join(cand.payload_categories)
            row.pop("visible_strings", None)
            writer.writerow(row)
    with (out_dir / "mp_menu_gate_probe_payload_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "category", "value", "context", "offset", "source"])
        writer.writeheader()
        for hit in hits:
            writer.writerow(asdict(hit))

    lines = [
        "# Code RED MP Menu Gate Probe",
        "",
        f"Generated: {summary['generated_at']}",
        f"Archive: `{archive}`",
        f"Entries: {meta.get('entry_count')}``",
        f"File entries: {meta.get('file_entry_count')}``",
        f"Candidate archive paths: {len(candidates)}",
        f"Payload hits: {len(hits)}",
        f"Top recommendation: `{summary['top_recommendation']}`",
        "",
        "## Category counts",
    ]
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Top archive targets"])
    for cand in top[:25]:
        cats = sorted(set(cand.path_categories) | set(cand.payload_categories))
        lines.append(f"- score={cand.score} `{cand.path}` cats={','.join(cats) or '-'} :: {cand.recommendation}")
    if not top:
        lines.append("- No archive-path candidates found.")
    lines.extend(["", "## Next actions"])
    for action in summary["next_actions"]:
        lines.append(f"- {action}")
    (out_dir / "mp_menu_gate_probe_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank real archive paths for MP menu/runtime gate investigation.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--build-probe", type=Path, default=DEFAULT_BUILD_PROBE)
    parser.add_argument("--gate-hunt", type=Path, default=DEFAULT_GATE_HUNT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-payload-scan", action="store_true", help="Only rank by archive paths; do not read payload bytes.")
    parser.add_argument("--max-read-bytes", type=int, default=4 * 1024 * 1024)
    args = parser.parse_args(argv)
    if not args.archive.exists():
        raise SystemExit(f"Archive not found: {args.archive}")
    prior = load_prior_report_paths(args.build_probe, args.gate_hunt)
    candidates, hits, meta = parse_archive_candidates(args.archive, not args.no_payload_scan, args.max_read_bytes)
    summary = write_outputs(args.out, args.archive, candidates, hits, meta, prior)
    print(json.dumps(summary, indent=2))
    return 0 if candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
