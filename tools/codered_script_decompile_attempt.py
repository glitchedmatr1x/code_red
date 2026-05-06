#!/usr/bin/env python3
"""Code RED script decompile attempt workflow.

Read-first helper for init/SCO/WSV investigations.

It can:
- inspect an RPF for visible init/script names and RSC block candidates
- classify false positive text hits such as "score" containing "sco"
- inventory extracted .sco/.wsc/.xsc/.wsv files
- run an explicit decompiler template only when requested

It does not decrypt, mutate, or write back archives.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SCRIPT_EXTS = {".sco", ".wsc", ".xsc", ".wsv"}
KEYWORDS = ["init", "main", "startup", "script", "sco", "wsc", "xsc", "wsv", "mp_", "graveyard", "zombie", "wave", "network"]
FILE_NAME_RE = re.compile(rb"[A-Za-z0-9_$@][A-Za-z0-9_ .$@/\\\-]{0,180}\.(?:sco|wsc|xsc|wsv)", re.IGNORECASE)
ASCII_RE = re.compile(rb"[\x20-\x7e]{4,220}")


@dataclass
class RscCandidate:
    index: int
    offset: int
    size_to_next_rsc: int
    header_hex: str
    entropy_4k: float
    ascii_ratio_4k: float
    status: str
    notes: list[str]


@dataclass
class StringHit:
    offset: int
    kind: str
    value: str
    category: str
    context: str
    status: str


@dataclass
class ScriptFile:
    path: str
    extension: str
    size: int
    sha1_prefix: str
    status: str
    notes: list[str]


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


def clean(raw: bytes) -> str:
    return raw.decode("utf-8", "ignore").strip("\x00\r\n\t ")


def context(blob: bytes, offset: int, window: int = 96) -> str:
    part = blob[max(0, offset - window):min(len(blob), offset + window)].replace(b"\x00", b" ")
    return re.sub(r"\s+", " ", clean(part))[:260]


def sha1_prefix(path: Path, limit: int = 16 * 1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        left = limit
        while left > 0:
            chunk = fh.read(min(1024 * 1024, left))
            if not chunk:
                break
            h.update(chunk)
            left -= len(chunk)
    return h.hexdigest()[:16]


def classify_string(value: str) -> tuple[str, str]:
    low = value.lower()
    suffix = Path(low).suffix
    if suffix in SCRIPT_EXTS:
        return "script_filename", "candidate_script_name"
    if "init" in low:
        return "init_signal", "visible_text_only"
    if "sco" in low and ".sco" not in low:
        return "sco_text_false_positive", "not_a_script_filename"
    if any(k in low for k in ("mp_", "network", "graveyard", "zombie", "wave")):
        return "mp_script_signal", "visible_text_only"
    if any(k in low for k in ("script", "wsc", "xsc", "wsv")):
        return "script_signal", "visible_text_only"
    return "other", "visible_text_only"


def scan_rpf(path: Path, limit: int = 5000) -> dict:
    blob = path.read_bytes()
    rsc_offsets = [m.start() for m in re.finditer(b"RSC", blob)]
    candidates: list[RscCandidate] = []
    for idx, off in enumerate(rsc_offsets):
        end = rsc_offsets[idx + 1] if idx + 1 < len(rsc_offsets) else len(blob)
        chunk = blob[off:min(end, off + 4096)]
        ent = entropy(chunk[16:])
        ar = ascii_ratio(chunk[16:])
        notes = []
        if ent > 7.5 and ar < 0.35:
            status = "blocked_compressed_or_encrypted_rsc"
            notes.append("High entropy RSC payload; needs RPF/RSC extractor before decompile")
        else:
            status = "inspectable_rsc_candidate"
            notes.append("Lower entropy or text-bearing RSC candidate")
        candidates.append(RscCandidate(idx, off, end - off, blob[off:off + 16].hex(), round(ent, 4), round(ar, 4), status, notes))

    hits: list[StringHit] = []
    seen: set[tuple[str, str]] = set()
    for match in FILE_NAME_RE.finditer(blob):
        value = clean(match.group(0)).replace("\\", "/")
        category, status = classify_string(value)
        key = (category, value.lower())
        if key in seen:
            continue
        seen.add(key)
        hits.append(StringHit(match.start(), "file_like", value, category, context(blob, match.start()), status))
        if len(hits) >= limit:
            break

    if len(hits) < limit:
        for match in ASCII_RE.finditer(blob):
            value = clean(match.group(0))
            low = value.lower()
            if not any(k in low for k in KEYWORDS):
                continue
            category, status = classify_string(value)
            key = (category, value.lower())
            if key in seen:
                continue
            seen.add(key)
            hits.append(StringHit(match.start(), "keyword_string", value, category, context(blob, match.start()), status))
            if len(hits) >= limit:
                break

    return {
        "archive": str(path),
        "size_bytes": len(blob),
        "header_ascii": clean(blob[:4]),
        "is_rpf6": blob[:4].upper().startswith(b"RPF6"),
        "rsc_block_count": len(candidates),
        "rsc_candidates": [asdict(c) for c in candidates],
        "largest_rsc_candidates": [asdict(c) for c in sorted(candidates, key=lambda c: c.size_to_next_rsc, reverse=True)[:50]],
        "string_hits": [asdict(h) for h in hits],
        "category_counts": dict(Counter(h.category for h in hits)),
        "decompile_status": "no_confirmed_visible_init_script_names" if not any(h.category == "script_filename" and "init" in h.value.lower() for h in hits) else "candidate_init_script_names_found",
    }


def inventory_scripts(roots: Iterable[Path]) -> list[ScriptFile]:
    out: list[ScriptFile] = []
    for root in roots:
        if not root.exists():
            continue
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in files:
            if path.suffix.lower() not in SCRIPT_EXTS:
                continue
            notes: list[str] = []
            status = "candidate_for_decompiler_template"
            if "init" in path.name.lower():
                notes.append("init-named script candidate")
            try:
                size = path.stat().st_size
                digest = sha1_prefix(path)
            except OSError as exc:
                size = 0
                digest = ""
                status = "read_failed"
                notes.append(str(exc))
            out.append(ScriptFile(str(path), path.suffix.lower(), size, digest, status, notes))
    return sorted(out, key=lambda item: ("init" not in Path(item.path).name.lower(), item.extension, item.path.lower()))


def render_command(template: str, decompiler: str, source: Path, output: Path) -> list[str]:
    rendered = template.format(decompiler=decompiler, source=str(source), output=str(output))
    return shlex.split(rendered, posix=(os.name != "nt"))


def run_decompiler(files: list[ScriptFile], out_dir: Path, decompiler: str, template: str, timeout: int) -> list[dict]:
    results = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for item in files:
        source = Path(item.path)
        output = out_dir / f"{source.stem}.decompiled.txt"
        cmd = render_command(template, decompiler, source, output)
        row = {"source": str(source), "output": str(output), "command": cmd}
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            row.update({
                "returncode": proc.returncode,
                "stdout": "\n".join(proc.stdout.splitlines()[:120]),
                "stderr": "\n".join(proc.stderr.splitlines()[:120]),
                "output_exists": output.exists(),
                "ok": proc.returncode == 0 and output.exists(),
            })
        except Exception as exc:
            row.update({"returncode": None, "stdout": "", "stderr": str(exc), "output_exists": False, "ok": False})
        results.append(row)
    return results


def write_report(out_dir: Path, rpf_results: list[dict], scripts: list[ScriptFile], decompile_results: list[dict] | None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rpf_count": len(rpf_results),
        "script_file_count": len(scripts),
        "init_script_file_count": sum(1 for s in scripts if "init" in Path(s.path).name.lower()),
        "decompile_results_count": len(decompile_results or []),
        "decompile_success_count": sum(1 for r in (decompile_results or []) if r.get("ok")),
        "rpf_summaries": [
            {
                "archive": r["archive"],
                "is_rpf6": r["is_rpf6"],
                "rsc_block_count": r["rsc_block_count"],
                "category_counts": r["category_counts"],
                "decompile_status": r["decompile_status"],
            }
            for r in rpf_results
        ],
    }
    (out_dir / "script_decompile_attempt_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "script_decompile_attempt_rpf.json").write_text(json.dumps(rpf_results, indent=2), encoding="utf-8")
    (out_dir / "script_decompile_attempt_scripts.json").write_text(json.dumps([asdict(s) for s in scripts], indent=2), encoding="utf-8")
    if decompile_results is not None:
        (out_dir / "script_decompile_attempt_results.json").write_text(json.dumps(decompile_results, indent=2), encoding="utf-8")

    with (out_dir / "script_decompile_attempt_hits.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["archive", "offset", "kind", "category", "status", "value", "context"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for result in rpf_results:
            for hit in result["string_hits"]:
                writer.writerow({"archive": result["archive"], **hit})

    with (out_dir / "script_decompile_attempt_rsc_candidates.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["archive", "index", "offset", "size_to_next_rsc", "header_hex", "entropy_4k", "ascii_ratio_4k", "status", "notes"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for result in rpf_results:
            for cand in result["largest_rsc_candidates"]:
                row = {"archive": result["archive"], **cand}
                row["notes"] = "; ".join(row["notes"])
                writer.writerow(row)

    lines = [
        "# Code RED Script Decompile Attempt",
        "",
        f"Generated: {summary['generated_at']}",
        f"RPF archives inspected: {summary['rpf_count']}",
        f"Extracted script files found: {summary['script_file_count']}",
        f"Init-named extracted scripts found: {summary['init_script_file_count']}",
        f"Decompiler successes: {summary['decompile_success_count']}/{summary['decompile_results_count']}",
        "",
        "## RPF status",
    ]
    for r in summary["rpf_summaries"]:
        lines.append(f"- `{r['archive']}`: RPF6={r['is_rpf6']} RSC={r['rsc_block_count']} status={r['decompile_status']} categories={r['category_counts']}")
    lines.extend(["", "## Notes"])
    lines.append("- If no visible init .sco/.wsv names are found, the archive table/resource payload still needs a stronger RPF/RSC extractor before source decompile can run.")
    lines.append("- False positives such as `score` containing `sco` are recorded as text hits, not script filenames.")
    lines.append("- Actual decompile execution requires `--decompile`, `--decompiler`, and `--decompiler-template`.")
    (out_dir / "script_decompile_attempt_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED script decompile attempt workflow")
    parser.add_argument("--rpf", action="append", type=Path, default=[], help="RPF archive to inspect. Can be repeated.")
    parser.add_argument("--source", action="append", type=Path, default=[], help="Extracted script/source folder or file. Can be repeated.")
    parser.add_argument("--out", type=Path, default=Path("logs/script_decompile_attempt"))
    parser.add_argument("--decompiler", default="", help="Explicit decompiler path")
    parser.add_argument("--decompiler-template", default="", help="Command template using {decompiler}, {source}, {output}")
    parser.add_argument("--decompile", action="store_true", help="Run decompiler commands; requires template and decompiler")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)

    rpf_results = [scan_rpf(path) for path in args.rpf if path.exists()]
    scripts = inventory_scripts(args.source)
    decompile_results = None
    if args.decompile:
        if not args.decompiler or not args.decompiler_template:
            raise SystemExit("--decompile requires --decompiler and --decompiler-template")
        decompile_results = run_decompiler(scripts, args.out / "decompiled", args.decompiler, args.decompiler_template, args.timeout)
    summary = write_report(args.out, rpf_results, scripts, decompile_results)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
