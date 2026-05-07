#!/usr/bin/env python3
"""Package focused MP UI gate targets from the copied content.rpf.

This read-only helper consumes the MP menu gate probe output and the copied
MP-injected content archive. It extracts the highest-priority UI/menu/XLive/
System Link candidate payloads into a small inspection pack and writes a patch
planning report.

It intentionally avoids broad extraction and ignores report-file noise. It does
not mutate the archive or game folder.
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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"
DEFAULT_ARCHIVE = ROOT / "build" / "content_mp_singleplayer" / "content.rpf"
DEFAULT_CANDIDATES = ROOT / "logs" / "content_mp_menu_gate_probe" / "mp_menu_gate_probe_candidates.json"
DEFAULT_OUT = ROOT / "logs" / "content_mp_ui_gate_target_pack"

PRIORITY_PATHS = [
    "root/content/ui/pausemenu/net_profile.sc.xml",
    "root/content/ui/pausemenu/net/lanmenu.sc.xml",
    "root/content/ui/pausemenu/lobby/main.sc.xml",
    "root/content/ui/pausemenu/lobby/friends.sc.xml",
    "root/content/ui/pausemenu/lobby/currentgamers.sc.xml",
    "root/content/ui/pausemenu/lobby/recentgamers.sc.xml",
    "root/content/ui/pausemenu/lobby/netplayercontextmenu.sc.xml",
    "root/content/ui/pausemenu/networking.sc.xml",
    "root/content/ui/pausemenu/net/offlinemenu.sc.xml",
    "root/content/ui/pausemenu/net/plaympconf.sc.xml",
    "root/content/ui/generalmenus.sc.xml",
    "root/content/release64/multiplayer/freemode/freemode.csc",
    "root/content/release/multiplayer/freemode/freemode.csc",
]

CATEGORY_PRIORITY = {
    "xlive_gate": 100,
    "system_link_gate": 95,
    "session_flow": 90,
    "menu_frontend": 85,
    "ui_flash": 75,
    "freemode_entry": 70,
    "script_bootstrap": 65,
    "mp_script_tree": 50,
}
STRING_RE = re.compile(rb"[\x20-\x7e]{4,240}")


@dataclass
class PackedTarget:
    archive_path: str
    output_path: str
    extension: str
    size: int
    offset: int
    sha1: str
    categories: list[str]
    score: int
    priority_reason: str
    visible_strings: list[str]
    note: str


def load_backend() -> Any:
    spec = importlib.util.spec_from_file_location("codered_workbench_backend", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def safe_name(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/\\"))[:180]


def read_entry_bytes(archive: Path, ent: dict[str, Any]) -> bytes:
    offset = int(ent.get("offset") or 0)
    size = int(ent.get("size") or ent.get("size_in_archive") or ent.get("flag1") or 0)
    if offset <= 0 or size <= 0:
        return b""
    with archive.open("rb") as fh:
        fh.seek(offset)
        return fh.read(size)


def visible_strings(data: bytes, limit: int = 40) -> list[str]:
    out: list[str] = []
    for match in STRING_RE.finditer(data):
        value = match.group(0).decode("utf-8", "ignore").strip()
        if not value:
            continue
        low = value.lower()
        if any(token in low for token in ("menu", "net", "live", "system", "link", "lobby", "session", "freemode", "multi", "button", "profile", "signin", "lan", "play")):
            out.append(value[:220])
            if len(out) >= limit:
                break
    return out


def load_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def candidate_priority(row: dict[str, Any]) -> int:
    cats = set(row.get("path_categories") or []) | set(row.get("payload_categories") or [])
    score = int(row.get("score") or 0)
    score += sum(CATEGORY_PRIORITY.get(cat, 0) for cat in cats)
    path = str(row.get("path") or "").lower()
    if path in {p.lower() for p in PRIORITY_PATHS}:
        score += 250
    if "/ui/pausemenu/net" in path or "/ui/pausemenu/lobby" in path:
        score += 150
    if "freemode.csc" in path:
        score += 130
    if path.endswith(".strtbl") and "zombiepack" in path:
        score -= 160
    return score


def select_targets(candidates: list[dict[str, Any]], max_targets: int) -> list[dict[str, Any]]:
    by_path = {str(row.get("path") or "").lower(): row for row in candidates if row.get("path")}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in PRIORITY_PATHS:
        row = by_path.get(path.lower())
        if row:
            selected.append(row)
            seen.add(path.lower())
    ranked = sorted(candidates, key=candidate_priority, reverse=True)
    for row in ranked:
        path = str(row.get("path") or "").lower()
        if not path or path in seen:
            continue
        cats = set(row.get("path_categories") or []) | set(row.get("payload_categories") or [])
        if cats & {"xlive_gate", "system_link_gate", "session_flow", "menu_frontend", "freemode_entry"}:
            selected.append(row)
            seen.add(path)
        if len(selected) >= max_targets:
            break
    return selected[:max_targets]


def reason_for(row: dict[str, Any]) -> str:
    path = str(row.get("path") or "")
    cats = set(row.get("path_categories") or []) | set(row.get("payload_categories") or [])
    if "xlive_gate" in cats:
        return "XLive/sign-in/profile gate candidate"
    if "system_link_gate" in cats:
        return "System Link/LAN gate candidate"
    if "session_flow" in cats:
        return "lobby/session route candidate"
    if "freemode_entry" in cats:
        return "freemode runtime bootstrap candidate"
    if "/ui/pausemenu" in path.lower():
        return "pause menu route/visibility candidate"
    return "supporting MP UI candidate"


def pack_targets(archive: Path, candidates_path: Path, out_dir: Path, max_targets: int) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = out_dir / "targets"
    extract_dir.mkdir(parents=True, exist_ok=True)
    candidates = load_candidates(candidates_path)
    selected = select_targets(candidates, max_targets)
    wb = load_backend()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"Not a parseable RPF6 archive: {archive}")
    entries = {str(ent.get("path") or ent.get("name") or "").lower(): ent for ent in info.get("entries", []) if ent.get("type") == "file"}
    packed: list[PackedTarget] = []
    missing: list[str] = []
    for row in selected:
        archive_path = str(row.get("path") or "")
        ent = entries.get(archive_path.lower())
        if ent is None:
            missing.append(archive_path)
            continue
        data = read_entry_bytes(archive, ent)
        target = extract_dir / safe_name(archive_path)
        target.write_bytes(data)
        cats = sorted(set(row.get("path_categories") or []) | set(row.get("payload_categories") or []))
        packed.append(
            PackedTarget(
                archive_path=archive_path,
                output_path=str(target),
                extension=Path(archive_path).suffix.lower(),
                size=len(data),
                offset=int(ent.get("offset") or 0),
                sha1=sha1(data),
                categories=cats,
                score=candidate_priority(row),
                priority_reason=reason_for(row),
                visible_strings=visible_strings(data),
                note="binary/high-entropy payload; inspect with Code RED viewer/decompiler if text is not readable" if not (Path(archive_path).suffix.lower() in {".strtbl", ".txt", ".csv", ".xml"}) else "candidate extracted for direct inspection",
            )
        )
    packed.sort(key=lambda p: p.score, reverse=True)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "archive": str(archive),
        "candidates_source": str(candidates_path),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "packed_count": len(packed),
        "missing_count": len(missing),
        "missing": missing,
        "top_targets": [asdict(p) for p in packed[:15]],
        "next_actions": [
            "Open extracted pausemenu/net and pausemenu/lobby SC XML payloads first.",
            "Compare net_profile.sc.xml, lanmenu.sc.xml, networking.sc.xml, and lobby/main.sc.xml for hidden/disabled MP route entries.",
            "If XML payloads look compressed/encrypted, route them through Code RED resource viewer/decompressor before patching.",
            "Use Menu Workshop or ScriptHook to create a controlled freemode.csc load/probe action after UI route candidates are identified.",
        ],
    }
    (out_dir / "mp_ui_gate_target_pack_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "mp_ui_gate_target_pack_manifest.json").write_text(json.dumps([asdict(p) for p in packed], indent=2), encoding="utf-8")
    with (out_dir / "mp_ui_gate_target_pack_manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["archive_path", "output_path", "extension", "size", "offset", "sha1", "categories", "score", "priority_reason", "note"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for item in packed:
            row = asdict(item)
            row["categories"] = ";".join(item.categories)
            row.pop("visible_strings", None)
            writer.writerow(row)
    lines = [
        "# Code RED MP UI Gate Target Pack",
        "",
        f"Generated: {summary['generated_at']}",
        f"Archive: `{archive}`",
        f"Packed targets: {len(packed)}",
        "",
        "## Priority targets",
    ]
    for item in packed[:30]:
        lines.append(f"- score={item.score} `{item.archive_path}` -> `{item.output_path}` :: {item.priority_reason}")
    lines.extend(["", "## Next actions"])
    for action in summary["next_actions"]:
        lines.append(f"- {action}")
    (out_dir / "mp_ui_gate_target_pack_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract/package focused MP UI gate targets from copied content.rpf.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-targets", type=int, default=40)
    args = parser.parse_args(argv)
    if not args.archive.exists():
        raise SystemExit(f"Archive not found: {args.archive}")
    if not args.candidates.exists():
        raise SystemExit(f"Candidate file not found: {args.candidates}")
    summary = pack_targets(args.archive, args.candidates, args.out, args.max_targets)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
