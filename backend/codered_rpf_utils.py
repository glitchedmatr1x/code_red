#!/usr/bin/env python3
"""Code RED RPF utility facade.

Stable, small CLI around the proven RPF6 backend in ``python_workbench.py``.
The source archive is always read-only here.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import zlib
from pathlib import Path

try:
    import zstandard as zstd
except Exception:
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"
_BACKEND = None


def load_backend():
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    spec = importlib.util.spec_from_file_location("codered_workbench_backend", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _BACKEND = module
    return module


def safe_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return str(path)


def parse_archive(archive: Path) -> dict:
    wb = load_backend()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise ValueError(f"Not a readable RPF6 archive: {archive}")
    return info


def find_entry(info: dict, entry_ref: str) -> dict:
    wanted = entry_ref.replace("\\", "/").lower()
    if wanted.isdigit():
        idx = int(wanted)
        for ent in info.get("entries", []):
            if ent.get("index") == idx and ent.get("type") == "file":
                return ent
    for ent in info.get("entries", []):
        if ent.get("type") != "file":
            continue
        candidates = {
            str(ent.get("path") or "").replace("\\", "/").lower(),
            str(ent.get("name") or "").lower(),
        }
        if wanted in candidates:
            return ent
    raise KeyError(entry_ref)


def write_inventory(archive: Path, out_dir: Path) -> dict:
    info = parse_archive(archive)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for ent in info.get("entries", []):
        entries.append({
            "index": ent.get("index"),
            "type": ent.get("type"),
            "path": ent.get("path"),
            "name": ent.get("name"),
            "extension": ent.get("extension"),
            "offset": ent.get("offset", ""),
            "size_in_archive": ent.get("size_in_archive", ""),
            "total_size": ent.get("total_size", ""),
            "is_resource": ent.get("is_resource", ""),
            "is_compressed": ent.get("is_compressed", ""),
            "resource_type": ent.get("resource_type", ""),
        })
    summary = {
        "archive": str(archive),
        "entry_count": info.get("entry_count"),
        "file_count": info.get("file_count"),
        "dir_count": info.get("dir_count"),
        "resolved_count": info.get("resolved_count"),
        "encrypted": info.get("encrypted"),
        "inventory_csv": safe_rel(out_dir / "rpf_inventory.csv"),
        "inventory_json": safe_rel(out_dir / "rpf_inventory.json"),
    }
    (out_dir / "rpf_inventory.json").write_text(json.dumps({"summary": summary, "entries": entries}, indent=2), encoding="utf-8")
    with (out_dir / "rpf_inventory.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(entries[0].keys()) if entries else ["index", "type", "path"])
        writer.writeheader()
        writer.writerows(entries)
    (out_dir / "rpf_inventory.md").write_text(
        "# Code RED RPF Inventory\n\n"
        f"Archive: `{archive}`\n\n"
        f"- Entries: `{summary['entry_count']}`\n"
        f"- Files: `{summary['file_count']}`\n"
        f"- Dirs: `{summary['dir_count']}`\n"
        f"- Resolved names: `{summary['resolved_count']}`\n"
        f"- Encrypted TOC: `{summary['encrypted']}`\n\n"
        "Use `rpf_inventory.csv` for indexing and `rpf_inventory.json` for automation.\n",
        encoding="utf-8",
    )
    return summary


def extract_entries(archive: Path, out_dir: Path, entry_ref: str = "", all_entries: bool = False) -> dict:
    wb = load_backend()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise ValueError(f"Not a readable RPF6 archive: {archive}")
    if all_entries:
        targets = [ent for ent in info.get("entries", []) if ent.get("type") == "file"]
    else:
        targets = [find_entry(info, entry_ref)]
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for ent in targets:
        rel = str(ent.get("path") or ent.get("name") or f"entry_{ent.get('index')}").replace("\\", "/")
        if rel.startswith("root/"):
            rel = rel[5:]
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = extract_entry_payload(wb, archive, ent)
            target.write_bytes(data)
            rows.append({
                "index": ent.get("index"),
                "path": ent.get("path"),
                "output": str(target),
                "size": len(data),
                "ok": True,
                "error": "",
            })
        except Exception as exc:
            rows.append({
                "index": ent.get("index"),
                "path": ent.get("path"),
                "output": str(target),
                "size": 0,
                "ok": False,
                "error": str(exc),
            })
    manifest = {
        "archive": str(archive),
        "out_dir": str(out_dir),
        "requested_entry": entry_ref,
        "all_entries": all_entries,
        "count": len(rows),
        "ok_count": sum(1 for row in rows if row["ok"]),
        "fail_count": sum(1 for row in rows if not row["ok"]),
        "rows": rows,
    }
    (out_dir / "_codered_extract_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def extract_entry_payload(wb, archive: Path, ent: dict) -> bytes:
    try:
        return wb.extract_rpf_entry(archive, ent)
    except Exception:
        if ent.get("is_resource"):
            raise
        with archive.open("rb") as fh:
            fh.seek(int(ent.get("offset") or 0))
            raw = fh.read(int(ent.get("size_in_archive") or 0))
        if ent.get("is_compressed"):
            if raw.startswith(b"\x28\xB5\x2F\xFD") and zstd is not None:
                max_size = int(ent.get("total_size") or 0) or 128 * 1024 * 1024
                return zstd.ZstdDecompressor().decompress(raw, max_output_size=max_size)
            for wbits in (-15, 15, 31):
                try:
                    return zlib.decompress(raw, wbits)
                except Exception:
                    pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED RPF read/extract utility")
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--archive", required=True)
    inv.add_argument("--out", default="logs/rpf_inventory")
    ext = sub.add_parser("extract")
    ext.add_argument("--archive", required=True)
    ext.add_argument("--out", required=True)
    ext.add_argument("--entry", default="")
    ext.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "inventory":
        print(json.dumps(write_inventory(Path(args.archive), Path(args.out)), indent=2))
        return 0
    if args.command == "extract":
        if not args.all and not args.entry:
            parser.error("extract requires --entry or --all")
        print(json.dumps(extract_entries(Path(args.archive), Path(args.out), args.entry, args.all), indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
