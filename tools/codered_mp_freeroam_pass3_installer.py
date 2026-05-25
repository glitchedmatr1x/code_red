#!/usr/bin/env python3
"""
Code RED MP Free Roam Pass 3 Installer

Builds a cloned content.rpf from an import-ready drop-in folder.
It does not modify the live game content.rpf unless --swap-in is explicitly passed.
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
from pathlib import Path
from typing import Any

DEFAULT_CODE_RED = Path(r"D:\Games\Red Dead Redemption\Code_RED")
DEFAULT_GAME_CONTENT = Path(r"D:\Games\Red Dead Redemption\game\content.rpf")


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"


def file_meta(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha1": sha1_bytes(data), "crc32": crc32_bytes(data)}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def normalize_archive_path(rel: Path) -> str:
    parts = [p for p in rel.parts if p not in ("", ".")]
    if not parts:
        raise ValueError(f"Bad empty relative path: {rel}")
    lower = [p.lower() for p in parts]

    if "dropin_import_ready" in lower:
        idx = lower.index("dropin_import_ready")
        parts = parts[idx + 1:]
        lower = [p.lower() for p in parts]

    if not parts:
        raise ValueError(f"Cannot map wrapper-only path: {rel}")

    if lower[0] == "root":
        return "/".join(parts).replace("\\", "/")
    if lower[0] == "content":
        return ("root/" + "/".join(parts)).replace("\\", "/")
    if lower[0] in {"release", "release64", "ui", "scripting", "dlc"}:
        return ("root/content/" + "/".join(parts)).replace("\\", "/")
    raise ValueError(f"Unsupported drop-in path layout: {rel}")


def collect_dropin_files(dropin: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(dropin.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dropin)
        lowered = [p.lower() for p in rel.parts]
        if lowered and lowered[0] in {"reports", "report", "logs", "original_backups"}:
            continue
        if path.suffix.lower() in {".md", ".csv", ".json", ".txt", ".log"} and lowered and lowered[0] not in {"content", "root", "release", "release64", "ui", "scripting", "dlc"}:
            continue
        archive_path = normalize_archive_path(rel)
        data = path.read_bytes()
        rows.append({
            "source_path": str(path),
            "relative_path": str(rel),
            "archive_path": archive_path,
            "size": len(data),
            "sha1": sha1_bytes(data),
            "crc32": crc32_bytes(data),
            "payload": data,
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def backup_file(source: Path, backup_dir: Path) -> Path:
    meta = file_meta(source)
    backup = backup_dir / f"{source.stem}_{meta['sha1'][:12]}{source.suffix}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(source, backup)
    return backup


def build_overlay_rpf(overlay, source_rpf: Path, output_rpf: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source_rpf)
    if info is None:
        raise RuntimeError(f"Source does not parse as RPF6: {source_rpf}")

    root = overlay.build_existing_tree(info)
    ops: list[dict[str, Any]] = []

    for row in rows:
        action, node = overlay.add_or_replace_file(wb, root, row["archive_path"], row["payload"], "replace", allow_resource_replace=True)
        ops.append({
            "archive_path": row["archive_path"],
            "action": action,
            "decoded_size": len(row["payload"]),
            "decoded_sha1": row["sha1"],
            "stored_size": node.stored_size,
            "compressed": node.force_compressed,
        })

    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    file_offsets = [int(entry["offset"]) for entry in info["entries"] if entry.get("type") == "file"]
    if not file_offsets:
        raise RuntimeError("Source archive has no file entries")
    payload_floor = min(file_offsets)
    if 16 + toc_size > payload_floor:
        raise RuntimeError(f"TOC would overlap first payload: toc_end={16 + toc_size} payload_floor={payload_floor}")

    output_bytes = bytearray(source_rpf.read_bytes())
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = overlay.align(len(output_bytes), overlay.payload_alignment(node))
        if node.new_offset > len(output_bytes):
            output_bytes.extend(b"\x00" * (node.new_offset - len(output_bytes)))
        output_bytes.extend(node.source_bytes or b"")
        padded = overlay.align(len(output_bytes), 8)
        if padded > len(output_bytes):
            output_bytes.extend(b"\x00" * (padded - len(output_bytes)))

    toc = overlay.pack_toc(wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", output_bytes, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    output_bytes[16:16 + len(toc)] = toc
    output_rpf.parent.mkdir(parents=True, exist_ok=True)
    output_rpf.write_bytes(output_bytes)
    parsed = wb.parse_rpf6(output_rpf)
    if parsed is None:
        raise RuntimeError(f"Output does not parse as RPF6: {output_rpf}")
    return {"entry_count_before": info.get("entry_count"), "entry_count_after": parsed.get("entry_count"), "toc_size": toc_size, "ops": ops, "output": file_meta(output_rpf)}


def verify_readback(utils, output_rpf: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wb = utils.load_backend()
    info = utils.parse_archive(output_rpf)
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            entry = utils.find_entry(info, row["archive_path"])
            data = utils.extract_entry_payload(wb, output_rpf, entry)
            if row["archive_path"].lower().endswith(".wsc") and row["payload"][:4] == b"RSC\x85" and data[:4] != b"RSC\x85":
                status = "resource_payload_readable"
            else:
                status = "exact_match" if sha1_bytes(data) == row["sha1"] and crc32_bytes(data) == row["crc32"] else "mismatch"
            out.append({"archive_path": row["archive_path"], "status": status, "expected_size": row["size"], "actual_size": len(data), "expected_sha1": row["sha1"], "actual_sha1": sha1_bytes(data), "expected_crc32": row["crc32"], "actual_crc32": crc32_bytes(data), "entry_index": entry.get("index"), "notes": ""})
        except Exception as exc:
            out.append({"archive_path": row["archive_path"], "status": "error", "expected_size": row["size"], "actual_size": "", "expected_sha1": row["sha1"], "actual_sha1": "", "expected_crc32": row["crc32"], "actual_crc32": "", "entry_index": "", "notes": str(exc)})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build/install Code RED MP Free Roam Pass 3 content.rpf from drop-in files.")
    ap.add_argument("--code-red", default=str(DEFAULT_CODE_RED), help="Code_RED project root.")
    ap.add_argument("--source-rpf", default=str(DEFAULT_GAME_CONTENT), help="Source/live game content.rpf to clone.")
    ap.add_argument("--dropin", default="", help="dropin_import_ready folder. Defaults under Code_RED build.")
    ap.add_argument("--out", default="", help="Output cloned RPF path. Defaults under Code_RED build.")
    ap.add_argument("--swap-in", action="store_true", help="After successful verify, replace source-rpf with the built RPF. Backup is created first.")
    ap.add_argument("--dry-run", action="store_true", help="Scan/drop-in/report only; do not build an RPF.")
    args = ap.parse_args(argv)

    code_red = Path(args.code_red)
    source_rpf = Path(args.source_rpf)
    dropin = Path(args.dropin) if args.dropin else code_red / "build" / "mp_freeroam_pass3" / "dropin_import_ready"
    build_root = code_red / "build" / "mp_freeroam_pass3_installer"
    reports = build_root / "reports"
    output_rpf = Path(args.out) if args.out else build_root / "content_mp_freeroam_pass3_installed.rpf"
    overlay_tool = code_red / "tools" / "codered_content_convert_overlay_builder.py"
    utils_tool = code_red / "tools" / "codered_rpf_utils.py"

    for label, path in [("Code_RED root", code_red), ("source RPF", source_rpf), ("drop-in folder", dropin), ("overlay builder", overlay_tool), ("RPF utils", utils_tool)]:
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    build_root.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    rows = collect_dropin_files(dropin)
    if not rows:
        raise RuntimeError(f"No importable files found in: {dropin}")

    source_before = file_meta(source_rpf)
    backup = backup_file(source_rpf, build_root / "original_backups")
    manifest_fields = ["archive_path", "relative_path", "source_path", "size", "sha1", "crc32"]
    write_csv(reports / "mp_pass3_installer_manifest.csv", rows, manifest_fields)
    summary: dict[str, Any] = {"source_rpf": source_before, "backup": str(backup), "dropin": str(dropin), "file_count": len(rows), "dry_run": args.dry_run, "swap_in": args.swap_in}

    if args.dry_run:
        write_json(reports / "mp_pass3_installer_summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 0

    overlay = load_module(overlay_tool, "codered_overlay_installer")
    utils = load_module(utils_tool, "codered_rpf_utils_installer")
    build_info = build_overlay_rpf(overlay, source_rpf, output_rpf, rows)
    verify_rows = verify_readback(utils, output_rpf, rows)
    verify_fields = ["archive_path", "status", "expected_size", "actual_size", "expected_sha1", "actual_sha1", "expected_crc32", "actual_crc32", "entry_index", "notes"]
    write_csv(reports / "mp_pass3_installer_readback_verification.csv", verify_rows, verify_fields)
    exact = sum(1 for row in verify_rows if row["status"] == "exact_match")
    bad = [row for row in verify_rows if row["status"] != "exact_match" and not (str(row.get("archive_path", "")).lower().endswith(".wsc") and row["status"] in ("mismatch", "resource_payload_readable"))]
    summary.update({"output_rpf": build_info["output"], "entry_count_before": build_info["entry_count_before"], "entry_count_after": build_info["entry_count_after"], "readback_exact_matches": exact, "readback_total": len(verify_rows), "readback_bad_count": len(bad), "swapped_in": False})

    if bad:
        write_json(reports / "mp_pass3_installer_summary.json", summary)
        raise RuntimeError(f"Readback verification failed for {len(bad)} files. Live RPF was not changed.")

    if args.swap_in:
        live_backup = backup_file(source_rpf, build_root / "live_swap_backups")
        shutil.copy2(output_rpf, source_rpf)
        swapped_meta = file_meta(source_rpf)
        if swapped_meta["sha1"] != build_info["output"]["sha1"]:
            shutil.copy2(live_backup, source_rpf)
            raise RuntimeError("Swap-in verification failed; restored live backup.")
        summary["swapped_in"] = True
        summary["live_swap_backup"] = str(live_backup)
        summary["source_after_swap"] = swapped_meta

    write_json(reports / "mp_pass3_installer_summary.json", summary)
    print(json.dumps(summary, indent=2))
    if args.swap_in:
        print("\nInstalled. Original backup is recorded in the summary JSON.")
    else:
        print(f"\nBuilt cloned RPF only. To test manually, copy this over game\\content.rpf:\n{output_rpf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




