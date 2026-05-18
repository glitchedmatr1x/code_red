#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import struct
import sys
import traceback
from pathlib import Path
from typing import Iterable

CAR_ID_DEFAULT = 1194
LAB = "car1194_wagonthief_wsc"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest().upper()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_bytes(path: Path) -> bytes:
    with path.open('rb') as f:
        return f.read()


def write_json(path: Path, obj: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2), encoding='utf-8')


def parse_rsc(data: bytes) -> dict:
    if len(data) < 16:
        return {"is_rsc": False, "error": "file shorter than 16-byte RSC header"}
    magic = data[:4].decode('ascii', errors='replace')
    if magic not in {"RSC5", "RSC7", "RSC8", "RSC\x85", "RSC\x86", "RSC05", "RSC85", "RSC86"}:
        # Normal Python ascii decode of RSC85 bytes is RSC�. Use exact int too.
        pass
    magic_u32 = struct.unpack_from('<I', data, 0)[0]
    magic_name = {
        0x05435352: 'RSC05',
        0x85435352: 'RSC85',
        0x86435352: 'RSC86',
    }.get(magic_u32, magic)
    if magic_name not in {'RSC05', 'RSC85', 'RSC86'}:
        return {"is_rsc": False, "magic_u32": magic_u32, "magic_hex": f"0x{magic_u32:08X}"}
    resource_type = struct.unpack_from('<I', data, 4)[0]
    flag1 = struct.unpack_from('<i', data, 8)[0]
    flag2 = struct.unpack_from('<i', data, 12)[0]
    uflag1 = struct.unpack_from('<I', data, 8)[0]
    uflag2 = struct.unpack_from('<I', data, 12)[0]
    # RSC85 page-size approximation used for status only. It matches our prior reports well enough for warnings.
    virtual_size = 0
    physical_size = 0
    if magic_name == 'RSC85':
        # Known from CodeX FlagInfo: total virtual/physical sizes are encoded in extended flags.
        # We only keep the conservative expected size from prior lab behavior when possible.
        # This is not used for patching.
        vbits = (uflag2 >> 0) & 0xF
        virtual_size = 4096 << vbits if vbits < 20 else 0
    return {
        "is_rsc": True,
        "magic": magic_name,
        "resource_type": resource_type,
        "flag1_signed": flag1,
        "flag2_signed": flag2,
        "flag1_hex": f"0x{uflag1:08X}",
        "flag2_hex": f"0x{uflag2:08X}",
        "header_size": 16,
        "payload_size": max(0, len(data) - 16),
        "resource_type_note": "WSC/script resource" if resource_type == 2 else "not script type 2",
        "direct_edit_warning": "RSC85 type-2 scripts are usually encrypted/compressed; raw integer replacement may find nothing unless a value exists outside that layer." if resource_type == 2 else "",
    }


def scan_u32_values(data: bytes, values: Iterable[int], start_offset: int = 0) -> list[dict]:
    results = []
    for value in values:
        if value < 0 or value > 0xFFFFFFFF:
            continue
        needle_le = struct.pack('<I', value)
        needle_be = struct.pack('>I', value)
        for endian, needle in [('le', needle_le), ('be', needle_be)]:
            off = data.find(needle, start_offset)
            while off != -1:
                results.append({
                    "value": value,
                    "endian": endian,
                    "offset": off,
                    "offset_hex": f"0x{off:X}",
                    "context_hex": data[max(0, off-16):off+20].hex(' ').upper(),
                })
                off = data.find(needle, off + 1)
    return results


def write_u32_hits_csv(path: Path, rows: list[dict]) -> None:
    ensure_dir(path.parent)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['value', 'endian', 'offset', 'offset_hex', 'context_hex'])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def cmd_status(args) -> dict:
    root = Path.cwd()
    return {
        "tool": "Code RED Car1194 WagonThief WSC Kit",
        "version": "1.0",
        "cwd": str(root),
        "target_script": "imports\\beat_crime_wagonthief.wsc",
        "known_car_id": CAR_ID_DEFAULT,
        "mode": "car-only, no truck id guessing",
        "notes": [
            "beat_crime_wagonthief.wsc is the preferred active script target.",
            "This kit cannot invent old wagon IDs; patch-u32 requires --old-id values.",
            "If RSC85 type-2 script decryption is still blocked, direct WSC editing remains blocked.",
        ],
    }


def cmd_analyze(args) -> dict:
    inp = Path(args.input)
    out = Path(args.out)
    data = read_bytes(inp)
    ensure_dir(out)
    rsc = parse_rsc(data)
    scan_values = [CAR_ID_DEFAULT]
    scan_values.extend(args.scan_id or [])
    hits = scan_u32_values(data, scan_values, 0)
    payload_hits = scan_u32_values(data, scan_values, 16 if rsc.get('is_rsc') else 0)
    write_u32_hits_csv(out / f"{inp.name}.u32_hits.csv", hits)
    report = {
        "input": str(inp),
        "size": len(data),
        "sha256": sha256_file(inp),
        "rsc": rsc,
        "known_car_id": CAR_ID_DEFAULT,
        "scan_values": scan_values,
        "raw_u32_hits": len(hits),
        "payload_region_u32_hits": len(payload_hits),
        "u32_hits_csv": str(out / f"{inp.name}.u32_hits.csv"),
        "interpretation": [
            "If 1194 appears, it may already reference the car, or it may be accidental data.",
            "If old wagon IDs do not appear in raw hits, they may be encrypted/compressed or represented as hashes/opcode immediates.",
            "Do not patch without a known old ID or verified payload decode.",
        ],
    }
    write_json(out / f"{inp.name}.analysis.json", report)
    return report


