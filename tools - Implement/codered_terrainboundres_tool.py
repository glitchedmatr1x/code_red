#!/usr/bin/env python3
"""Code RED terrainboundres.rpf viewer/exporter/copied-archive patcher.

This tool is intentionally conservative. It never writes to the source archive.
It can inventory and export terrain-bound WTB resources, decode RSC05/zstd
payloads for research, and apply edited WTB resource files to a copied RPF with
re-read verification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from codered_wsi_explorer import RPF6, aes_blocks, rdr_hash, sha1


WTB_RE = re.compile(r"^(?P<x>[0-9a-fA-F]{4})(?P<y>[0-9a-fA-F]{4})_bnd\.wtb$")
ZSTD_MAGIC = b"\x28\xB5\x2F\xFD"


def signed16(hex_text: str) -> int:
    value = int(hex_text, 16)
    return value - 0x10000 if value & 0x8000 else value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        if fields:
            writer.writeheader()
        writer.writerows(rows)


def zstd_decompress(data: bytes, expected_size: int | None = None) -> bytes:
    try:
        import zstandard as zstd

        dctx = zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data)
        except zstd.ZstdError:
            if expected_size and expected_size > 0:
                try:
                    return dctx.decompress(data, max_output_size=expected_size)
                except zstd.ZstdError:
                    pass
            with dctx.stream_reader(io.BytesIO(data)) as reader:
                return reader.read()
    except Exception as exc:
        if shutil.which("zstd"):
            proc = subprocess.run(
                ["zstd", "-d", "-q", "--single-thread", "--stdout"],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return proc.stdout
        raise RuntimeError("Zstandard decode requires the zstandard Python package or zstd CLI") from exc


def zstd_compress(data: bytes, level: int = 9) -> bytes:
    try:
        import zstandard as zstd

        return zstd.ZstdCompressor(level=level, write_checksum=False).compress(data)
    except Exception as exc:
        if shutil.which("zstd"):
            proc = subprocess.run(
                ["zstd", "-q", "-z", f"-{level}", "--no-check", "--single-thread", "--stdout"],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return proc.stdout
        raise RuntimeError("Zstandard encode requires the zstandard Python package or zstd CLI") from exc


def parse_rsc05(raw: bytes) -> dict[str, Any]:
    if len(raw) < 12 or raw[:4] != b"RSC\x05":
        raise ValueError("Expected RSC05 resource bytes")
    return {
        "magic": raw[:4].decode("latin-1"),
        "resource_type": struct.unpack_from("<I", raw, 4)[0],
        "flag1": struct.unpack_from("<I", raw, 8)[0],
        "header_hex": raw[:12].hex(),
    }


def decode_wtb_resource(raw: bytes, expected_size: int | None = None) -> tuple[dict[str, Any], bytes]:
    header = parse_rsc05(raw)
    payload = zstd_decompress(raw[12:], expected_size=expected_size)
    return header, payload


def maybe_decode_plain_zstd(raw: bytes, expected_size: int | None = None) -> bytes:
    if raw.startswith(ZSTD_MAGIC):
        return zstd_decompress(raw, expected_size=expected_size)
    return raw


def tile_meta(name: str) -> dict[str, Any]:
    match = WTB_RE.match(name)
    if not match:
        return {}
    x_hex = match.group("x").lower()
    y_hex = match.group("y").lower()
    x_u16 = int(x_hex, 16)
    y_u16 = int(y_hex, 16)
    x_s16 = signed16(x_hex)
    y_s16 = signed16(y_hex)
    return {
        "grid_x_hex": x_hex,
        "grid_y_hex": y_hex,
        "grid_x_u16": x_u16,
        "grid_y_u16": y_u16,
        "grid_x_s16": x_s16,
        "grid_y_s16": y_s16,
        "bounds_grid_cell_size_guess": 0x40,
        "world_min_x_guess": x_s16,
        "world_min_y_guess": y_s16,
        "world_max_x_guess": x_s16 + 0x40,
        "world_max_y_guess": y_s16 + 0x40,
    }


def ascii_samples(data: bytes, limit: int = 30) -> tuple[int, list[dict[str, Any]]]:
    samples: list[dict[str, Any]] = []
    count = 0
    for match in re.finditer(rb"[\x20-\x7E]{4,}", data):
        count += 1
        if len(samples) < limit:
            samples.append({"offset": match.start(), "text": match.group(0).decode("latin-1", "replace")})
    return count, samples


def float3_samples(data: bytes, limit: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for off in range(0, max(0, len(data) - 12), 4):
        x, y, z = struct.unpack_from("<3f", data, off)
        if all(-100000.0 <= v <= 100000.0 and v == v for v in (x, y, z)) and max(abs(x), abs(y), abs(z)) >= 1.0:
            rows.append({"offset": off, "x": round(x, 6), "y": round(y, 6), "z": round(z, 6)})
            if len(rows) >= limit:
                break
    return rows


def inspect_payload(data: bytes) -> dict[str, Any]:
    string_count, strings = ascii_samples(data)
    return {
        "decoded_size": len(data),
        "decoded_sha1": sha1(data),
        "ascii_string_count": string_count,
        "ascii_string_samples": strings,
        "float3_samples": float3_samples(data),
        "first_64_hex": data[:64].hex(),
    }


def entry_row(rpf_path: Path, entry: Any) -> dict[str, Any]:
    territory = ""
    parts = entry.path.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[-3].lower() == "terrainboundres":
        territory = parts[-2]
    row = {
        "archive": rpf_path.name,
        "archive_path": str(rpf_path),
        "entry_index": entry.index,
        "entry_path": entry.path,
        "name": entry.name,
        "extension": entry.ext,
        "territory": territory,
        "name_hash": f"0x{entry.name_hash:08X}",
        "base_hash": f"0x{rdr_hash(entry.name.rsplit('.', 1)[0]):08X}" if "." in entry.name else "",
        "offset": entry.offset,
        "stored_size": entry.size,
        "resource": entry.resource,
        "compressed": entry.compressed,
        "resource_type": entry.resource_type if entry.resource_type is not None else "",
        "decoded_total_size": entry.total,
    }
    row.update(tile_meta(entry.name))
    return row


def build_inventory(archive: Path, decode_samples: int = 20) -> dict[str, Any]:
    rpf = RPF6(archive)
    rows = [entry_row(archive, entry) for entry in rpf.files()]
    wtb_rows = [row for row in rows if row["extension"] == ".wtb"]
    txt_rows = [row for row in rows if row["extension"] == ".txt"]
    territories: dict[str, int] = {}
    for row in wtb_rows:
        territory = row.get("territory") or "unknown"
        territories[territory] = territories.get(territory, 0) + 1

    decoded_samples: list[dict[str, Any]] = []
    for entry in rpf.files(".wtb")[: max(0, decode_samples)]:
        raw = rpf.slot(entry)
        sample = entry_row(archive, entry)
        try:
            header, payload = decode_wtb_resource(raw, expected_size=entry.total)
            sample.update(header)
            sample.update(inspect_payload(payload))
            sample["decode_ok"] = True
        except Exception as exc:
            sample["decode_ok"] = False
            sample["decode_error"] = str(exc)
        decoded_samples.append(sample)

    grid_x = [int(row["grid_x_s16"]) for row in wtb_rows if row.get("grid_x_s16") != ""]
    grid_y = [int(row["grid_y_s16"]) for row in wtb_rows if row.get("grid_y_s16") != ""]
    return {
        "archive": rpf.summary(),
        "counts": {
            "entries": len(rpf.entries),
            "files": len(rpf.files()),
            "wtb_tiles": len(wtb_rows),
            "txt_sidecars": len(txt_rows),
            "territories": len(territories),
        },
        "grid_extent_guess": {
            "min_x": min(grid_x) if grid_x else None,
            "max_x": max(grid_x) if grid_x else None,
            "min_y": min(grid_y) if grid_y else None,
            "max_y": max(grid_y) if grid_y else None,
            "cell_size": 0x40,
        },
        "territory_counts": dict(sorted(territories.items())),
        "entries": rows,
        "decoded_samples": decoded_samples,
    }


def render_inventory_md(inventory: dict[str, Any]) -> str:
    counts = inventory["counts"]
    extent = inventory["grid_extent_guess"]
    lines = [
        "# Code RED terrainboundres Inventory",
        "",
        f"Archive: `{inventory['archive']['archive']}`",
        f"Entries: {counts['entries']}  Files: {counts['files']}  WTB tiles: {counts['wtb_tiles']}  TXT sidecars: {counts['txt_sidecars']}",
        f"Grid extent guess: x={extent['min_x']}..{extent['max_x']} y={extent['min_y']}..{extent['max_y']} cell={extent['cell_size']}",
        "",
        "## Territories",
        "",
    ]
    for territory, count in inventory["territory_counts"].items():
        lines.append(f"- `{territory}`: {count} WTB tiles")
    lines.extend(["", "## Decoded Sample Tiles", ""])
    for sample in inventory.get("decoded_samples", [])[:20]:
        state = "ok" if sample.get("decode_ok") else f"failed: {sample.get('decode_error', '')}"
        lines.append(
            f"- `{sample['entry_path']}` index={sample['entry_index']} stored={sample['stored_size']} decoded={sample.get('decoded_size', '')} decode={state}"
        )
    lines.extend(
        [
            "",
            "## Edit Safety",
            "",
            "- Source archives are never modified by this tool.",
            "- Use `export` to create a patchable extracted folder.",
            "- Use `patch-folder` to apply edited `.wtb` resources to a copied archive and verify by re-reading.",
            "- Decoded payload size must stay equal to the original decoded WTB payload unless the RPF resource flag updater is extended for changed resource page totals.",
        ]
    )
    return "\n".join(lines)


def cmd_inventory(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(Path(args.archive), decode_samples=args.decode_samples)
    entries = inventory["entries"]
    wtb_rows = [row for row in entries if row["extension"] == ".wtb"]
    txt_rows = [row for row in entries if row["extension"] == ".txt"]
    (outdir / "terrainboundres_inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    (outdir / "terrainboundres_inventory.md").write_text(render_inventory_md(inventory), encoding="utf-8")
    write_csv(outdir / "terrainboundres_entries.csv", entries)
    write_csv(outdir / "terrainboundres_wtb_tiles.csv", wtb_rows)
    write_csv(outdir / "terrainboundres_txt_sidecars.csv", txt_rows)
    print(f"Wrote terrainboundres inventory to {outdir}")


def cmd_inspect(args: argparse.Namespace) -> None:
    archive = Path(args.archive)
    rpf = RPF6(archive)
    entry = rpf.find(args.path) or next((item for item in rpf.files(".wtb") if item.name.lower() == args.path.lower()), None)
    if not entry:
        raise SystemExit(f"WTB entry not found: {args.path}")
    raw = rpf.slot(entry)
    header, payload = decode_wtb_resource(raw, expected_size=entry.total)
    result = entry_row(archive, entry)
    result.update(header)
    result.update(inspect_payload(payload))
    print(json.dumps(result, indent=2))


def safe_rel_path(internal_path: str, fallback: str) -> Path:
    parts = [part for part in internal_path.replace("\\", "/").split("/") if part not in {"", ".", ".."}]
    if not parts:
        parts = [fallback]
    return Path(*parts)


def cmd_export(args: argparse.Namespace) -> None:
    archive = Path(args.archive)
    rpf = RPF6(archive)
    outdir = Path(args.outdir)
    raw_root = outdir / f"{archive.stem}_contents"
    decoded_root = outdir / f"{archive.stem}_decoded_payloads"
    raw_root.mkdir(parents=True, exist_ok=True)
    if args.decoded_payloads:
        decoded_root.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for entry in rpf.files():
        if args.wtb_only and entry.ext != ".wtb":
            continue
        raw = rpf.slot(entry)
        rel = safe_rel_path(entry.path, entry.name)
        out = raw_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
        row = entry_row(archive, entry)
        row["raw_output"] = str(out)
        row["raw_sha1"] = sha1(raw)
        if args.decoded_payloads:
            try:
                if entry.ext == ".wtb":
                    _, payload = decode_wtb_resource(raw, expected_size=entry.total)
                    decoded_out = decoded_root / rel.with_suffix(rel.suffix + ".payload.bin")
                else:
                    payload = maybe_decode_plain_zstd(raw, expected_size=entry.total)
                    decoded_out = decoded_root / rel
                decoded_out.parent.mkdir(parents=True, exist_ok=True)
                decoded_out.write_bytes(payload)
                row["decoded_output"] = str(decoded_out)
                row["decoded_sha1"] = sha1(payload)
                row["decoded_size"] = len(payload)
            except Exception as exc:
                row["decoded_error"] = str(exc)
        manifest.append(row)
    write_csv(outdir / "terrainboundres_export_manifest.csv", manifest)
    (outdir / "terrainboundres_export_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Exported {len(manifest)} entries to {raw_root}")


def patch_toc_entry(data: bytearray, rpf: RPF6, entry: Any, new_size: int, new_offset: int | None = None) -> None:
    if new_offset is not None and new_offset % 2048:
        raise ValueError("RPF resource relocation offset must be 2048-byte aligned")
    toc = bytearray(rpf.toc)
    off = entry.index * 20
    a, b, c, d, e = struct.unpack(">5I", toc[off : off + 20])
    b = (b & 0xF0000000) | (new_size & 0x0FFFFFFF)
    if new_offset is not None:
        c = ((new_offset // 8) & 0x7FFFFF00) | (entry.resource_type or (c & 0xFF))
    toc[off : off + 20] = struct.pack(">5I", a, b, c, d, e)
    data[16 : 16 + rpf.toc_size] = aes_blocks(bytes(toc), False) if rpf.enc else bytes(toc)


def append_payload(data: bytearray, payload: bytes) -> int:
    offset = (len(data) + 2047) & ~2047
    data.extend(b"\0" * (offset - len(data)))
    data.extend(payload)
    return offset


def find_entry_for_patch(rpf: RPF6, patch_file: Path, patch_root: Path) -> Any | None:
    rel = patch_file.relative_to(patch_root).as_posix().lower()
    normalized = rel[5:] if rel.startswith("root/") else rel
    by_name = []
    for entry in rpf.files(".wtb"):
        path = entry.path.lower()
        path_norm = path[5:] if path.startswith("root/") else path
        if rel == path or normalized == path_norm:
            return entry
        if patch_file.name.lower() == entry.name.lower():
            by_name.append(entry)
    return by_name[0] if len(by_name) == 1 else None


def validate_wtb_replacement(original_entry: Any, original_raw: bytes, replacement_raw: bytes) -> tuple[bool, str, dict[str, Any]]:
    details: dict[str, Any] = {
        "original_raw_sha1": sha1(original_raw),
        "replacement_raw_sha1": sha1(replacement_raw),
        "original_size": len(original_raw),
        "replacement_size": len(replacement_raw),
    }
    try:
        original_header, original_payload = decode_wtb_resource(original_raw, expected_size=original_entry.total)
        replacement_header, replacement_payload = decode_wtb_resource(replacement_raw, expected_size=original_entry.total)
    except Exception as exc:
        return False, f"WTB replacement decode failed: {exc}", details
    details.update(
        {
            "original_decoded_sha1": sha1(original_payload),
            "replacement_decoded_sha1": sha1(replacement_payload),
            "original_decoded_size": len(original_payload),
            "replacement_decoded_size": len(replacement_payload),
            "resource_type": replacement_header.get("resource_type"),
        }
    )
    if replacement_header.get("resource_type") != 36:
        return False, "Replacement is not resource type 36 WTB terrain-bound data.", details
    if len(replacement_payload) != len(original_payload):
        return False, "Decoded WTB payload size changed; blocked until resource page total rewriting is extended.", details
    if len(original_payload) != int(original_entry.total or len(original_payload)):
        details["total_size_warning"] = "Original decoded size does not match RPF total_size field."
    if original_header.get("flag1") != replacement_header.get("flag1"):
        return False, "Replacement RSC flag1 differs from the original; blocked to keep TOC resource totals stable.", details
    return True, "WTB replacement validated.", details


def apply_one_wtb_patch(archive_copy: Path, target_entry: Any, replacement_file: Path) -> dict[str, Any]:
    rpf = RPF6(archive_copy)
    live = rpf.find(target_entry.path)
    if not live:
        return {"status": "blocked", "entry_path": target_entry.path, "patch": str(replacement_file), "reason": "Target entry was not found in archive copy."}
    original_raw = rpf.slot(live)
    replacement_raw = replacement_file.read_bytes()
    if original_raw == replacement_raw:
        return {
            "status": "identical",
            "entry_path": live.path,
            "patch": str(replacement_file),
            "raw_sha1": sha1(original_raw),
        }
    ok, reason, details = validate_wtb_replacement(live, original_raw, replacement_raw)
    row: dict[str, Any] = {"status": "blocked", "entry_path": live.path, "patch": str(replacement_file), "reason": reason}
    row.update(details)
    if not ok:
        return row
    data = bytearray(archive_copy.read_bytes())
    old_offset = live.offset
    old_size = live.size
    relocated = len(replacement_raw) > old_size
    if relocated:
        new_offset = append_payload(data, replacement_raw)
        patch_toc_entry(data, rpf, live, len(replacement_raw), new_offset)
    else:
        data[old_offset : old_offset + len(replacement_raw)] = replacement_raw
        if len(replacement_raw) < old_size:
            data[old_offset + len(replacement_raw) : old_offset + old_size] = b"\0" * (old_size - len(replacement_raw))
        new_offset = old_offset
        patch_toc_entry(data, rpf, live, len(replacement_raw), None)
    archive_copy.write_bytes(data)
    reparsed = RPF6(archive_copy)
    verify_entry = reparsed.find(live.path)
    if not verify_entry:
        row["reason"] = "Patched archive could not resolve the entry after write."
        return row
    verify_raw = reparsed.slot(verify_entry)
    if verify_raw != replacement_raw:
        row["reason"] = "Patched archive re-read did not match replacement bytes."
        row["verify_raw_sha1"] = sha1(verify_raw)
        return row
    _, verify_payload = decode_wtb_resource(verify_raw, expected_size=verify_entry.total)
    row.update(
        {
            "status": "archive_copy_replace_relocated_verified" if relocated else "archive_copy_replace_verified",
            "reason": "Copied archive patched and verified by re-read.",
            "old_offset": old_offset,
            "new_offset": new_offset,
            "old_size": old_size,
            "new_size": len(replacement_raw),
            "relocated": relocated,
            "verify_raw_sha1": sha1(verify_raw),
            "verify_decoded_sha1": sha1(verify_payload),
        }
    )
    return row


def render_patch_report(source: Path, output: Path, patch_root: Path, rows: list[dict[str, Any]], unmatched: list[str]) -> str:
    applied = sum(1 for row in rows if row.get("status") in {"archive_copy_replace_verified", "archive_copy_replace_relocated_verified"})
    identical = sum(1 for row in rows if row.get("status") == "identical")
    blocked = sum(1 for row in rows if row.get("status") not in {"archive_copy_replace_verified", "archive_copy_replace_relocated_verified", "identical"})
    relocated = sum(1 for row in rows if row.get("status") == "archive_copy_replace_relocated_verified")
    lines = [
        "Code RED terrainboundres Patch Report",
        "====================================",
        "",
        f"Source archive: {source}",
        f"Working copy: {output}",
        f"Patch root: {patch_root}",
        f"Patch results: applied={applied} relocated={relocated} identical={identical} blocked={blocked} unmatched={len(unmatched)}",
        "",
    ]
    if unmatched:
        lines.append("Unmatched WTB patch files:")
        lines.extend(f"- {item}" for item in unmatched[:100])
        lines.append("")
    lines.append("Results:")
    for row in rows:
        lines.append(f"- [{row.get('status')}] {Path(row.get('patch', '')).name} -> {row.get('entry_path', '')} | {row.get('reason', '')}")
        if row.get("relocated"):
            lines.append(f"  relocated: old_offset=0x{int(row.get('old_offset') or 0):X} new_offset=0x{int(row.get('new_offset') or 0):X}")
    return "\n".join(lines)


def cmd_patch_folder(args: argparse.Namespace) -> None:
    source = Path(args.archive)
    patch_root = Path(args.patch_root)
    if not patch_root.exists():
        raise SystemExit(f"Patch root not found: {patch_root}")
    output = Path(args.out) if args.out else patch_root / f"{source.stem}__terrainbound_patched_copy{source.suffix}"
    if source.resolve() == output.resolve():
        raise SystemExit("Refusing to patch source archive in place.")
    shutil.copy2(source, output)
    source_rpf = RPF6(source)
    patch_files = sorted(path for path in patch_root.rglob("*.wtb") if path.is_file())
    rows: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for patch_file in patch_files:
        entry = find_entry_for_patch(source_rpf, patch_file, patch_root)
        if not entry:
            unmatched.append(patch_file.relative_to(patch_root).as_posix())
            continue
        rows.append(apply_one_wtb_patch(output, entry, patch_file))
    report = render_patch_report(source, output, patch_root, rows, unmatched)
    report_path = output.with_name(output.stem + "_terrainbound_patch_report.txt")
    json_path = output.with_name(output.stem + "_terrainbound_patch_report.json")
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps({"source": str(source), "output": str(output), "patch_root": str(patch_root), "results": rows, "unmatched": unmatched}, indent=2), encoding="utf-8")
    print(report)
    print(f"Report: {report_path}")
    print(f"JSON: {json_path}")


def cmd_patch_bytes(args: argparse.Namespace) -> None:
    source = Path(args.archive)
    output = Path(args.out)
    if source.resolve() == output.resolve():
        raise SystemExit("Refusing to patch source archive in place.")
    rpf = RPF6(source)
    entry = rpf.find(args.path) or next((item for item in rpf.files(".wtb") if item.name.lower() == args.path.lower()), None)
    if not entry:
        raise SystemExit(f"WTB entry not found: {args.path}")
    raw = rpf.slot(entry)
    header = raw[:12]
    _, payload = decode_wtb_resource(raw, expected_size=entry.total)
    buf = bytearray(payload)
    offset = int(args.offset, 0)
    replacement = bytes.fromhex(args.hex.replace(" ", ""))
    if offset < 0 or offset + len(replacement) > len(buf):
        raise SystemExit("Decoded payload patch range is outside the WTB payload.")
    old = bytes(buf[offset : offset + len(replacement)])
    buf[offset : offset + len(replacement)] = replacement
    rebuilt = header + zstd_compress(bytes(buf), level=args.zstd_level)
    tmp_dir = output.parent / f"{output.stem}_single_wtb_patch_source"
    tmp_file = tmp_dir / safe_rel_path(entry.path, entry.name)
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file.write_bytes(rebuilt)
    shutil.copy2(source, output)
    row = apply_one_wtb_patch(output, entry, tmp_file)
    row.update({"decoded_offset": offset, "old_hex": old.hex(), "new_hex": replacement.hex(), "rebuilt_resource_size": len(rebuilt)})
    report_path = output.with_name(output.stem + "_terrainbound_byte_patch_report.json")
    report_path.write_text(json.dumps(row, indent=2), encoding="utf-8")
    print(json.dumps(row, indent=2))
    print(f"Report: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="View/export/edit copied terrainboundres.rpf WTB contents")
    sub = parser.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("inventory", help="Write terrainboundres inventory reports")
    q.add_argument("archive")
    q.add_argument("--outdir", default="reports/terrainboundres_inventory")
    q.add_argument("--decode-samples", type=int, default=20)
    q.set_defaults(fn=cmd_inventory)

    q = sub.add_parser("inspect", help="Inspect one WTB entry by full internal path or filename")
    q.add_argument("archive")
    q.add_argument("path")
    q.set_defaults(fn=cmd_inspect)

    q = sub.add_parser("export", help="Export patchable raw WTB resources and optional decoded payloads")
    q.add_argument("archive")
    q.add_argument("--outdir", default="exports/terrainboundres_export")
    q.add_argument("--decoded-payloads", action="store_true")
    q.add_argument("--wtb-only", action="store_true")
    q.set_defaults(fn=cmd_export)

    q = sub.add_parser("patch-folder", help="Apply edited WTB files to a copied terrainboundres RPF")
    q.add_argument("archive")
    q.add_argument("patch_root")
    q.add_argument("--out")
    q.set_defaults(fn=cmd_patch_folder)

    q = sub.add_parser("patch-wtb-bytes", help="Patch bytes in a decoded WTB payload and write a copied archive")
    q.add_argument("archive")
    q.add_argument("path")
    q.add_argument("--offset", required=True)
    q.add_argument("--hex", required=True)
    q.add_argument("--out", required=True)
    q.add_argument("--zstd-level", type=int, default=9)
    q.set_defaults(fn=cmd_patch_bytes)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
