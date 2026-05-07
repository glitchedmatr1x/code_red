#!/usr/bin/env python3
"""Extract precise decoded-SCXML route/auth blocks for MP LAN patch planning.

This tool is read-only. It consumes decoded SCXML output and the auth-gate patch
plan, then writes focused snippets around the actual route/auth/load terms:

- NetConf_PlayLAN
- net/PlayMpConf.sc / PlayMpConf
- NetMachine.TriggerMultiplayerLoad(arg2)
- NetMachine.Authenticate(...)
- NetMachine.ShowSignInUI(true)
- auth.fail_NotSignedIn
- NetAlert_NotSignedInSysLink

It does not patch archives or decoded files. Its purpose is to make the next
patch pass surgical instead of guessing from broad reports.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECODED = ROOT / "logs" / "content_mp_scxml_zstd_probe" / "decoded"
DEFAULT_PLAN = ROOT / "logs" / "content_mp_auth_gate_patch_plan" / "auth_gate_patch_plan_summary.json"
DEFAULT_OUT = ROOT / "logs" / "content_mp_route_block_extract"

TERMS = [
    "NetConf_PlayLAN",
    "PlayMpConf",
    "net/PlayMpConf.sc",
    "NetMachine.TriggerMultiplayerLoad",
    "TriggerMultiplayerLoad",
    "NetMachine.Authenticate",
    "NetMachine.ShowSignInUI",
    "auth.fail_NotSignedIn",
    "NetAlert_NotSignedInSysLink",
    "NotSignedIn",
    "Online Multiplayer",
    "System Link",
    "LAN",
]

PRIORITY_FILENAMES = [
    "root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_networking.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_net_offlinemenu.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml",
]

CALL_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?[A-Za-z_][A-Za-z0-9_]*\s*\([^\n<>]{0,260}\)")
STATE_RE = re.compile(r"(?:Enter|Exit|goto|Include|Exclude|Select|Focus|Unfocus|Activate|Deactivate|SendEvent|SendDelayedEvent|RemoveDelayedEvent)\s*\([^\n<>]{0,260}\)")
XML_TAG_RE = re.compile(r"<\/?([A-Za-z0-9_:.\-]+)")


@dataclass
class BlockHit:
    path: str
    file_name: str
    line: int
    term: str
    category: str
    snippet_start_line: int
    snippet_end_line: int
    snippet_text: str
    calls: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class FileBlockSummary:
    path: str
    file_name: str
    hit_count: int
    categories: dict[str, int]
    terms: dict[str, int]
    priority: str
    output_markdown: str


def clean(text: str, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()[:limit]


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = data.decode(enc)
            if text and sum(1 for c in text[:4000] if c.isprintable() or c in "\r\n\t") / max(1, min(len(text), 4000)) > 0.65:
                return text
        except Exception:
            pass
    return data.decode("utf-8", "replace")


def iter_files(decoded: Path) -> Iterable[Path]:
    if decoded.is_file():
        return [decoded]
    return sorted((p for p in decoded.rglob("*.xml") if p.is_file()), key=lambda p: str(p).lower())


def categorize(term: str, line: str) -> str:
    low = f"{term} {line}".lower()
    if "triggermultiplayerload" in low:
        return "runtime_load"
    if "authenticate" in low or "signin" in low or "notsignedin" in low or "auth." in low:
        return "auth_gate"
    if "plaympconf" in low:
        return "plaympconf_route"
    if "playlan" in low or "system link" in low or "lan" in low:
        return "lan_route"
    return "route_signal"


def unique(values: Iterable[str], limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = clean(value, 260)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def extract_snippet(lines: list[str], hit_idx: int, radius: int) -> tuple[int, int, str]:
    start = max(0, hit_idx - radius)
    end = min(len(lines), hit_idx + radius + 1)

    # Expand a little to catch immediate XML block boundaries when close by.
    for i in range(hit_idx, max(-1, hit_idx - radius - 10), -1):
        if i < 0:
            break
        if re.search(r"<[^/!][^>]*>$", lines[i].strip()) or re.search(r"<(state|transition|event|item|button|screen|component|scene)\b", lines[i], re.I):
            start = min(start, i)
            break
    for i in range(hit_idx, min(len(lines), hit_idx + radius + 10)):
        if re.search(r"</(state|transition|event|item|button|screen|component|scene)>", lines[i], re.I):
            end = max(end, i + 1)
            break
    numbered = [f"{idx + 1:05d}: {lines[idx]}" for idx in range(start, end)]
    return start + 1, end, "\n".join(numbered)


def find_hits(path: Path, text: str, radius: int) -> list[BlockHit]:
    lines = text.splitlines()
    hits: list[BlockHit] = []
    for idx, line in enumerate(lines):
        for term in TERMS:
            if re.search(re.escape(term), line, re.I):
                start, end, snippet = extract_snippet(lines, idx, radius)
                calls = unique(m.group(0) for m in CALL_RE.finditer(snippet))
                states = unique(m.group(0) for m in STATE_RE.finditer(snippet))
                tags = unique((m.group(1) for m in XML_TAG_RE.finditer(snippet)), 40)
                hits.append(
                    BlockHit(
                        path=str(path),
                        file_name=path.name,
                        line=idx + 1,
                        term=term,
                        category=categorize(term, line),
                        snippet_start_line=start,
                        snippet_end_line=end,
                        snippet_text=snippet,
                        calls=calls,
                        states=states,
                        tags=tags,
                    )
                )
    return hits


def prioritize(path: Path, hits: list[BlockHit]) -> str:
    name = path.name.lower()
    cats = {h.category for h in hits}
    if "lanmenu" in name and "auth_gate" in cats:
        return "primary_lan_auth_gate"
    if "plaympconf" in name and "runtime_load" in cats:
        return "primary_runtime_load"
    if "networking" in name:
        return "route_graph_reference"
    if "offlinemenu" in name:
        return "offline_menu_reference"
    if "lobby_main" in name or "lobby" in name:
        return "lobby_route_reference"
    return "supporting_reference"


def write_file_markdown(out_dir: Path, path: Path, hits: list[BlockHit]) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.name)
    target = out_dir / f"{safe}.route_blocks.md"
    lines = [
        f"# Route blocks: {path.name}",
        "",
        f"Source: `{path}`",
        f"Hits: {len(hits)}",
        f"Priority: `{prioritize(path, hits)}`",
        "",
    ]
    for i, hit in enumerate(hits, start=1):
        lines.extend([
            f"## Hit {i}: {hit.term} / {hit.category}",
            "",
            f"Line: {hit.line}",
            f"Snippet lines: {hit.snippet_start_line}-{hit.snippet_end_line}",
            "",
            "Calls/states in snippet:",
        ])
        for call in unique(hit.calls + hit.states, 40):
            lines.append(f"- `{call}`")
        lines.extend(["", "```xml", hit.snippet_text, "```", ""])
    target.write_text("\n".join(lines), encoding="utf-8")
    return str(target)


def load_plan(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run(decoded: Path, plan: Path, out: Path, radius: int, priority_only: bool) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    blocks_dir = out / "route_blocks"
    all_hits: list[BlockHit] = []
    summaries: list[FileBlockSummary] = []
    files = list(iter_files(decoded))
    if priority_only:
        wanted = {name.lower() for name in PRIORITY_FILENAMES}
        files = [p for p in files if p.name.lower() in wanted]
    for path in files:
        text = read_text(path)
        hits = find_hits(path, text, radius)
        if not hits:
            continue
        all_hits.extend(hits)
        cat_counts = Counter(hit.category for hit in hits)
        term_counts = Counter(hit.term for hit in hits)
        md = write_file_markdown(blocks_dir, path, hits)
        summaries.append(
            FileBlockSummary(
                path=str(path),
                file_name=path.name,
                hit_count=len(hits),
                categories=dict(cat_counts),
                terms=dict(term_counts),
                priority=prioritize(path, hits),
                output_markdown=md,
            )
        )
    priority_order = {
        "primary_lan_auth_gate": 0,
        "primary_runtime_load": 1,
        "route_graph_reference": 2,
        "offline_menu_reference": 3,
        "lobby_route_reference": 4,
        "supporting_reference": 9,
    }
    summaries.sort(key=lambda s: (priority_order.get(s.priority, 99), -s.hit_count, s.file_name.lower()))
    category_counts = Counter(hit.category for hit in all_hits)
    term_counts = Counter(hit.term for hit in all_hits)
    plan_data = load_plan(plan)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "decoded_source": str(decoded),
        "auth_patch_plan": str(plan) if plan.exists() else "",
        "files_considered": len(files),
        "files_with_hits": len(summaries),
        "block_hit_count": len(all_hits),
        "category_counts": dict(category_counts),
        "term_counts": dict(term_counts),
        "file_summaries": [asdict(s) for s in summaries],
        "status": "route_blocks_ready" if all_hits else "no_route_blocks_found",
        "next_actions": [
            "Open the primary lanmenu and plaympconf route block markdown files first.",
            "Confirm the exact SCXML syntax around Authenticate/ShowSignInUI and TriggerMultiplayerLoad.",
            "Create a copied-file candidate patch only after the exact before/after block is understood.",
            "Do not patch online/profile/netstats routes unless a separate explicit online route experiment is created.",
        ],
    }
    (out / "route_block_extract_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "route_block_hits.json").write_text(json.dumps([asdict(h) for h in all_hits], indent=2), encoding="utf-8")
    if plan_data is not None:
        (out / "input_auth_patch_plan_summary.json").write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
    with (out / "route_block_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["path", "file_name", "line", "term", "category", "snippet_start_line", "snippet_end_line"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for hit in all_hits:
            row = asdict(hit)
            row.pop("snippet_text", None)
            row.pop("calls", None)
            row.pop("states", None)
            row.pop("tags", None)
            writer.writerow(row)
    lines = [
        "# Code RED MP Route Block Extract",
        "",
        f"Generated: {summary['generated_at']}",
        f"Decoded source: `{decoded}`",
        f"Files with hits: {len(summaries)}",
        f"Block hits: {len(all_hits)}",
        "",
        "## Category counts",
    ]
    for name, count in sorted(category_counts.items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Priority block files"])
    for s in summaries[:20]:
        lines.append(f"- `{s.priority}` `{s.file_name}` -> `{s.output_markdown}`")
    lines.extend(["", "## Next actions"])
    for action in summary["next_actions"]:
        lines.append(f"- {action}")
    (out / "route_block_extract_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract exact decoded-SCXML route/auth blocks for MP LAN patch planning.")
    parser.add_argument("--decoded", type=Path, default=DEFAULT_DECODED)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--radius", type=int, default=12, help="Number of lines around each hit to include before boundary expansion.")
    parser.add_argument("--all-files", action="store_true", help="Scan all decoded XML files instead of only priority route files.")
    args = parser.parse_args(argv)
    if not args.decoded.exists():
        raise SystemExit(f"Decoded folder not found: {args.decoded}")
    summary = run(args.decoded, args.plan, args.out, args.radius, not args.all_files)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("block_hit_count", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
