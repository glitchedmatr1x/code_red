#!/usr/bin/env python3
"""
Code RED script artifact classifier.

Read-only classifier for .wsc, .sco, .xsc, and nearby script artifacts.
It records size, SHA1, first bytes, printable strings, extension groups, and
same-content hash groups so we do not guess whether a .wsc is interchangeable
with .xsc/.sco.

Usage from repo root:
  py -3 tools/codered_classify_script_artifacts.py --root "C:\\Users\\glitc\\OneDrive\\Desktop\\CodeRED_RPF_Extracts"

Also classify Code RED compile outputs:
  py -3 tools/codered_classify_script_artifacts.py --root script_compiling\\sccl\\output --out logs\\sccl_output_script_artifact_classification
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path

EXTS = {".wsc", ".sco", ".xsc", ".csc", ".ysc"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def hex_head(path: Path, n: int = 64) -> str:
    try:
        return path.read_bytes()[:n].hex(" ").upper()
    except OSError:
        return ""


def ascii_head(path: Path, n: int = 128) -> str:
    try:
        data = path.read_bytes()[:n]
    except OSError:
        return ""
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def strings(path: Path, min_len: int = 4, max_bytes: int = 512_000, limit: int = 30) -> list[str]:
    try:
        data = path.read_bytes()[:max_bytes]
    except OSError:
        return []
    chunks = re.findall(rb"[\x20-\x7E]{%d,}" % min_len, data)
    out = []
    for chunk in chunks:
        s = chunk.decode("ascii", errors="ignore")
        if s.strip():
            out.append(s[:200])
        if len(out) >= limit:
            break
    return out


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if path.suffix.lower() in EXTS:
                yield path


def classify(path: Path, root: Path) -> dict:
    rel = path.relative_to(root).as_posix()
    st = path.stat()
    return {
        "relative_path": rel,
        "suffix": path.suffix.lower(),
        "size": st.st_size,
        "sha1": sha1(path),
        "hex_head_64": hex_head(path),
        "ascii_head_128": ascii_head(path),
        "sample_strings": strings(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Folder to scan")
    parser.add_argument("--out", default="logs/script_artifact_classification", help="Output prefix")
    parser.add_argument("--top", type=int, default=500)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Missing root: {root}")

    rows = []
    for path in iter_files(root):
        try:
            rows.append(classify(path, root))
        except Exception as exc:
            rows.append({
                "relative_path": path.relative_to(root).as_posix(),
                "suffix": path.suffix.lower(),
                "error": str(exc),
            })
    rows.sort(key=lambda r: (r.get("suffix", ""), r.get("relative_path", "")))
    rows = rows[: args.top]

    by_ext: dict[str, list[dict]] = defaultdict(list)
    by_hash: dict[str, list[dict]] = defaultdict(list)
    by_head: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_ext[row.get("suffix", "")].append(row)
        if row.get("sha1"):
            by_hash[row["sha1"]].append(row)
        if row.get("hex_head_64"):
            by_head[row["hex_head_64"]].append(row)

    same_hash_groups = [items for items in by_hash.values() if len(items) > 1]
    same_head_groups = [items for items in by_head.values() if len(items) > 1]

    report = {
        "root": str(root),
        "boundary": "Read-only classification. No files modified.",
        "counts_by_extension": {ext: len(items) for ext, items in sorted(by_ext.items())},
        "same_hash_groups": same_hash_groups,
        "same_head_groups": same_head_groups[:50],
        "rows": rows,
        "interpretation": [
            "Do not rename .xsc or .sco to .wsc unless a copied-archive proof demonstrates that the target slot accepts it.",
            "If .wsc files have different headers/byte shapes from .xsc/.sco, treat WSC as a distinct archive script format or extracted representation.",
            "SC-CL proven targets in this lane are RDR_#SC -> .xsc and RDR_SCO -> .sco.",
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_path = out.with_suffix(".json")
    md_path = out.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Code RED Script Artifact Classification",
        "",
        f"Root: `{root}`",
        "",
        "Boundary: read-only classification. No files modified.",
        "",
        "## Counts by extension",
        "",
    ]
    for ext, items in sorted(by_ext.items()):
        lines.append(f"- `{ext}`: `{len(items)}`")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- SC-CL proven targets in this lane are `RDR_#SC -> .xsc` and `RDR_SCO -> .sco`.",
        "- Do not rename `.xsc` or `.sco` to `.wsc` unless a copied-archive proof demonstrates that the target slot accepts it.",
        "- If `.wsc` files have different headers/byte shapes, treat WSC as a distinct script/container format or extracted representation.",
        "",
    ])
    if same_hash_groups:
        lines.append("## Same SHA1 groups")
        lines.append("")
        for group in same_hash_groups[:20]:
            lines.append("### shared hash")
            for item in group:
                lines.append(f"- `{item.get('relative_path')}` size `{item.get('size')}` suffix `{item.get('suffix')}`")
            lines.append("")
    lines.append("## Files")
    lines.append("")
    for row in rows[:120]:
        lines.append(f"### `{row.get('relative_path')}`")
        if row.get("error"):
            lines.append(f"- error: `{row['error']}`")
            lines.append("")
            continue
        lines.append(f"- suffix: `{row.get('suffix')}`")
        lines.append(f"- size: `{row.get('size')}`")
        lines.append(f"- sha1: `{row.get('sha1')}`")
        lines.append(f"- hex head: `{row.get('hex_head_64')}`")
        lines.append(f"- ascii head: `{row.get('ascii_head_128')}`")
        sample = row.get("sample_strings") or []
        if sample:
            lines.append(f"- strings: `{'; '.join(sample[:4])}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("# Code RED Script Artifact Classification")
    print(f"Root: {root}")
    print(f"JSON: {json_path}")
    print(f"MD: {md_path}")
    print("Counts by extension:")
    for ext, items in sorted(by_ext.items()):
        print(f"  {ext}: {len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