def cmd_plan(args) -> dict:
    inp = Path(args.input)
    out = Path(args.out)
    data = read_bytes(inp)
    rsc = parse_rsc(data)
    ensure_dir(out)
    plan = {
        "target": "beat_crime_wagonthief.wsc",
        "input": str(inp),
        "input_sha256": sha256_file(inp),
        "known_car_id": CAR_ID_DEFAULT,
        "known_car_id_hex_le": struct.pack('<I', CAR_ID_DEFAULT).hex(' ').upper(),
        "rsc": rsc,
        "recommended_first_patch": "patch-u32 only after identifying an old wagon/coach/cart model/template id from a known-good test.",
        "why_this_script": "wagon thief already contains active theft/vehicle behavior; playercar is reference material, not the first patch target.",
        "blocked_until": [
            "old wagon/template id is identified, or",
            "Vehicle Script Lab successfully decrypts/decompresses RSC85 type-2 script payload and exposes real immediates/constant pools",
        ],
        "safe_command_template": ".\\Run_CodeRED_Car1194_WagonThief_WSC.bat patch-u32 --input imports\\beat_crime_wagonthief.wsc --old-id OLD_ID --new-id 1194 --out patches\\beat_crime_wagonthief_car1194.wsc",
    }
    write_json(out / "car1194_wagonthief_patch_plan.json", plan)
    return plan


def cmd_patch_u32(args) -> dict:
    inp = Path(args.input)
    out = Path(args.out)
    data = bytearray(read_bytes(inp))
    old_ids = list(dict.fromkeys(args.old_id))
    new_id = int(args.new_id)
    if new_id < 0 or new_id > 0xFFFFFFFF:
        raise SystemExit("new-id outside u32 range")
    new_bytes = struct.pack('<I', new_id)
    edits = []
    for old in old_ids:
        if old < 0 or old > 0xFFFFFFFF:
            raise SystemExit(f"old-id outside u32 range: {old}")
        old_bytes = struct.pack('<I', old)
        off = bytes(data).find(old_bytes)
        while off != -1:
            before = bytes(data[max(0, off-16):off+20]).hex(' ').upper()
            data[off:off+4] = new_bytes
            after = bytes(data[max(0, off-16):off+20]).hex(' ').upper()
            edits.append({
                "old_id": old,
                "new_id": new_id,
                "offset": off,
                "offset_hex": f"0x{off:X}",
                "before_context_hex": before,
                "after_context_hex": after,
            })
            off = bytes(data).find(old_bytes, off + 4)
    if not edits and not args.allow_noop:
        raise SystemExit("No old-id values were found. No WSC written. Add --allow-noop only if you intentionally want a copied no-op output.")
    ensure_dir(out.parent)
    out.write_bytes(data)
    result = {
        "input": str(inp),
        "output": str(out),
        "source_sha256": sha256_file(inp),
        "output_sha256": sha256_file(out),
        "source_size": inp.stat().st_size,
        "output_size": out.stat().st_size,
        "exact_size_preserved": inp.stat().st_size == out.stat().st_size,
        "old_ids": old_ids,
        "new_id": new_id,
        "edits_applied": len(edits),
        "edits": edits,
        "guardrails": [
            "source WSC was not modified",
            "only exact 4-byte u32 replacements were made",
            "file size was not changed",
            "no script decompile/recompile was claimed",
        ],
    }
    report = out.with_suffix(out.suffix + '.patch_report.json')
    write_json(report, result)
    result["report_path"] = str(report)
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Code RED car-only beat_crime_wagonthief.wsc patch helper for known Car01x id 1194.')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    a = sub.add_parser('analyze')
    a.add_argument('--input', default='imports/beat_crime_wagonthief.wsc')
    a.add_argument('--out', default='logs/car1194_wagonthief_wsc/analyze')
    a.add_argument('--scan-id', nargs='*', type=int)
    pl = sub.add_parser('plan')
    pl.add_argument('--input', default='imports/beat_crime_wagonthief.wsc')
    pl.add_argument('--out', default='logs/car1194_wagonthief_wsc/plan')
    pu = sub.add_parser('patch-u32')
    pu.add_argument('--input', default='imports/beat_crime_wagonthief.wsc')
    pu.add_argument('--old-id', nargs='+', type=int, required=True)
    pu.add_argument('--new-id', type=int, default=CAR_ID_DEFAULT)
    pu.add_argument('--out', default='patches/beat_crime_wagonthief_car1194.wsc')
    pu.add_argument('--allow-noop', action='store_true')
    args = p.parse_args(argv)
    try:
        if args.command == 'status':
            obj = cmd_status(args)
        elif args.command == 'analyze':
            obj = cmd_analyze(args)
        elif args.command == 'plan':
            obj = cmd_plan(args)
        elif args.command == 'patch-u32':
            obj = cmd_patch_u32(args)
        else:
            raise SystemExit(f'unknown command {args.command}')
        print(json.dumps(obj, indent=2))
        return 0
    except Exception as exc:
        log_dir = Path('logs') / LAB
        ensure_dir(log_dir)
        (log_dir / 'crash.log').write_text(traceback.format_exc(), encoding='utf-8')
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        print(f'Crash note: {log_dir / "crash.log"}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
