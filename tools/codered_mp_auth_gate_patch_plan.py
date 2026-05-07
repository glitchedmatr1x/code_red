#!/usr/bin/env python3
"""Build a safe MP auth-gate patch plan from decoded SCXML UI resources.

This tool does not modify archives or game files. It consumes decoded SCXML/XML
outputs from the Zstandard UI decode pass and produces a route/auth report plus
candidate patch-plan records for a local/LAN/System-Link experiment.

Design goals:
- focus only on the LAN/System Link path around NetConf_PlayLAN / PlayMpConf;
- preserve Online/XLive-labelled routes by default;
- identify auth/sign-in gates before any patching;
- emit a patch plan and optional candidate text copies, not an installed patch.

Typical command:

    python tools/codered_mp_auth_gate_patch_plan.py \
      --decoded logs/content_mp_scxml_zstd_probe/decoded \
      --out logs/content_mp_auth_gate_patch_plan \
      --emit-candidates
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECODED = ROOT / "logs" / "content_mp_scxml_zstd_probe" / "decoded"
DEFAULT_ZSTD_SUMMARY = ROOT / "logs" / "content_mp_scxml_zstd_probe" / "scxml_zstd_probe_summary.json"
DEFAULT_OUT = ROOT / "logs" / "content_mp_auth_gate_patch_plan"

ROUTE_TERMS = [
    "NetConf_PlayLAN",
    "PlayMpConf",
    "TriggerMultiplayerLoad",
    "NetMachine.TriggerMultiplayerLoad",
    "NetMachine.Authenticate",
    "NetMachine.ShowSignInUI",
    "auth.fail_NotSignedIn",
    "NetAlert_NotSignedInSysLink",
    "Online Multiplayer",
    "System Link",
    "LAN",
    "networking",
    "offlinemenu",
    "lanmenu",
    "plaympconf",
]

LOCAL_ROUTE_TERMS = ["PlayLAN", "LAN", "System Link", "SysLink", "offlinemenu", "lanmenu", "private", "local"]
ONLINE_ROUTE_TERMS = ["Online Multiplayer", "XLive", "Xbox", "SignedIn", "ShowSignInUI", "profile", "online", "public"]
AUTH_PATTERNS = [
    r"NetMachine\.Authenticate\s*\(",
    r"NetMachine\.ShowSignInUI\s*\(",
    r"auth\.fail_NotSignedIn",
    r"NetAlert_NotSignedInSysLink",
    r"NotSignedIn",
    r"SignedIn",
]
CALL_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?[A-Za-z_][A-Za-z0-9_]*\s*\([^\n<>]{0,240}\)")
INCLUDE_RE = re.compile(r"(?:include|src|file|href|target|screen|scene|goto|route|link)\s*=\s*['\"]([^'\"]+)['\"]", re.I)
TAG_TEXT_RE = re.compile(r">([^<>]{2,220})<")
XMLISH_EXTS = {".xml", ".sc", ".txt", ".dat"}


@dataclass
class RouteHit:
    path: str
    line: int
    category: str
    term: str
    text: str
    local_score: int
    online_score: int


@dataclass
class FileRouteSummary:
    path: str
    route_hits: int
    auth_hits: int
    local_score: int
    online_score: int
    calls: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class PatchPlanItem:
    path: str
    scope: str
    target_terms: list[str]
    action: str
    risk: str
    reason: str
    suggested_strategy: str
    candidate_output: str = ""
    diff_output: str = ""


def clean(text: str, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()[:limit]


def iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: str(p).lower())


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = data.decode(enc)
            if sum(1 for c in text[:2000] if c.isprintable() or c in "\r\n\t") / max(1, min(len(text), 2000)) > 0.65:
                return text
        except Exception:
            continue
    return data.decode("utf-8", "replace")


def score_terms(text: str, terms: list[str]) -> int:
    low = text.lower()
    return sum(low.count(term.lower()) for term in terms)


def classify_hit(line: str, term: str) -> str:
    low = (line + " " + term).lower()
    if "authenticate" in low or "signin" in low or "notsignedin" in low or "signedin" in low or "auth." in low:
        return "auth_gate"
    if "triggermultiplayerload" in low:
        return "runtime_load"
    if "plaympconf" in low or "playlan" in low or "lanmenu" in low or "system link" in low:
        return "lan_route"
    if "online" in low or "xlive" in low or "profile" in low:
        return "online_route"
    return "route_signal"


def find_route_hits(path: Path, text: str) -> list[RouteHit]:
    hits: list[RouteHit] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for term in ROUTE_TERMS:
            if re.search(re.escape(term), line, re.I):
                hits.append(
                    RouteHit(
                        path=str(path),
                        line=line_no,
                        category=classify_hit(line, term),
                        term=term,
                        text=clean(line),
                        local_score=score_terms(line, LOCAL_ROUTE_TERMS),
                        online_score=score_terms(line, ONLINE_ROUTE_TERMS),
                    )
                )
    return hits


def unique_limited(values: Iterable[str], limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = clean(value, 240)
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


def summarize_file(path: Path, text: str, hits: list[RouteHit]) -> FileRouteSummary:
    calls = unique_limited(m.group(0) for m in CALL_RE.finditer(text))
    includes = unique_limited(m.group(1) for m in INCLUDE_RE.finditer(text))
    labels = unique_limited(m.group(1) for m in TAG_TEXT_RE.finditer(text) if any(t.lower() in m.group(1).lower() for t in ROUTE_TERMS + LOCAL_ROUTE_TERMS + ONLINE_ROUTE_TERMS))
    local_score = score_terms(text, LOCAL_ROUTE_TERMS)
    online_score = score_terms(text, ONLINE_ROUTE_TERMS)
    auth_hits = sum(1 for pattern in AUTH_PATTERNS for _ in re.finditer(pattern, text, re.I))
    low_name = path.name.lower()
    if auth_hits and local_score >= online_score:
        rec = "primary local/LAN auth gate candidate"
    elif "plaympconf" in low_name or any("TriggerMultiplayerLoad" in c for c in calls):
        rec = "runtime multiplayer load route candidate"
    elif local_score:
        rec = "supporting LAN/System Link route file"
    elif online_score:
        rec = "online/XLive route file; preserve unless explicitly targeting online route"
    else:
        rec = "supporting route signal"
    return FileRouteSummary(str(path), len(hits), auth_hits, local_score, online_score, calls, includes, labels, rec)


def make_candidate_patch(text: str, file_summary: FileRouteSummary) -> tuple[str, list[str]]:
    """Produce a conservative candidate text copy with comment markers only.

    The goal is not to auto-bypass auth. It marks candidate lines and adds a
    local-only patch block placeholder so a human/Codex pass can inspect exact
    SCXML syntax before a real patch is generated.
    """
    notes: list[str] = []
    lines = text.splitlines()
    out_lines: list[str] = []
    for line in lines:
        should_mark = any(re.search(pattern, line, re.I) for pattern in AUTH_PATTERNS) or re.search(r"TriggerMultiplayerLoad|NetConf_PlayLAN|PlayMpConf", line, re.I)
        if should_mark:
            notes.append(clean(line))
            out_lines.append("<!-- CodeRED_MP_AUTH_GATE_REVIEW: inspect local/LAN-only route before patching -->")
        out_lines.append(line)
    header = [
        "<!--",
        "Code RED MP auth-gate patch candidate COPY ONLY.",
        "This file is not an installed patch.",
        "Purpose: mark LAN/System Link auth/load route lines for manual patch planning.",
        f"Source: {file_summary.path}",
        f"Recommendation: {file_summary.recommendation}",
        "Do not remove online/XLive auth gates blindly.",
        "-->",
    ]
    return "\n".join(header + out_lines) + "\n", notes


def write_candidate_outputs(out_dir: Path, summaries: list[FileRouteSummary], texts: dict[str, str], emit: bool) -> list[PatchPlanItem]:
    candidate_dir = out_dir / "candidate_text_copies"
    diff_dir = out_dir / "candidate_diffs"
    if emit:
        candidate_dir.mkdir(parents=True, exist_ok=True)
        diff_dir.mkdir(parents=True, exist_ok=True)
    items: list[PatchPlanItem] = []
    for summary in summaries:
        if summary.route_hits == 0:
            continue
        low = Path(summary.path).name.lower()
        is_priority = any(token in low for token in ("plaympconf", "lanmenu", "networking", "offlinemenu", "net_profile", "lobby_main", "main.sc", "generalmenus"))
        if not is_priority and summary.auth_hits == 0 and not any("TriggerMultiplayerLoad" in c for c in summary.calls):
            continue
        scope = "local_lan_systemlink" if summary.local_score >= summary.online_score else "online_or_mixed_preserve"
        if summary.auth_hits and scope == "local_lan_systemlink":
            action = "review_auth_gate_for_local_fallback"
            risk = "medium"
            reason = "LAN/System Link route contains sign-in/auth blocker terms."
            strategy = "Create a local-only branch that avoids ShowSignInUI/NotSignedIn alert and preserves args into TriggerMultiplayerLoad."
        elif any("TriggerMultiplayerLoad" in c for c in summary.calls):
            action = "trace_runtime_load_args"
            risk = "medium"
            reason = "File reaches the multiplayer load call."
            strategy = "Confirm arg names/values before calling through Menu Workshop or a copied SCXML route."
        elif scope == "online_or_mixed_preserve":
            action = "preserve_online_auth"
            risk = "high"
            reason = "Route appears online/XLive-labelled."
            strategy = "Do not bypass this route; use it only for reference while targeting LAN/System Link."
        else:
            action = "supporting_route_reference"
            risk = "low"
            reason = "Route supports LAN/System Link menu flow."
            strategy = "Use as context for exact route chain and labels."
        candidate_path = ""
        diff_path = ""
        if emit:
            text = texts.get(summary.path, "")
            candidate_text, _notes = make_candidate_patch(text, summary)
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(summary.path).name)
            target = candidate_dir / f"{safe}.candidate.xml"
            target.write_text(candidate_text, encoding="utf-8")
            candidate_path = str(target)
            diff = "\n".join(
                difflib.unified_diff(
                    text.splitlines(),
                    candidate_text.splitlines(),
                    fromfile=summary.path,
                    tofile=str(target),
                    lineterm="",
                )
            )
            dpath = diff_dir / f"{safe}.candidate.diff"
            dpath.write_text(diff, encoding="utf-8")
            diff_path = str(dpath)
        items.append(
            PatchPlanItem(
                path=summary.path,
                scope=scope,
                target_terms=["NetConf_PlayLAN", "PlayMpConf", "TriggerMultiplayerLoad", "Authenticate", "ShowSignInUI", "NotSignedIn"],
                action=action,
                risk=risk,
                reason=reason,
                suggested_strategy=strategy,
                candidate_output=candidate_path,
                diff_output=diff_path,
            )
        )
    items.sort(key=lambda i: ({"medium": 0, "high": 1, "low": 2}.get(i.risk, 9), i.path.lower()))
    return items


def load_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run(decoded: Path, out_dir: Path, zstd_summary: Path, emit_candidates: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    route_hits: list[RouteHit] = []
    summaries: list[FileRouteSummary] = []
    texts: dict[str, str] = {}
    for path in iter_files(decoded):
        if path.suffix.lower() not in XMLISH_EXTS:
            continue
        text = read_text(path)
        texts[str(path)] = text
        hits = find_route_hits(path, text)
        route_hits.extend(hits)
        summaries.append(summarize_file(path, text, hits))
    summaries.sort(key=lambda s: (s.auth_hits, s.route_hits, s.local_score), reverse=True)
    patch_items = write_candidate_outputs(out_dir, summaries, texts, emit_candidates)
    category_counts = Counter(hit.category for hit in route_hits)
    term_counts = Counter(hit.term for hit in route_hits)
    zstd = load_json(zstd_summary)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "decoded_source": str(decoded),
        "zstd_summary": str(zstd_summary) if zstd_summary.exists() else "",
        "decoded_file_count": len(summaries),
        "files_with_route_hits": sum(1 for s in summaries if s.route_hits),
        "route_hit_count": len(route_hits),
        "auth_hit_file_count": sum(1 for s in summaries if s.auth_hits),
        "patch_plan_item_count": len(patch_items),
        "category_counts": dict(category_counts),
        "term_counts": dict(term_counts),
        "top_route_files": [asdict(s) for s in summaries[:20] if s.route_hits or s.auth_hits],
        "patch_plan": [asdict(item) for item in patch_items],
        "status": "route_patch_plan_ready" if patch_items else "no_patch_plan_targets_found",
        "important_caveat": "This is a patch plan only. It does not remove auth checks or install patched files.",
        "next_actions": [
            "Inspect auth_gate_route_chain.md and proposed_patch_manifest.json.",
            "Prioritize local/LAN/System Link route files, not online/XLive-labelled routes.",
            "If candidate text copies were emitted, inspect them for exact SCXML syntax before producing a real patch.",
            "Only after a real route diff is approved, rebuild a copied content.rpf patch layer and test with rollback ready.",
        ],
    }
    (out_dir / "auth_gate_patch_plan_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "route_hits.json").write_text(json.dumps([asdict(h) for h in route_hits], indent=2), encoding="utf-8")
    (out_dir / "route_file_summaries.json").write_text(json.dumps([asdict(s) for s in summaries], indent=2), encoding="utf-8")
    (out_dir / "proposed_patch_manifest.json").write_text(json.dumps([asdict(item) for item in patch_items], indent=2), encoding="utf-8")
    if zstd is not None:
        (out_dir / "input_zstd_summary.json").write_text(json.dumps(zstd, indent=2), encoding="utf-8")
    with (out_dir / "route_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "line", "category", "term", "text", "local_score", "online_score"])
        writer.writeheader()
        for hit in route_hits:
            writer.writerow(asdict(hit))
    with (out_dir / "proposed_patch_manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "scope", "target_terms", "action", "risk", "reason", "suggested_strategy", "candidate_output", "diff_output"])
        writer.writeheader()
        for item in patch_items:
            row = asdict(item)
            row["target_terms"] = ";".join(item.target_terms)
            writer.writerow(row)
    lines = [
        "# Code RED MP Auth Gate Route Chain",
        "",
        f"Generated: {summary['generated_at']}",
        f"Decoded source: `{decoded}`",
        f"Decoded files scanned: {len(summaries)}",
        f"Route hits: {len(route_hits)}",
        f"Patch-plan items: {len(patch_items)}",
        "",
        "## Known target chain",
        "",
        "```text",
        "NetConf_PlayLAN",
        "→ net/PlayMpConf.sc",
        "→ NetMachine.TriggerMultiplayerLoad(arg2)",
        "```",
        "",
        "## Auth/sign-in blockers to isolate, not blindly delete",
        "",
        "```text",
        "auth.fail_NotSignedIn",
        "NetAlert_NotSignedInSysLink",
        "NetMachine.Authenticate('Online Multiplayer')",
        "NetMachine.ShowSignInUI(true)",
        "```",
        "",
        "## Category counts",
    ]
    for name, count in sorted(category_counts.items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Highest priority files"])
    for item in patch_items[:30]:
        lines.append(f"- `{item.path}` :: {item.scope} :: {item.action} :: risk={item.risk}")
    if not patch_items:
        lines.append("- No patch-plan items found.")
    lines.extend(["", "## Suggested safe experiment"])
    lines.extend([
        "1. Keep online/XLive routes intact.",
        "2. Target only LAN/System Link/local route files.",
        "3. Preserve the argument that reaches `TriggerMultiplayerLoad(arg2)`.",
        "4. Replace the local route's sign-in prompt/alert branch only after exact SCXML syntax is confirmed.",
        "5. Install only through a copied archive/patch layer with rollback.",
    ])
    (out_dir / "auth_gate_route_chain.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a safe patch plan for MP LAN/System Link auth gates from decoded SCXML.")
    parser.add_argument("--decoded", type=Path, default=DEFAULT_DECODED)
    parser.add_argument("--zstd-summary", type=Path, default=DEFAULT_ZSTD_SUMMARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--emit-candidates", action="store_true", help="Write candidate text copies with review markers and diffs. These are not installed patches.")
    args = parser.parse_args(argv)
    if not args.decoded.exists():
        raise SystemExit(f"Decoded folder not found: {args.decoded}")
    summary = run(args.decoded, args.out, args.zstd_summary, args.emit_candidates)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("patch_plan_item_count", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
