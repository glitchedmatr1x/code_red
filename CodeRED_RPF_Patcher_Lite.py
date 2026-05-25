#!/usr/bin/env python3
"""
CodeRED RPF Patcher Lite

Portable folder-based RPF patcher for Red Dead Redemption PC.

Mod folder examples:
  MyMod/content/ui/pausemenu/networking.sc.xml
  MyMod/content/release64/scripting/designerdefined/long_update_thread.wsc
  MyMod/tune/...
  MyMod/content.rpf/content/...

Default behavior:
  - builds cloned RPFs first
  - replacement-only by default
  - backs up before --swap-in
  - does not require Magic RDR
  - uses bundled backend/ files created by Make-PortableFromCodeRED.ps1
"""
from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import importlib.util
import json
import shutil
import struct
import sys
from collections import defaultdict
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR / "backend"

RESOURCE_EXTS = {".wsc", ".xsc", ".csc", ".sco", ".wft", ".wfd", ".wtd", ".xtd", ".xtx", ".strtbl"}
CONTENT_IMPLICIT_PREFIXES = {"release", "release64", "ui", "scripting", "multiplayer", "dlc"}

def sha1b(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()

def crc32b(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"

def file_meta(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha1": sha1b(data), "crc32": crc32b(data)}

def load_module(path: Path, name: str):
    if not path.exists():
        raise FileNotFoundError(f"Missing backend file: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load backend module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def backup_file(source: Path, backup_dir: Path) -> Path:
    meta = file_meta(source)
    out = backup_dir / f"{source.stem}_{meta['sha1'][:12]}{source.suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        shutil.copy2(source, out)
    return out

def rpf_map(game_dir: Path) -> dict[str, Path]:
    found = {}
    for path in game_dir.glob("*.rpf"):
        found[path.stem.lower()] = path
        found[path.name.lower()] = path
    return found

def normalize_archive_path(parts: list[str]) -> str:
    clean = [p for p in parts if p not in ("", ".")]
    if not clean:
        raise ValueError("empty internal path")
    if clean[0].lower() == "root":
        return "/".join(clean).replace("\\", "/")
    return ("root/" + "/".join(clean)).replace("\\", "/")

def infer_target(rel: Path, game_dir: Path, rpfmap: dict[str, Path], target_rpf: str | None) -> tuple[Path, str]:
    parts = list(rel.parts)
    low = [p.lower() for p in parts]
    if not parts:
        raise ValueError(f"bad path: {rel}")

    if target_rpf:
        name = target_rpf.lower()
        if not name.endswith(".rpf"):
            name += ".rpf"
        return game_dir / name, normalize_archive_path(parts)

    if low[0].endswith(".rpf"):
        if len(parts) < 2:
            raise ValueError(f"wrapper folder has no internal path: {rel}")
        return game_dir / parts[0], normalize_archive_path(parts[1:])

    first = low[0]
    if first in rpfmap:
        return rpfmap[first], normalize_archive_path(parts)
    if f"{first}.rpf" in rpfmap:
        return rpfmap[f"{first}.rpf"], normalize_archive_path(parts)
    if first in CONTENT_IMPLICIT_PREFIXES:
        return (rpfmap.get("content.rpf") or game_dir / "content.rpf"), normalize_archive_path(["content", *parts])

    raise ValueError(f"Cannot infer RPF from {rel}. Use top folder like content/ or tune/, or wrapper content.rpf/content/...")

def should_skip(path: Path, rel: Path) -> bool:
    parts = [p.lower() for p in rel.parts]
    if not parts:
        return True
    if parts[0] in {"reports", "logs", "original_backups", "__pycache__"}:
        return True
    if path.name.lower() in {"readme.md", "manifest.csv", "manifest.json"}:
        return True
    return False

def archive_path_set(info: dict) -> set[str]:
    return {
        str(e.get("path") or "").replace("\\", "/").lower()
        for e in info.get("entries", [])
        if e.get("type") == "file"
    }

def collect_plan(mod_dir: Path, game_dir: Path, target_rpf: str | None) -> tuple[list[dict], list[dict]]:
    rpfmap = rpf_map(game_dir)
    rows, errors = [], []
    for path in sorted(mod_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(mod_dir)
        if should_skip(path, rel):
            continue
        try:
            rpf, archive_path = infer_target(rel, game_dir, rpfmap, target_rpf)
            data = path.read_bytes()
            rows.append({
                "status": "planned",
                "relative_path": rel.as_posix(),
                "source_path": str(path),
                "target_rpf": str(rpf),
                "archive_path": archive_path,
                "exists": False,
                "ext": path.suffix.lower(),
                "size": len(data),
                "sha1": sha1b(data),
                "crc32": crc32b(data),
                "notes": "",
            })
        except Exception as exc:
            errors.append({"relative_path": rel.as_posix(), "source_path": str(path), "error": str(exc)})
    return rows, errors

def build_one(overlay, utils, source_rpf: Path, output_rpf: Path, items: list[dict], allow_add: bool, allow_add_resource: bool) -> dict:
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source_rpf)
    if info is None:
        raise RuntimeError(f"Not a readable RPF6 archive: {source_rpf}")

    existing_paths = archive_path_set(info)
    root = overlay.build_existing_tree(info)
    ops, skipped = [], []

    for row in items:
        row["exists"] = row["archive_path"].lower() in existing_paths
        if not row["exists"] and not allow_add:
            row["status"] = "skipped_missing"
            row["notes"] = "not present; pass --allow-add to add"
            skipped.append(row.copy())
            continue
        if not row["exists"] and row["ext"] in RESOURCE_EXTS and not allow_add_resource:
            row["status"] = "skipped_missing_resource"
            row["notes"] = "missing resource-like file; add blocked unless --allow-add-resource"
            skipped.append(row.copy())
            continue

        payload = Path(row["source_path"]).read_bytes()
        action, node = overlay.add_or_replace_file(
            wb,
            root,
            row["archive_path"],
            payload,
            "replace" if row["exists"] else "add",
            allow_resource_replace=True,
        )
        row["status"] = action
        ops.append({
            "archive_path": row["archive_path"],
            "action": action,
            "decoded_size": len(payload),
            "decoded_sha1": row["sha1"],
            "stored_size": node.stored_size,
            "compressed": node.force_compressed,
            "resource_replace": getattr(node, "resource_replace", False),
        })

    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    floor = min(int(e["offset"]) for e in info["entries"] if e.get("type") == "file")
    if 16 + toc_size > floor:
        raise RuntimeError(f"TOC would overlap first payload: toc_end={16 + toc_size} payload_floor={floor}")

    output = bytearray(source_rpf.read_bytes())
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = overlay.align(len(output), overlay.payload_alignment(node))
        if node.new_offset > len(output):
            output.extend(b"\x00" * (node.new_offset - len(output)))
        output.extend(node.source_bytes or b"")
        padded = overlay.align(len(output), 8)
        if padded > len(output):
            output.extend(b"\x00" * (padded - len(output)))

    toc = overlay.pack_toc(wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(
        ">4I",
        output,
        0,
        0x52504636,
        len(nodes),
        int(info.get("debug_offset") or 0),
        int(info.get("enc_flag") or 0),
    )
    output[16 : 16 + len(toc)] = toc

    output_rpf.parent.mkdir(parents=True, exist_ok=True)
    output_rpf.write_bytes(output)

    parsed = wb.parse_rpf6(output_rpf)
    if parsed is None:
        raise RuntimeError(f"Output does not parse: {output_rpf}")

    return {
        "source": file_meta(source_rpf),
        "output": file_meta(output_rpf),
        "entry_count_before": info.get("entry_count"),
        "entry_count_after": parsed.get("entry_count"),
        "ops": ops,
        "skipped": skipped,
    }

def verify_readback(utils, output_rpf: Path, items: list[dict]) -> list[dict]:
    wb = utils.load_backend()
    info = utils.parse_archive(output_rpf)
    rows = []
    for row in items:
        if str(row.get("status", "")).startswith("skipped") or row.get("status") == "error":
            continue
        try:
            ent = utils.find_entry(info, row["archive_path"])
            data = utils.extract_entry_payload(wb, output_rpf, ent)
            exact = sha1b(data) == row["sha1"] and crc32b(data) == row["crc32"]
            status = "exact_match" if exact else ("resource_readable_or_transformed" if row["ext"] in RESOURCE_EXTS else "mismatch")
            rows.append({
                "target_rpf": "",
                "output_rpf": str(output_rpf),
                "archive_path": row["archive_path"],
                "status": status,
                "expected_size": row["size"],
                "actual_size": len(data),
                "expected_sha1": row["sha1"],
                "actual_sha1": sha1b(data),
                "notes": "",
            })
        except Exception as exc:
            rows.append({
                "target_rpf": "",
                "output_rpf": str(output_rpf),
                "archive_path": row["archive_path"],
                "status": "error",
                "expected_size": row["size"],
                "actual_size": "",
                "expected_sha1": row["sha1"],
                "actual_sha1": "",
                "notes": str(exc),
            })
    return rows

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Patch RDR PC RPFs from folder-based drop-ins.")
    parser.add_argument("--mod-dir", required=True)
    parser.add_argument("--game-dir", default=r"D:\Games\Red Dead Redemption\game")
    parser.add_argument("--build-root", default="")
    parser.add_argument("--target-rpf", default="")
    parser.add_argument("--allow-add", action="store_true")
    parser.add_argument("--allow-add-resource", action="store_true")
    parser.add_argument("--swap-in", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    mod_dir = Path(args.mod_dir)
    game_dir = Path(args.game_dir)
    build_root = Path(args.build_root) if args.build_root else APP_DIR / "build"
    reports = build_root / "reports"
    outputs = build_root / "built_rpfs"

    overlay = load_module(BACKEND_DIR / "codered_content_convert_overlay_builder.py", "codered_overlay_lite")
    utils = load_module(BACKEND_DIR / "codered_rpf_utils.py", "codered_rpf_utils_lite")

    rows, errors = collect_plan(mod_dir, game_dir, args.target_rpf or None)
    groups = defaultdict(list)
    for row in rows:
        groups[Path(row["target_rpf"])].append(row)

    fields = ["status", "relative_path", "source_path", "target_rpf", "archive_path", "exists", "ext", "size", "sha1", "crc32", "notes"]
    write_csv(reports / "install_plan.csv", rows, fields)
    write_csv(reports / "path_errors.csv", errors, ["relative_path", "source_path", "error"])

    summary = {
        "mod_dir": str(mod_dir),
        "game_dir": str(game_dir),
        "file_count": len(rows),
        "path_error_count": len(errors),
        "target_rpf_count": len(groups),
        "dry_run": args.dry_run,
        "swap_in": args.swap_in,
        "outputs": {},
    }

    if args.dry_run:
        write_json(reports / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 0

    all_verify = []
    for target_rpf, items in groups.items():
        if not target_rpf.exists():
            raise FileNotFoundError(f"Target RPF not found: {target_rpf}")

        source_backup = backup_file(target_rpf, build_root / "original_backups")
        output_rpf = outputs / target_rpf.name
        build_info = build_one(overlay, utils, target_rpf, output_rpf, items, args.allow_add, args.allow_add_resource)
        verify_rows = verify_readback(utils, output_rpf, items)
        for row in verify_rows:
            row["target_rpf"] = str(target_rpf)
        all_verify.extend(verify_rows)

        bad = [r for r in verify_rows if r["status"] in {"mismatch", "error"}]
        write_csv(reports / f"{target_rpf.stem}_ops.csv", build_info["ops"], ["archive_path", "action", "decoded_size", "decoded_sha1", "stored_size", "compressed", "resource_replace"])
        write_csv(reports / f"{target_rpf.stem}_skipped.csv", build_info["skipped"], fields)
        write_csv(reports / f"{target_rpf.stem}_readback_verification.csv", verify_rows, ["target_rpf", "output_rpf", "archive_path", "status", "expected_size", "actual_size", "expected_sha1", "actual_sha1", "notes"])

        if bad:
            raise RuntimeError(f"Readback verification failed for {target_rpf.name}: {len(bad)} bad files. Live RPF was not changed.")

        swapped = False
        live_backup = ""
        if args.swap_in:
            live = backup_file(target_rpf, build_root / "live_swap_backups")
            shutil.copy2(output_rpf, target_rpf)
            if file_meta(target_rpf)["sha1"] != build_info["output"]["sha1"]:
                shutil.copy2(live, target_rpf)
                raise RuntimeError(f"Swap verification failed for {target_rpf}; restored backup.")
            swapped = True
            live_backup = str(live)

        summary["outputs"][target_rpf.name] = {
            "backup": str(source_backup),
            "built_rpf": str(output_rpf),
            "ops_count": len(build_info["ops"]),
            "skipped_count": len(build_info["skipped"]),
            "swapped_in": swapped,
            "live_swap_backup": live_backup,
        }

    write_csv(reports / "all_readback_verification.csv", all_verify, ["target_rpf", "output_rpf", "archive_path", "status", "expected_size", "actual_size", "expected_sha1", "actual_sha1", "notes"])
    write_json(reports / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    print("\nInstalled into live RPFs with backups." if args.swap_in else f"\nBuilt cloned RPFs under:\n{outputs}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
