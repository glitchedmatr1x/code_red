#!/usr/bin/env python3
"""Code RED Magic-RDR parity bridge.

Purpose:
- restore/guard the external Magic-RDR extraction lane that Code RED needs for
  full archive listing/extraction parity when the internal RPF6 path cannot
  decrypt a table by itself.
- keep the workflow read-first and explicit: Code RED does not guess Magic-RDR's
  CLI syntax. Inventory/extract commands run only through user-provided templates
  or a documented local wrapper.

Examples:
    python tools/codered_magic_rdr_bridge.py --check

    python tools/codered_magic_rdr_bridge.py --archive imports/content.rpf \
      --out logs/magic_rdr_inventory \
      --inventory-template '"{magic}" "{archive}" --list --out "{out}"'

    python tools/codered_magic_rdr_bridge.py --archive imports/content.rpf \
      --out logs/magic_rdr_extract \
      --extract-template '"{magic}" "{archive}" --extract "{out}"'

Template variables:
    {magic}   detected or explicit Magic-RDR executable/wrapper path
    {archive} archive path
    {out}     output directory
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_EXTS = {".sco", ".wsc", ".xsc", ".wsv"}
INIT_RE = re.compile(r"(^|[/\\])[^/\\]*init[^/\\]*\.(?:sco|wsc|xsc|wsv)$", re.I)
FREEMODE_WORDS = ("freemode", "free_mode", "free-mode", "mp_", "network", "session", "lobby", "host", "client", "team", "spawn", "graveyard", "overrun", "wave", "zombie")


@dataclass
class BridgeCandidate:
    path: str
    kind: str
    source: str
    exists: bool


@dataclass
class ResourceHit:
    path: str
    extension: str
    init_named: bool
    z_prefixed: bool
    freemode_signal: bool
    category: str


def _which_all(names: list[str]) -> list[str]:
    out: list[str] = []
    for name in names:
        found = shutil.which(name)
        if found:
            out.append(found)
    return out


def detect_magic_rdr(explicit: str = "") -> dict:
    candidates: list[BridgeCandidate] = []
    if explicit:
        p = Path(explicit)
        candidates.append(BridgeCandidate(str(p), "explicit", "--magic", p.exists()))
    for env_name in ("CODERED_MAGIC_RDR", "MAGIC_RDR", "MAGICRDR"):
        value = os.environ.get(env_name)
        if value:
            p = Path(value)
            candidates.append(BridgeCandidate(str(p), "env", env_name, p.exists()))
    for found in _which_all(["MagicRDR", "Magic-RDR", "magic-rdr", "magicrdr", "MagicRDR.exe", "Magic-RDR.exe"]):
        candidates.append(BridgeCandidate(found, "path", "PATH", Path(found).exists()))
    search_roots = [
        REPO_ROOT / "resources",
        REPO_ROOT / "tools",
        REPO_ROOT / "related_apps",
        REPO_ROOT / "data",
        REPO_ROOT,
    ]
    patterns = ["**/MagicRDR*.exe", "**/Magic-RDR*.exe", "**/magic-rdr*", "**/Magic-RDR-main/**", "**/MagicRDR/**"]
    seen_dirs: set[str] = set()
    for root in search_roots:
        if not root.exists():
            continue
        for pattern in patterns:
            for p in root.glob(pattern):
                if p.is_dir():
                    key = str(p.resolve())
                    if key in seen_dirs:
                        continue
                    seen_dirs.add(key)
                    candidates.append(BridgeCandidate(str(p), "resource_dir", pattern, True))
                elif p.exists():
                    candidates.append(BridgeCandidate(str(p), "resource_file", pattern, True))
    deduped: list[BridgeCandidate] = []
    seen: set[str] = set()
    for c in candidates:
        key = c.path.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    runnable = [c for c in deduped if c.exists and Path(c.path).is_file()]
    resource_dirs = [c for c in deduped if c.exists and Path(c.path).is_dir()]
    primary = runnable[0].path if runnable else (resource_dirs[0].path if resource_dirs else "")
    return {
        "primary": primary,
        "runnable": [asdict(c) for c in runnable],
        "resource_dirs": [asdict(c) for c in resource_dirs],
        "candidates": [asdict(c) for c in deduped],
        "available": bool(primary),
        "runnable_available": bool(runnable),
    }


def render_command(template: str, magic: str, archive: Path, out: Path) -> list[str]:
    rendered = template.format(magic=magic, archive=str(archive), out=str(out))
    return shlex.split(rendered, posix=(os.name != "nt"))


def run_template(template: str, magic: str, archive: Path, out: Path, timeout: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    command = render_command(template, magic, archive, out)
    started = time.time()
    try:
        proc = subprocess.run(command, cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "ran": True,
            "command": command,
            "returncode": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "stdout": "\n".join(proc.stdout.splitlines()[:200]),
            "stderr": "\n".join(proc.stderr.splitlines()[:200]),
            "ok": proc.returncode == 0,
        }
    except Exception as exc:
        return {
            "ran": False,
            "command": command,
            "returncode": None,
            "duration_seconds": round(time.time() - started, 3),
            "stdout": "",
            "stderr": str(exc),
            "ok": False,
        }


def scan_output(out: Path) -> tuple[list[ResourceHit], dict]:
    hits: list[ResourceHit] = []
    if not out.exists():
        return hits, {"files_scanned": 0, "text_files_scanned": 0}
    files_scanned = 0
    text_files_scanned = 0
    names: set[str] = set()
    for path in out.rglob("*"):
        if not path.is_file():
            continue
        files_scanned += 1
        rel = str(path.relative_to(out)).replace("\\", "/")
        names.add(rel)
        suffix = path.suffix.lower()
        # Also inspect text reports/lists that Magic-RDR or a wrapper may write.
        if suffix in {".txt", ".csv", ".json", ".md", ".log"}:
            text_files_scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            for m in re.finditer(r"[A-Za-z0-9_ .$@/\\-]{1,180}\.(?:sco|wsc|xsc|wsv|rpf|wtd|wtx|strtbl|xml|csv|dat)", text, re.I):
                names.add(m.group(0).replace("\\", "/"))
    for name in sorted(names, key=str.lower):
        ext = Path(name).suffix.lower()
        if ext not in SCRIPT_EXTS and not any(word in name.lower() for word in FREEMODE_WORDS):
            continue
        stem = Path(name).stem.lower()
        init_named = bool(INIT_RE.search(name)) or "init" in stem
        z_prefixed = stem.startswith("z")
        freemode_signal = any(word in name.lower() for word in FREEMODE_WORDS)
        if ext in SCRIPT_EXTS and init_named and not z_prefixed:
            category = "non_z_init_script"
        elif ext in SCRIPT_EXTS and init_named and z_prefixed:
            category = "z_init_script"
        elif ext in SCRIPT_EXTS:
            category = "script"
        elif freemode_signal:
            category = "freemode_or_mp_signal"
        else:
            category = "other"
        hits.append(ResourceHit(name, ext, init_named, z_prefixed, freemode_signal, category))
    return hits, {"files_scanned": files_scanned, "text_files_scanned": text_files_scanned}


def write_outputs(out: Path, detection: dict, inventory_result: dict, extract_result: dict, hits: list[ResourceHit], scan_stats: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    category_counts = Counter(h.category for h in hits)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "magic_rdr": detection,
        "inventory_result": inventory_result,
        "extract_result": extract_result,
        "scan_stats": scan_stats,
        "hit_count": len(hits),
        "category_counts": dict(category_counts),
        "non_z_init_script_count": category_counts.get("non_z_init_script", 0),
        "freemode_or_mp_signal_count": sum(1 for h in hits if h.freemode_signal),
        "parity_status": "magic_rdr_output_contains_non_z_init_scripts" if category_counts.get("non_z_init_script", 0) else "no_non_z_init_scripts_confirmed_from_magic_rdr_output",
    }
    (out / "magic_rdr_bridge_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "magic_rdr_bridge_hits.json").write_text(json.dumps([asdict(h) for h in hits], indent=2), encoding="utf-8")
    with (out / "magic_rdr_bridge_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "extension", "init_named", "z_prefixed", "freemode_signal", "category"])
        writer.writeheader()
        for hit in hits:
            writer.writerow(asdict(hit))
    lines = [
        "# Code RED Magic-RDR Parity Bridge",
        "",
        f"Generated: {summary['generated_at']}",
        f"Magic-RDR available: {detection.get('available')}",
        f"Runnable available: {detection.get('runnable_available')}",
        f"Primary: `{detection.get('primary') or 'not found'}`",
        f"Hits: {summary['hit_count']}",
        f"Non-z init scripts: {summary['non_z_init_script_count']}",
        f"Freemode/MP signals: {summary['freemode_or_mp_signal_count']}",
        f"Parity status: `{summary['parity_status']}`",
        "",
        "## Categories",
    ]
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Non-z init / MP highlights"])
    for hit in hits[:200]:
        if hit.category == "non_z_init_script" or hit.freemode_signal:
            lines.append(f"- [{hit.category}] `{hit.path}`")
    if not hits:
        lines.append("- No script or MP/freemode hits found in bridge output yet.")
    (out / "magic_rdr_bridge_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED Magic-RDR parity bridge")
    parser.add_argument("--archive", type=Path, default=None, help="RPF archive to inventory/extract")
    parser.add_argument("--out", type=Path, default=Path("logs/magic_rdr_bridge"))
    parser.add_argument("--magic", default="", help="Explicit Magic-RDR executable/wrapper path")
    parser.add_argument("--check", action="store_true", help="Only detect Magic-RDR resources")
    parser.add_argument("--inventory-template", default="", help="Explicit inventory command template using {magic}, {archive}, {out}")
    parser.add_argument("--extract-template", default="", help="Explicit extract command template using {magic}, {archive}, {out}")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--require-runnable", action="store_true", help="Return nonzero if no runnable Magic-RDR executable/wrapper is found")
    args = parser.parse_args(argv)

    detection = detect_magic_rdr(args.magic)
    inventory_result = {"ran": False, "reason": "no inventory template supplied"}
    extract_result = {"ran": False, "reason": "no extract template supplied"}
    if args.require_runnable and not detection.get("runnable_available"):
        summary = write_outputs(args.out, detection, inventory_result, extract_result, [], {"files_scanned": 0, "text_files_scanned": 0})
        print(json.dumps(summary, indent=2))
        return 2
    if args.check or not args.archive:
        summary = write_outputs(args.out, detection, inventory_result, extract_result, [], {"files_scanned": 0, "text_files_scanned": 0})
        print(json.dumps(summary, indent=2))
        return 0 if detection.get("available") else 1
    magic = str(detection.get("primary") or args.magic)
    if not magic:
        summary = write_outputs(args.out, detection, inventory_result, extract_result, [], {"files_scanned": 0, "text_files_scanned": 0})
        print(json.dumps(summary, indent=2))
        return 1
    if args.inventory_template:
        inventory_result = run_template(args.inventory_template, magic, args.archive, args.out / "inventory", args.timeout)
    if args.extract_template:
        extract_result = run_template(args.extract_template, magic, args.archive, args.out / "extracted", args.timeout)
    hits, scan_stats = scan_output(args.out)
    summary = write_outputs(args.out, detection, inventory_result, extract_result, hits, scan_stats)
    print(json.dumps(summary, indent=2))
    return 0 if detection.get("available") else 1


if __name__ == "__main__":
    raise SystemExit(main())
