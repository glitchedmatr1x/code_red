#!/usr/bin/env python3
"""Code RED WSC Direct ID / Population Vehicle Patcher.

Focused, reviewable patching for RDR1 RSC85 type-2 WSC scripts.
- Finds AES key from rdr.exe using CodeX known offsets/hash.
- AES decrypts/encrypts 16 rounds ECB, matching CodeX Rpf6Crypto.
- Zstandard streaming decompress/compress.
- Scans/patches explicit vehicle actor IDs or trainer indexes in chosen binary formats.

This is intentionally NOT a decompiler and does not mutate source files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Tuple, Optional, Any

VEHICLE_NAMES = {
    1177: "Stagecoach",
    1178: "Stagecoach002",
    1179: "Stagecoach003",
    1180: "Stagecoach004",
    1181: "dlc_Vehicle01x",
    1182: "StagecoachGatling01",
    1183: "Cart01",
    1184: "Cart02",
    1185: "Cart003",
    1186: "Cart004",
    1187: "Cart005",
    1188: "Cart006",
    1189: "Canoe01",
    1190: "Raft02",
    1191: "Raft03",
    1192: "Raft01",
    1193: "Truck01",
    1194: "Car01",
    1195: "Wagon04",
    1196: "Wagon05",
    1197: "WagonPrison01",
    1198: "WagonGatling01",
    1199: "Wagon02",
    1200: "Chuckwagon",
    1201: "Chuckwagon02",
    1202: "Coach01",
}
DEFAULT_OLD_WAGON_IDS = [1183,1184,1185,1186,1187,1188,1195,1196,1197,1198,1199,1200,1201,1202]
CODEX_AES_KEY_SHA1 = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
CODEX_AES_KEY_OFFSETS = [0x22A2300, 0x2293500]

FORMATS = {
    "u8": ("B", 1),
    "i8": ("b", 1),
    "u16le": ("<H", 2),
    "u16be": (">H", 2),
    "i16le": ("<h", 2),
    "i16be": (">h", 2),
    "u32le": ("<I", 4),
    "u32be": (">I", 4),
    "i32le": ("<i", 4),
    "i32be": (">i", 4),
}
PREFER_ACTOR_FORMATS = ["u16be", "u16le", "u32le", "u32be", "i16be", "i16le", "i32le", "i32be"]
PREFER_INDEX_FORMATS = ["u8", "u16be", "u16le", "u32le", "u32be", "i16be", "i16le", "i32le", "i32be"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()


def read_file(path: Path) -> bytes:
    return path.read_bytes()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def is_rsc(data: bytes) -> bool:
    return len(data) >= 16 and data[:3] == b"RSC"


def parse_rsc_header(data: bytes) -> Dict[str, Any]:
    if not is_rsc(data):
        return {"is_rsc": False}
    magic = data[:4]
    resource_type = struct.unpack_from("<I", data, 4)[0]
    flag1 = struct.unpack_from("<I", data, 8)[0]
    flag2 = struct.unpack_from("<I", data, 12)[0]
    virtual_pages = flag2 & 0x7FFFFFFF
    physical_pages = flag1 & 0x7FFFFFFF
    # For the RDR1 type-2 WSCs observed in this project, virtual_pages * 4096 gives the decoded size.
    return {
        "is_rsc": True,
        "magic": "RSC" + ("85" if magic[3] == 0x85 else f"{magic[3]:02X}"),
        "resource_type": resource_type,
        "flag1_hex": f"0x{flag1:08X}",
        "flag2_hex": f"0x{flag2:08X}",
        "flag1_signed": struct.unpack("<i", struct.pack("<I", flag1))[0],
        "flag2_signed": struct.unpack("<i", struct.pack("<I", flag2))[0],
        "header_size": 16,
        "payload_size": max(0, len(data) - 16),
        "virtual_size": virtual_pages * 4096,
        "physical_size": physical_pages * 4096,
        "expected_unpacked_size": virtual_pages * 4096 + physical_pages * 4096,
    }


def candidate_rdr_exe_paths(explicit: Optional[str], cwd: Path) -> List[Path]:
    out: List[Path] = []
    if explicit:
        out.append(Path(explicit))
    env = os.environ.get("CODERED_RDR_EXE")
    if env:
        out.append(Path(env))
    out.append(cwd / "rdr.exe")
    out.append(cwd.parent / "rdr.exe")
    # Deduplicate preserving order
    seen = set()
    result = []
    for p in out:
        s = str(p.resolve() if p.exists() else p)
        if s not in seen:
            seen.add(s)
            result.append(p)
    return result


def find_aes_key(explicit_exe: Optional[str] = None) -> Tuple[Optional[bytes], List[Dict[str, Any]]]:
    attempts = []
    cwd = Path.cwd()
    for exe in candidate_rdr_exe_paths(explicit_exe, cwd):
        info = {"exe": str(exe), "exists": exe.exists(), "method": None, "key_sha1": None}
        if not exe.exists():
            attempts.append(info)
            continue
        data = exe.read_bytes()
        for off in CODEX_AES_KEY_OFFSETS:
            if off + 32 <= len(data):
                key = data[off:off+32]
                if sha1(key) == CODEX_AES_KEY_SHA1:
                    info["method"] = f"known_offset_0x{off:X}"
                    info["key_sha1"] = sha1(key).hex().upper()
                    attempts.append(info)
                    return key, attempts
        # Conservative fallback: 4-byte aligned search. May take a moment but only if offsets fail.
        max_len = len(data) - 32
        for off in range(0, max_len + 1, 4):
            key = data[off:off+32]
            if sha1(key) == CODEX_AES_KEY_SHA1:
                info["method"] = f"sha1_scan_0x{off:X}"
                info["key_sha1"] = sha1(key).hex().upper()
                attempts.append(info)
                return key, attempts
        attempts.append(info)
    return None, attempts


def aes_crypt_16_rounds(data: bytes, key: bytes, decrypt: bool) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except Exception as e:
        raise RuntimeError("Missing Python package 'cryptography'. Run install_wsc_direct_id_deps.bat") from e
    buf = bytearray(data)
    length = len(buf) & ~15
    if length <= 0:
        return bytes(buf)
    for _ in range(16):
        cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
        ctx = cipher.decryptor() if decrypt else cipher.encryptor()
        chunk = bytes(buf[:length])
        out = ctx.update(chunk) + ctx.finalize()
        buf[:length] = out
    return bytes(buf)


def zstd_decompress(data: bytes) -> bytes:
    try:
        import zstandard as zstd
    except Exception as e:
        raise RuntimeError("Missing Python package 'zstandard'. Run install_wsc_direct_id_deps.bat") from e
    dctx = zstd.ZstdDecompressor()
    # Use streaming because many RDR1 frames omit content size in the frame header.
    import io
    out = io.BytesIO()
    with dctx.stream_reader(io.BytesIO(data)) as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return out.getvalue()


def zstd_compress(data: bytes, level: int = 22, write_content_size: bool = True) -> bytes:
    try:
        import zstandard as zstd
    except Exception as e:
        raise RuntimeError("Missing Python package 'zstandard'. Run install_wsc_direct_id_deps.bat") from e
    cctx = zstd.ZstdCompressor(level=level, write_content_size=write_content_size)
    return cctx.compress(data)


def zstd_skippable_pad(n: int) -> bytes:
    # Zstandard skippable frame: magic 0x184D2A50 + N, LE size, payload.
    if n <= 0:
        return b""
    if n < 8:
        # Not enough for a valid skippable frame. We avoid raw NUL padding.
        raise ValueError("Need at least 8 bytes for Zstandard skippable padding")
    payload_len = n - 8
    return struct.pack("<II", 0x184D2A50, payload_len) + (b"\x00" * payload_len)


def decode_wsc(path: Path, rdr_exe: Optional[str] = None) -> Tuple[bytes, bytes, Dict[str, Any], List[Dict[str, Any]]]:
    raw = path.read_bytes()
    header = parse_rsc_header(raw)
    if not header.get("is_rsc") or header.get("resource_type") != 2:
        raise RuntimeError("Input is not an RSC85 type-2 WSC/script resource")
    key, attempts = find_aes_key(rdr_exe)
    if key is None:
        raise RuntimeError("Could not find RDR1 AES key from rdr.exe. Set CODERED_RDR_EXE to the real rdr.exe, not PlayRDR.exe")
    payload = raw[16:]
    decrypted = aes_crypt_16_rounds(payload, key, decrypt=True)
    decoded = zstd_decompress(decrypted)
    return raw, decoded, header, attempts


def repack_wsc(raw_original: bytes, decoded: bytes, rdr_exe: Optional[str] = None, allow_variable_size: bool = False, max_growth: int = 0, fit_sweep: bool = True) -> Tuple[bytes, Dict[str, Any]]:
    original_payload_size = len(raw_original) - 16
    key, attempts = find_aes_key(rdr_exe)
    if key is None:
        raise RuntimeError("Could not find RDR1 AES key for repack")
    attempts_report = []
    candidates = []
    levels = list(range(22, 0, -1)) if fit_sweep else [22]
    for level in levels:
        for content_size in (False, True):
            try:
                comp = zstd_compress(decoded, level=level, write_content_size=content_size)
                candidates.append((len(comp), level, content_size, comp))
                attempts_report.append({"codec": f"zstd-level-{level}-{'content-size' if content_size else 'no-content-size'}", "size": len(comp), "delta": len(comp)-original_payload_size})
            except Exception as e:
                attempts_report.append({"codec": f"zstd-level-{level}", "error": repr(e)})
    candidates.sort(key=lambda t: t[0])
    fit = next((c for c in candidates if c[0] <= original_payload_size), None)
    if fit is not None:
        size, level, content_size, comp = fit
        pad = original_payload_size - size
        if pad == 0:
            payload = comp
            fit_mode = "exact"
        else:
            try:
                payload = comp + zstd_skippable_pad(pad)
                fit_mode = "zstd-skippable-padding"
            except ValueError:
                # Pad too tiny. Treat as no exact fit, unless variable output is allowed.
                fit = None
        if fit is not None:
            encrypted = aes_crypt_16_rounds(payload, key, decrypt=False)
            output = raw_original[:16] + encrypted
            # Validate
            decrypted2 = aes_crypt_16_rounds(output[16:], key, decrypt=True)
            decoded2 = zstd_decompress(decrypted2)
            return output, {
                "fit_mode": fit_mode,
                "chosen_codec": f"zstd-level-{level}-{'content-size' if content_size else 'no-content-size'}",
                "original_payload_size": original_payload_size,
                "compressed_size": size,
                "pad": original_payload_size - size,
                "compressed_or_padded_size": len(payload),
                "output_size": len(output),
                "output_sha256": sha256(output),
                "validate_ok": decoded2 == decoded,
                "validate_decoded_size": len(decoded2),
                "validate_error": None,
                "attempts": attempts_report[:60],
            }
    smallest = candidates[0] if candidates else None
    if allow_variable_size and smallest:
        size, level, content_size, comp = smallest
        growth = size - original_payload_size
        if growth <= max_growth:
            encrypted = aes_crypt_16_rounds(comp, key, decrypt=False)
            output = raw_original[:16] + encrypted
            decrypted2 = aes_crypt_16_rounds(output[16:], key, decrypt=True)
            decoded2 = zstd_decompress(decrypted2)
            return output, {
                "fit_mode": "variable-size-rpf-required",
                "warning": "Output WSC size changes; inject with an RPF path that updates entry size/TOC. Do not raw-overwrite fixed-size slots.",
                "chosen_codec": f"zstd-level-{level}-{'content-size' if content_size else 'no-content-size'}",
                "original_payload_size": original_payload_size,
                "compressed_size": size,
                "growth": growth,
                "compressed_or_padded_size": len(comp),
                "output_size": len(output),
                "output_sha256": sha256(output),
                "validate_ok": decoded2 == decoded,
                "validate_decoded_size": len(decoded2),
                "validate_error": None,
                "attempts": attempts_report[:60],
            }
    raise RuntimeError(json.dumps({
        "fit_mode": "blocked-compressed-output-too-large",
        "original_payload_size": original_payload_size,
        "smallest_candidate_size": smallest[0] if smallest else None,
        "smallest_over_by": (smallest[0] - original_payload_size) if smallest else None,
        "attempts": attempts_report[:60],
    }))


def can_pack_value(fmt: str, value: int) -> bool:
    code, _ = FORMATS[fmt]
    try:
        struct.pack(code, value)
        return True
    except Exception:
        return False


def pack_value(fmt: str, value: int) -> bytes:
    return struct.pack(FORMATS[fmt][0], value)


def scan_values(data: bytes, values: Iterable[int], fmt: str, base_id: int = 1177, value_kind: str = "actor") -> List[Dict[str, Any]]:
    vals = [v for v in values if can_pack_value(fmt, v)]
    hits = []
    if not vals:
        return hits
    patterns = [(v, pack_value(fmt, v)) for v in vals]
    for value, pat in patterns:
        start = 0
        while True:
            off = data.find(pat, start)
            if off < 0:
                break
            prev_start = max(0, off - 8)
            next_end = min(len(data), off + len(pat) + 8)
            actor_id = value if value_kind == "actor" else value + base_id
            hits.append({
                "offset": off,
                "offset_hex": f"0x{off:X}",
                "format": fmt,
                "value_kind": value_kind,
                "stored_value": value,
                "actor_id": actor_id,
                "vehicle_name": VEHICLE_NAMES.get(actor_id, ""),
                "bytes_hex": pat.hex(" ").upper(),
                "context_hex": data[prev_start:next_end].hex(" ").upper(),
            })
            start = off + 1
    hits.sort(key=lambda h: (h["offset"], h["format"], h["stored_value"]))
    return hits


def write_csv(path: Path, rows: List[Dict[str, Any]]):
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_json(path: Path, obj: Any):
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def summarize_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[Tuple[str,str,int,int,str], int] = {}
    for h in hits:
        key = (h["value_kind"], h["format"], int(h["stored_value"]), int(h["actor_id"]), h.get("vehicle_name", ""))
        counts[key] = counts.get(key, 0) + 1
    rows = []
    for (kind, fmt, stored, actor, name), count in sorted(counts.items(), key=lambda x: (x[0][0], x[0][1], x[0][3])):
        rows.append({"value_kind": kind, "format": fmt, "stored_value": stored, "actor_id": actor, "vehicle_name": name, "hits": count})
    return rows


def cmd_status(args):
    key, attempts = find_aes_key(args.rdr_exe)
    print(json.dumps({
        "tool": "Code RED WSC Direct ID / Population Patcher",
        "version": "4.0-population",
        "cwd": str(Path.cwd()),
        "aes_key_available": key is not None,
        "aes_key_attempts": attempts,
        "vehicles": VEHICLE_NAMES,
    }, indent=2))
    return 0


def scan_one(path: Path, out_dir: Path, args) -> Dict[str, Any]:
    raw, decoded, header, attempts = decode_wsc(path, args.rdr_exe)
    ensure_dir(out_dir)
    range_low = args.range_low
    range_high = args.range_high
    actor_values = list(range(range_low, range_high + 1))
    index_values = [v - args.base_id for v in actor_values]
    all_hits = []
    actor_hits = []
    index_hits = []
    formats = args.formats or list(FORMATS.keys())
    for fmt in formats:
        # actor ID scan
        ah = scan_values(decoded, actor_values, fmt, args.base_id, "actor")
        actor_hits.extend(ah)
        # index scan; only values that fit current format
        ih = scan_values(decoded, index_values, fmt, args.base_id, "index")
        index_hits.extend(ih)
    all_hits = actor_hits + index_hits
    write_csv(out_dir / f"{path.name}.actor_hits.csv", actor_hits)
    write_csv(out_dir / f"{path.name}.index_hits.csv", index_hits)
    write_csv(out_dir / f"{path.name}.summary.csv", summarize_hits(all_hits))
    (out_dir / f"{path.name}.decoded_payload.bin").write_bytes(decoded)
    summary = {
        "input": str(path),
        "input_size": len(raw),
        "input_sha256": sha256(raw),
        "rsc": header,
        "decode": {"codec": "zstd", "decoded_size": len(decoded), "decoded_sha256": sha256(decoded)},
        "range": [range_low, range_high],
        "base_id": args.base_id,
        "actor_hits": len(actor_hits),
        "index_hits": len(index_hits),
        "summary_csv": str(out_dir / f"{path.name}.summary.csv"),
        "actor_hits_csv": str(out_dir / f"{path.name}.actor_hits.csv"),
        "index_hits_csv": str(out_dir / f"{path.name}.index_hits.csv"),
    }
    write_json(out_dir / f"{path.name}.scan.json", summary)
    return summary


def cmd_population_scan(args):
    inputs = [Path(p) for p in args.input]
    out_root = Path(args.out)
    results = []
    for p in inputs:
        try:
            results.append(scan_one(p, out_root / p.stem, args))
        except Exception as e:
            results.append({"input": str(p), "status": "error", "error": repr(e)})
    print(json.dumps({"out": str(out_root), "files": results}, indent=2))
    return 0 if all(r.get("status") != "error" for r in results) else 1


def choose_auto_plan(decoded: bytes, old_ids: List[int], target_ids: List[int], args) -> Dict[str, Any]:
    candidates = []
    encodings = [args.encoding] if args.encoding != "both" else ["actor", "index"]
    for kind in encodings:
        fmt_list = []
        if args.int_format and args.int_format != "auto":
            fmt_list = [args.int_format]
        else:
            fmt_list = PREFER_ACTOR_FORMATS if kind == "actor" else PREFER_INDEX_FORMATS
        for fmt in fmt_list:
            values = old_ids if kind == "actor" else [v - args.base_id for v in old_ids]
            hits = scan_values(decoded, values, fmt, args.base_id, kind)
            if 0 < len(hits) <= args.max_replacements:
                # Prefer actor IDs over indexes, then lower hit counts, then preferred order.
                priority = 0 if kind == "actor" else 1
                candidates.append({"kind": kind, "format": fmt, "hits": hits, "count": len(hits), "priority": priority})
    if not candidates:
        return {"selected": None, "candidates": []}
    candidates.sort(key=lambda c: (c["priority"], c["count"], (PREFER_ACTOR_FORMATS if c["kind"]=="actor" else PREFER_INDEX_FORMATS).index(c["format"]) if c["format"] in (PREFER_ACTOR_FORMATS if c["kind"]=="actor" else PREFER_INDEX_FORMATS) else 999))
    return {"selected": candidates[0], "candidates": [{"kind": c["kind"], "format": c["format"], "count": c["count"]} for c in candidates]}


def patch_decoded(decoded: bytes, old_ids: List[int], target_ids: List[int], kind: str, fmt: str, base_id: int) -> Tuple[bytes, List[Dict[str, Any]]]:
    data = bytearray(decoded)
    old_values = old_ids if kind == "actor" else [v - base_id for v in old_ids]
    target_values = target_ids if kind == "actor" else [v - base_id for v in target_ids]
    if not target_values:
        raise RuntimeError("No target values")
    replacements = []
    patterns = []
    for old_id, old_val in zip(old_ids, old_values):
        if can_pack_value(fmt, old_val):
            patterns.append((old_id, old_val, pack_value(fmt, old_val)))
    for old_id, old_val, pat in patterns:
        start = 0
        while True:
            off = bytes(data).find(pat, start)
            if off < 0:
                break
            repl_index = len(replacements) % len(target_values)
            target_id = target_ids[repl_index % len(target_ids)]
            target_val = target_values[repl_index % len(target_values)]
            new_pat = pack_value(fmt, target_val)
            data[off:off+len(pat)] = new_pat
            replacements.append({
                "offset": off,
                "offset_hex": f"0x{off:X}",
                "format": fmt,
                "value_kind": kind,
                "old_actor_id": old_id,
                "old_stored_value": old_val,
                "old_name": VEHICLE_NAMES.get(old_id, ""),
                "target_actor_id": target_id,
                "target_stored_value": target_val,
                "target_name": VEHICLE_NAMES.get(target_id, ""),
                "old_bytes_hex": pat.hex(" ").upper(),
                "new_bytes_hex": new_pat.hex(" ").upper(),
            })
            start = off + len(pat)
    return bytes(data), replacements


def cmd_population_patch(args):
    inp = Path(args.input)
    out = Path(args.out)
    ensure_dir(out.parent)
    old_ids = args.old_ids or list(DEFAULT_OLD_WAGON_IDS)
    target_ids = args.target_ids or [args.target_id]
    raw, decoded, header, attempts = decode_wsc(inp, args.rdr_exe)
    plan = choose_auto_plan(decoded, old_ids, target_ids, args) if args.int_format == "auto" or args.encoding == "both" else None
    if plan:
        selected = plan["selected"]
        if selected is None:
            report = {"status": "blocked-no-low-count-candidate", "input": str(inp), "old_ids": old_ids, "target_ids": target_ids, "max_replacements": args.max_replacements, "candidates": plan["candidates"]}
            write_json(out.with_suffix(out.suffix + ".report.json"), report)
            print(json.dumps(report, indent=2))
            return 1
        kind = selected["kind"]
        fmt = selected["format"]
        preview_hits = selected["hits"]
        candidates_report = plan["candidates"]
    else:
        kind = args.encoding if args.encoding != "both" else "actor"
        fmt = args.int_format
        values = old_ids if kind == "actor" else [v - args.base_id for v in old_ids]
        preview_hits = scan_values(decoded, values, fmt, args.base_id, kind)
        candidates_report = [{"kind": kind, "format": fmt, "count": len(preview_hits)}]
    write_csv(out.with_suffix(out.suffix + ".preview_hits.csv"), preview_hits)
    if len(preview_hits) == 0:
        report = {"status": "blocked-no-replacements", "input": str(inp), "kind": kind, "int_format": fmt, "old_ids": old_ids, "target_ids": target_ids, "candidates": candidates_report}
        write_json(out.with_suffix(out.suffix + ".report.json"), report)
        print(json.dumps(report, indent=2))
        return 1
    if len(preview_hits) > args.max_replacements:
        report = {"status": "blocked-too-many-replacements", "input": str(inp), "candidate_replacements": len(preview_hits), "max_replacements": args.max_replacements, "kind": kind, "int_format": fmt, "preview_hits_csv": str(out.with_suffix(out.suffix + ".preview_hits.csv"))}
        write_json(out.with_suffix(out.suffix + ".report.json"), report)
        print(json.dumps(report, indent=2))
        return 1
    if args.preview_only:
        report = {"status": "preview-only", "input": str(inp), "kind": kind, "int_format": fmt, "old_ids": old_ids, "target_ids": target_ids, "candidate_replacements": len(preview_hits), "preview_hits_csv": str(out.with_suffix(out.suffix + ".preview_hits.csv")), "candidates": candidates_report}
        write_json(out.with_suffix(out.suffix + ".report.json"), report)
        print(json.dumps(report, indent=2))
        return 0
    patched_decoded, replacements = patch_decoded(decoded, old_ids, target_ids, kind, fmt, args.base_id)
    write_csv(out.with_suffix(out.suffix + ".replacements.csv"), replacements)
    try:
        output_bytes, fit_report = repack_wsc(raw, patched_decoded, args.rdr_exe, allow_variable_size=args.allow_variable_size, max_growth=args.max_growth, fit_sweep=args.fit_sweep)
    except Exception as e:
        try:
            detail = json.loads(str(e))
        except Exception:
            detail = {"error": repr(e)}
        report = {"status": "blocked-repack-fit-failed", "input": str(inp), "replacements": len(replacements), "kind": kind, "int_format": fmt, "fit_report": detail}
        write_json(out.with_suffix(out.suffix + ".report.json"), report)
        print(json.dumps(report, indent=2))
        return 1
    out.write_bytes(output_bytes)
    report = {
        "status": "patched",
        "input": str(inp),
        "output": str(out),
        "input_size": len(raw),
        "output_size": len(output_bytes),
        "input_sha256": sha256(raw),
        "output_sha256": sha256(output_bytes),
        "rsc": header,
        "decode": {"codec": "zstd", "decoded_size": len(decoded), "decoded_sha256": sha256(decoded)},
        "mode": "population-patch",
        "encoding": kind,
        "int_format": fmt,
        "old_ids": old_ids,
        "target_ids": target_ids,
        "replacements": len(replacements),
        "preview_hits_csv": str(out.with_suffix(out.suffix + ".preview_hits.csv")),
        "replacements_csv": str(out.with_suffix(out.suffix + ".replacements.csv")),
        "fit_report": fit_report,
        "candidates": candidates_report,
    }
    write_json(out.with_suffix(out.suffix + ".report.json"), report)
    print(json.dumps(report, indent=2))
    return 0


def cmd_batch_population_patch(args):
    in_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    files = sorted(in_dir.glob("*.wsc"))
    results = []
    for f in files:
        out = out_dir / (f.stem + f"_population_to_{args.target_id}.wsc")
        subargs = argparse.Namespace(**vars(args))
        subargs.input = str(f)
        subargs.out = str(out)
        try:
            rc = cmd_population_patch(subargs)
            # Read report if exists for compact result
            report_path = out.with_suffix(out.suffix + ".report.json")
            if report_path.exists():
                rep = json.loads(report_path.read_text(encoding="utf-8"))
                results.append({"input": str(f), "status": rep.get("status"), "output": rep.get("output"), "replacements": rep.get("replacements"), "encoding": rep.get("encoding"), "int_format": rep.get("int_format"), "report": str(report_path)})
            else:
                results.append({"input": str(f), "status": "unknown"})
        except Exception as e:
            results.append({"input": str(f), "status": "error", "error": repr(e)})
    summary = {"out_dir": str(out_dir), "files": results}
    write_json(out_dir / "batch_population_patch_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if all(r.get("status") in ("patched", "preview-only", "blocked-no-low-count-candidate", "blocked-no-replacements") for r in results) else 1


def build_parser():
    p = argparse.ArgumentParser(description="Code RED WSC Direct ID / Population Vehicle Patcher")
    p.add_argument("--rdr-exe", default=None, help="Path to real rdr.exe; env CODERED_RDR_EXE is also accepted")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("population-scan", help="Scan one or more WSCs for vehicle actor IDs and trainer indexes across formats")
    s.add_argument("--input", nargs="+", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--range-low", type=int, default=1177)
    s.add_argument("--range-high", type=int, default=1202)
    s.add_argument("--base-id", type=int, default=1177)
    s.add_argument("--formats", nargs="*", choices=list(FORMATS.keys()), default=None)
    s.set_defaults(func=cmd_population_scan)

    s = sub.add_parser("population-patch", help="Patch explicit old vehicle actor IDs, with auto actor/index detection for population scripts")
    s.add_argument("--input", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--old-ids", nargs="*", type=int, default=None, help="Vehicle actor IDs to replace. Defaults to cart/wagon/coach IDs.")
    s.add_argument("--target-id", type=int, default=1194)
    s.add_argument("--target-ids", nargs="*", type=int, default=None, help="Optional alternating targets, e.g. 1193 1194")
    s.add_argument("--encoding", choices=["actor", "index", "both"], default="both")
    s.add_argument("--int-format", choices=["auto"] + list(FORMATS.keys()), default="auto")
    s.add_argument("--base-id", type=int, default=1177)
    s.add_argument("--max-replacements", type=int, default=16)
    s.add_argument("--preview-only", action="store_true")
    s.add_argument("--fit-sweep", action="store_true", default=True)
    s.add_argument("--allow-variable-size", action="store_true")
    s.add_argument("--max-growth", type=int, default=64)
    s.set_defaults(func=cmd_population_patch)

    s = sub.add_parser("batch-population-patch", help="Run population-patch against every .wsc in a directory")
    s.add_argument("--input-dir", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--old-ids", nargs="*", type=int, default=None)
    s.add_argument("--target-id", type=int, default=1194)
    s.add_argument("--target-ids", nargs="*", type=int, default=None)
    s.add_argument("--encoding", choices=["actor", "index", "both"], default="both")
    s.add_argument("--int-format", choices=["auto"] + list(FORMATS.keys()), default="auto")
    s.add_argument("--base-id", type=int, default=1177)
    s.add_argument("--max-replacements", type=int, default=16)
    s.add_argument("--preview-only", action="store_true")
    s.add_argument("--fit-sweep", action="store_true", default=True)
    s.add_argument("--allow-variable-size", action="store_true")
    s.add_argument("--max-growth", type=int, default=64)
    s.set_defaults(func=cmd_batch_population_patch)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(json.dumps({"status": "error", "error": repr(e)}, indent=2))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
