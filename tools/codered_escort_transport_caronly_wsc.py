#!/usr/bin/env python3
"""
Code RED Escort/Transport Car-Only WSC Patcher

Purpose:
  Patch selected escort/transport WSC scripts so wagon/cart/coach vehicle actor IDs
  become Car01 only:
    1194 Car01

Safety:
  - Decodes RSC85 type-2 WSC scripts using the RDR1 AES key from rdr.exe.
  - Patches decoded binary integer operands only; no ASCII substring replacement.
  - Defaults to u16be, which matched the proven WagonThief/Ambush path.
  - Preview and batch summaries are supported.
  - Real patching blocks if replacement count exceeds --max-replacements unless
    --allow-many is provided.
  - Originals are never modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib

AES_KEY_HASH = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
AES_KEY_OFFSETS = [0x22A2300, 0x2293500]
DEFAULT_OLD_LOW = 1177
DEFAULT_OLD_HIGH = 1202
DEFAULT_TARGET_ID = 1194
VEHICLE_NAMES = {
    1177: "Cart00", 1178: "Cart01", 1179: "Cart02", 1180: "Cart003", 1181: "Cart004", 1182: "Cart005",
    1183: "Cart01", 1184: "Cart02", 1185: "Cart003", 1186: "Cart004", 1187: "Cart005", 1188: "Cart006",
    1189: "Wagon01", 1190: "Wagon03", 1191: "WagonSupply01", 1192: "WagonSupply02",
    1193: "Truck01", 1194: "Car01", 1195: "Wagon04", 1196: "Wagon05", 1197: "WagonPrison01",
    1198: "WagonGatling01", 1199: "Wagon02", 1200: "Chuckwagon", 1201: "Chuckwagon02", 1202: "Coach01",
}
INT_FORMATS = {
    "u8": (1, "B"),
    "u16le": (2, "<H"),
    "u16be": (2, ">H"),
    "u32le": (4, "<I"),
    "u32be": (4, ">I"),
    "i16le": (2, "<h"),
    "i16be": (2, ">h"),
    "i32le": (4, "<i"),
    "i32be": (4, ">i"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()


def vehicle_name(v: int) -> str:
    return VEHICLE_NAMES.get(v, str(v))


def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for cur in [p, *p.parents]:
        if (cur / "tools").exists() or (cur / "Code_RED.bat").exists() or (cur / "main.py").exists():
            return cur
    return p


def likely_rdr_exe_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("CODERED_RDR_EXE")
    if env:
        paths.append(Path(env))
    paths.extend([
        root / "rdr.exe",
        root / "RDR.exe",
        root.parent / "rdr.exe",
        root.parent / "RDR.exe",
        Path.cwd() / "rdr.exe",
        Path.cwd() / "RDR.exe",
        Path.cwd().parent / "rdr.exe",
        Path.cwd().parent / "RDR.exe",
    ])
    out: list[Path] = []
    seen = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            out.append(path)
            seen.add(key)
    return out


def search_aes_key_in_exe(exe_path: Path) -> tuple[bytes | None, dict]:
    info = {"exe": str(exe_path), "exists": exe_path.exists(), "method": None, "key_sha1": None}
    if not exe_path.exists():
        return None, info
    data = exe_path.read_bytes()
    for off in AES_KEY_OFFSETS:
        if 0 <= off <= len(data) - 32:
            key = data[off:off + 32]
            if sha1(key) == AES_KEY_HASH:
                info.update({"method": f"known_offset_0x{off:X}", "key_sha1": sha1(key).hex().upper()})
                return key, info
    # conservative fallback; the known offsets usually hit, so keep this limited
    limit = min(len(data) - 32, 1048576)
    for off in range(0, max(0, limit) + 1, 4):
        key = data[off:off + 32]
        if sha1(key) == AES_KEY_HASH:
            info.update({"method": f"fallback_scan_0x{off:X}", "key_sha1": sha1(key).hex().upper()})
            return key, info
    info["method"] = "not_found"
    return None, info


def get_aes_key(root: Path, explicit_exe: str | None = None) -> tuple[bytes | None, list[dict]]:
    attempts: list[dict] = []
    paths = [Path(explicit_exe)] if explicit_exe else likely_rdr_exe_paths(root)
    for path in paths:
        key, info = search_aes_key_in_exe(path)
        attempts.append(info)
        if key is not None:
            return key, attempts
    return None, attempts


def aes_crypt_block(data: bytes, key: bytes, decrypt: bool) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except Exception as exc:
        raise RuntimeError("Python package 'cryptography' is required. Run the included install .bat.") from exc
    length = len(data) & -16
    prefix = data[:length]
    suffix = data[length:]
    if not prefix:
        return data
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    out = prefix
    for _ in range(16):
        ctx = cipher.decryptor() if decrypt else cipher.encryptor()
        out = ctx.update(out) + ctx.finalize()
    return out + suffix


def parse_rsc_header(data: bytes) -> dict:
    if len(data) < 16:
        return {"is_rsc": False, "reason": "too_small"}
    magic = data[:4]
    if magic not in (b"RSC\x05", b"RSC\x85", b"RSC\x86"):
        return {"is_rsc": False, "magic_hex": magic.hex().upper()}
    resource_type = struct.unpack_from("<I", data, 4)[0]
    f1u = struct.unpack_from("<I", data, 8)[0]
    f2u = struct.unpack_from("<I", data, 12)[0]
    return {
        "is_rsc": True,
        "magic": "RSC" + f"{magic[3]:02X}",
        "resource_type": resource_type,
        "flag1_signed": struct.unpack_from("<i", data, 8)[0],
        "flag2_signed": struct.unpack_from("<i", data, 12)[0],
        "flag1_hex": f"0x{f1u:08X}",
        "flag2_hex": f"0x{f2u:08X}",
        "header_size": 16,
        "payload_size": len(data) - 16,
        "virtual_size": (f2u & 0x7FF) * 4096,
        "physical_size": (f1u & 0x7FF) * 4096,
        "expected_unpacked_size": ((f2u & 0x7FF) + (f1u & 0x7FF)) * 4096,
    }


def _zstd_cli() -> str | None:
    return shutil.which("zstd") or shutil.which("zstd.exe")


def zstd_decompress(data: bytes, expected_size: int | None = None) -> bytes:
    try:
        import zstandard as zstd  # type: ignore
        dctx = zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data, max_output_size=expected_size or 0)
        except Exception:
            with dctx.stream_reader(data) as reader:
                return reader.read()
    except Exception as py_exc:
        exe = _zstd_cli()
        if exe:
            with tempfile.TemporaryDirectory(prefix="codered_zstd_") as td:
                inp = Path(td) / "in.zst"
                outp = Path(td) / "out.bin"
                inp.write_bytes(data)
                proc = subprocess.run([exe, "-d", "-f", "-q", str(inp), "-o", str(outp)], capture_output=True, text=True)
                if proc.returncode == 0 and outp.exists():
                    return outp.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd.exe decompression failed")
        raise RuntimeError("zstandard support unavailable or failed: " + str(py_exc))


def zstd_compress(data: bytes, level: int = 22, write_content_size: bool = True) -> bytes:
    try:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdCompressor(level=level, write_content_size=write_content_size).compress(data)
    except TypeError:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdCompressor(level=level).compress(data)
    except Exception as py_exc:
        exe = _zstd_cli()
        if exe:
            with tempfile.TemporaryDirectory(prefix="codered_zstd_") as td:
                inp = Path(td) / "in.bin"
                outp = Path(td) / "out.zst"
                inp.write_bytes(data)
                proc = subprocess.run([exe, "-f", "-q", f"-{level}", str(inp), "-o", str(outp)], capture_output=True, text=True)
                if proc.returncode == 0 and outp.exists():
                    return outp.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd.exe compression failed")
        raise RuntimeError("zstandard support unavailable or failed: " + str(py_exc))


def _zstd_skippable_padding(size: int) -> bytes:
    if size == 0:
        return b""
    if size < 8:
        raise ValueError("zstd skippable padding needs at least 8 bytes")
    return struct.pack("<II", 0x184D2A50, size - 8) + (b"\x00" * (size - 8))


def try_decompress(blob: bytes, expected_size: int | None = None) -> tuple[bytes | None, str, str | None]:
    errors: list[str] = []
    try:
        out = zstd_decompress(blob, expected_size)
        return out, "zstd", None
    except Exception as exc:
        errors.append("zstd: " + str(exc))
    for name, fn in [("zlib", lambda b: zlib.decompress(b)), ("raw-deflate", lambda b: zlib.decompress(b, -15))]:
        try:
            return fn(blob), name, None
        except Exception as exc:
            errors.append(name + ": " + str(exc))
    return None, "unknown", " | ".join(errors)


def compress_candidates(payload: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for level in [22, 21, 20, 19, 18, 15, 12, 9, 6, 3, 1]:
        try:
            out.append((f"zstd-level-{level}", zstd_compress(payload, level, True)))
            out.append((f"zstd-level-{level}-no-content-size", zstd_compress(payload, level, False)))
        except Exception as exc:
            out.append((f"zstd-unavailable-{level}:{exc}", b""))
            break
    for level in range(9, -1, -1):
        out.append((f"zlib-level-{level}", zlib.compress(payload, level)))
    for level in range(9, -1, -1):
        co = zlib.compressobj(level, zlib.DEFLATED, -15)
        out.append((f"raw-deflate-level-{level}", co.compress(payload) + co.flush()))
    return [(n, b) for n, b in out if b]


def fit_compressed_payload(candidates: list[tuple[str, bytes]], target_size: int, allow_grow: bool = False) -> tuple[str, bytes, dict] | None:
    attempts = []
    for cname, comp in candidates:
        if len(comp) > target_size:
            attempts.append({"codec": cname, "size": len(comp), "fit": "too-large"})
            continue
        pad = target_size - len(comp)
        if pad == 0:
            attempts.append({"codec": cname, "size": len(comp), "fit": "exact"})
            return cname, comp, {"fit_mode": "exact", "codec": cname, "pad": 0, "attempts": attempts}
        if cname.startswith("zstd") and pad >= 8:
            final = comp + _zstd_skippable_padding(pad)
            attempts.append({"codec": cname, "size": len(comp), "pad": pad, "fit": "zstd-skippable"})
            return cname, final, {"fit_mode": "zstd-skippable-padding", "codec": cname, "pad": pad, "attempts": attempts}
        attempts.append({"codec": cname, "size": len(comp), "pad": pad, "fit": "candidate-pad-not-used"})
    if allow_grow and candidates:
        cname, comp = min(candidates, key=lambda x: len(x[1]))
        attempts.append({"codec": cname, "size": len(comp), "fit": "allow-grow-variable-size", "over_by": len(comp) - target_size})
        return cname, comp, {
            "fit_mode": "allow-grow-variable-size",
            "codec": cname,
            "pad": 0,
            "original_payload_size": target_size,
            "grown_payload_size": len(comp),
            "over_by": len(comp) - target_size,
            "attempts": attempts,
            "warning": "Use only with an RPF importer that updates replacement file sizes.",
        }
    return None


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def int_hits(data: bytes, values: set[int], formats: list[str]) -> list[dict]:
    hits: list[dict] = []
    for fmt_name in formats:
        width, fmt = INT_FORMATS[fmt_name]
        if len(data) < width:
            continue
        for off in range(0, len(data) - width + 1):
            try:
                v = int(struct.unpack_from(fmt, data, off)[0])
            except struct.error:
                continue
            if v in values:
                hits.append({
                    "offset": off,
                    "hex_offset": f"0x{off:X}",
                    "value": v,
                    "value_name": vehicle_name(v),
                    "format": fmt_name,
                    "width": width,
                    "aligned2": off % 2 == 0,
                    "aligned4": off % 4 == 0,
                    "context_hex": data[max(0, off - 16):min(len(data), off + width + 16)].hex(" ").upper(),
                })
    return hits


def summarize_by_format(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get("format", "unknown"))
        out[k] = out.get(k, 0) + 1
    return out


def count_by_value(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        v = str(r.get("value", ""))
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 999999))


def decode_resource(path: Path, root: Path, rdr_exe: str | None) -> tuple[bytes | None, dict, bytes | None]:
    data = path.read_bytes()
    rsc = parse_rsc_header(data)
    report: dict = {
        "input": str(path),
        "input_size": len(data),
        "input_sha256": sha256(data),
        "rsc": rsc,
    }
    if not rsc.get("is_rsc") or rsc.get("resource_type") != 2:
        report["status"] = "blocked-not-rsc-type2"
        return None, report, None
    key, attempts = get_aes_key(root, rdr_exe)
    report["aes_key_attempts"] = attempts
    if key is None:
        report["status"] = "blocked-no-aes-key"
        return None, report, None
    encrypted_payload = data[16:]
    decrypted_compressed = aes_crypt_block(encrypted_payload, key, decrypt=True)
    decoded, codec, err = try_decompress(decrypted_compressed, rsc.get("expected_unpacked_size") or None)
    report["decode"] = {
        "encrypted_payload_size": len(encrypted_payload),
        "decrypted_payload_sha256": sha256(decrypted_compressed),
        "codec": codec,
        "decompress_error": err,
        "decoded_size": len(decoded) if decoded is not None else 0,
    }
    if decoded is None:
        report["status"] = "blocked-decompress-failed"
        return None, report, key
    report["status"] = "decoded"
    report["decoded_sha256"] = sha256(decoded)
    return decoded, report, key


def scan_one(path: Path, root: Path, args: argparse.Namespace) -> tuple[dict, list[dict]]:
    decoded, report, _key = decode_resource(path, root, getattr(args, "rdr_exe", None))
    values = set(range(args.old_low, args.old_high + 1))
    formats = [args.int_format] if args.int_format != "auto" else ["u16be", "u16le", "u32le", "u32be", "i16le", "i32le", "u8"]
    if decoded is None:
        return report, []
    hits = int_hits(decoded, values, formats)
    report.update({
        "scan_range": [args.old_low, args.old_high],
        "target_id": args.target_id,
        "target_name": vehicle_name(args.target_id),
        "int_formats": formats,
        "vehicle_hits": len(hits),
        "vehicle_hits_by_format": summarize_by_format(hits),
        "vehicle_hits_by_value": count_by_value(hits),
    })
    return report, hits


def patch_payload_caronly(payload: bytes, old_low: int, old_high: int, target_id: int, int_format: str, patch_existing_target: bool) -> tuple[bytes, list[dict]]:
    width, fmt = INT_FORMATS[int_format]
    target_bytes = struct.pack(fmt, target_id)
    old_values = set(range(old_low, old_high + 1))
    buf = bytearray(payload)
    replacements: list[dict] = []
    for off in range(0, len(payload) - width + 1):
        try:
            old = int(struct.unpack_from(fmt, payload, off)[0])
        except struct.error:
            continue
        if old not in old_values:
            continue
        if old == target_id and not patch_existing_target:
            continue
        if bytes(buf[off:off + width]) != struct.pack(fmt, old):
            continue
        buf[off:off + width] = target_bytes
        replacements.append({
            "offset": off,
            "hex_offset": f"0x{off:X}",
            "format": int_format,
            "width": width,
            "old": old,
            "old_name": vehicle_name(old),
            "new": target_id,
            "new_name": vehicle_name(target_id),
            "aligned2": off % 2 == 0,
            "aligned4": off % 4 == 0,
            "safety": "exact decoded binary integer only; no ASCII substring replacement",
        })
    return bytes(buf), replacements


def patch_one(in_path: Path, out_path: Path, root: Path, args: argparse.Namespace) -> dict:
    data = in_path.read_bytes()
    decoded, report, key = decode_resource(in_path, root, getattr(args, "rdr_exe", None))
    report.update({
        "mode": "escort-transport-car-only",
        "old_range": [args.old_low, args.old_high],
        "target_id": args.target_id,
        "target_name": vehicle_name(args.target_id),
        "int_format": args.int_format,
        "max_replacements": args.max_replacements,
    })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if decoded is None or key is None:
        report.setdefault("status", "blocked-decode-failed")
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    if args.int_format == "auto":
        # Use the safest proven path first. Auto chooses the first format with hits.
        chosen = None
        for fmt in ["u16be", "u16le", "u32le", "u32be", "i16le", "i32le", "u8"]:
            values = set(range(args.old_low, args.old_high + 1))
            hits = int_hits(decoded, values, [fmt])
            hits = [h for h in hits if h["value"] != args.target_id or args.patch_existing_target]
            if hits:
                chosen = fmt
                break
        if chosen is None:
            chosen = "u16be"
    else:
        chosen = args.int_format
    patched, replacements = patch_payload_caronly(decoded, args.old_low, args.old_high, args.target_id, chosen, args.patch_existing_target)
    before_hits = int_hits(decoded, set(range(args.old_low, args.old_high + 1)), [chosen])
    after_hits = int_hits(patched, set(range(args.old_low, args.old_high + 1)), [chosen])
    after_undesired = [h for h in after_hits if int(h["value"]) != args.target_id]
    report["patch"] = {
        "chosen_format": chosen,
        "before_hits": len(before_hits),
        "before_hits_by_value": count_by_value(before_hits),
        "replacements": len(replacements),
        "after_hits": len(after_hits),
        "after_hits_by_value": count_by_value(after_hits),
        "after_undesired_hits": len(after_undesired),
        "after_undesired_by_value": count_by_value(after_undesired),
    }
    write_csv(out_path.with_suffix(out_path.suffix + ".before_hits.csv"), before_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".replacements.csv"), replacements)
    if not replacements and not args.allow_noop:
        report["status"] = "blocked-no-replacements"
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    if len(replacements) > args.max_replacements and not args.allow_many:
        report["status"] = "blocked-too-many-replacements"
        report["reason"] = f"{len(replacements)} replacements exceeds max {args.max_replacements}; rerun with --allow-many only after reviewing CSV."
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    if args.preview_only:
        report["status"] = "preview-only"
        report["preview_note"] = "No WSC written. Review .replacements.csv, then rerun without --preview-only."
        (out_path.with_suffix(out_path.suffix + ".decoded_payload_before.bin")).write_bytes(decoded)
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    rsc = report["rsc"]
    header = data[:16]
    original_payload_size = len(data[16:])
    fit = fit_compressed_payload(compress_candidates(patched), original_payload_size, allow_grow=args.allow_grow)
    if fit is None:
        report["status"] = "blocked-repack-fit-failed"
        report["reason"] = "Recompressed payload did not fit original WSC. Try --allow-grow only if your RPF importer updates file sizes."
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    cname, packed, fit_report = fit
    encrypted_new = aes_crypt_block(packed, key, decrypt=False)
    output = header + encrypted_new
    check_dec = aes_crypt_block(output[16:], key, decrypt=True)
    check_payload, check_codec, check_err = try_decompress(check_dec, rsc.get("expected_unpacked_size") or None)
    report["repack"] = {
        "compress_codec": cname,
        "fit_report": fit_report,
        "compressed_or_padded_size": len(packed),
        "padded_encrypted_payload_size": len(encrypted_new),
        "output_size": len(output),
        "output_sha256": sha256(output),
        "validate_codec": check_codec,
        "validate_error": check_err,
        "validate_decoded_size": len(check_payload) if check_payload is not None else 0,
        "validate_ok": check_payload == patched,
    }
    out_path.write_bytes(output)
    write_csv(out_path.with_suffix(out_path.suffix + ".after_hits.csv"), after_hits)
    (out_path.with_suffix(out_path.suffix + ".decoded_payload_before.bin")).write_bytes(decoded)
    (out_path.with_suffix(out_path.suffix + ".decoded_payload_after.bin")).write_bytes(patched)
    report["status"] = "patched" if report["repack"]["validate_ok"] else "patched-validation-warning"
    report["output"] = str(out_path)
    (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def selected_wsc_files(input_dir: Path, terms: list[str], explicit_files: list[str] | None = None) -> list[Path]:
    if explicit_files:
        return [Path(p) for p in explicit_files]
    terms_lower = [t.lower() for t in terms]
    paths: list[Path] = []
    for p in sorted(input_dir.glob("*.wsc")):
        name = p.name.lower()
        if any(t in name for t in terms_lower):
            paths.append(p)
    return paths


def cmd_status(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    key, attempts = get_aes_key(root, args.rdr_exe)
    out = {
        "tool": "Code RED Escort/Transport Car-Only WSC Patcher",
        "version": "1.0",
        "cwd": str(Path.cwd()),
        "repo_root_guess": str(root),
        "default_target": "1194 Car01 only",
        "default_scan_terms": ["escort", "transport"],
        "default_range": [DEFAULT_OLD_LOW, DEFAULT_OLD_HIGH],
        "default_int_format": "u16be",
        "aes_key_available": key is not None,
        "aes_key_attempts": attempts,
        "notes": [
            "Use preview-only first.",
            "This patches exact decoded binary vehicle IDs only; it does not patch ASCII digit chains.",
            "Real patching blocks if replacement count exceeds --max-replacements unless --allow-many is used.",
        ],
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    path = Path(args.input)
    report, hits = scan_one(path, root, args)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / (path.name + ".vehicle_hits.csv"), hits)
    (out_dir / (path.name + ".scan.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "decoded" else 2


def cmd_patch(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    report = patch_one(Path(args.input), Path(args.out), root, args)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in {"preview-only", "patched"} else 2


def cmd_batch_scan(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    files = selected_wsc_files(Path(args.input_dir), args.terms, args.files)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict] = []
    for p in files:
        report, hits = scan_one(p, root, args)
        write_csv(out_dir / (p.name + ".vehicle_hits.csv"), hits)
        summaries.append({
            "input": str(p),
            "status": report.get("status"),
            "vehicle_hits": report.get("vehicle_hits", 0),
            "vehicle_hits_by_value": json.dumps(report.get("vehicle_hits_by_value", {}), sort_keys=True),
            "scan_json": str(out_dir / (p.name + ".scan.json")),
        })
        (out_dir / (p.name + ".scan.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = {
        "status": "complete",
        "input_dir": str(Path(args.input_dir)),
        "terms": args.terms,
        "files_considered": len(files),
        "out_dir": str(out_dir),
        "summaries": summaries,
    }
    write_csv(out_dir / "batch_scan_summary.csv", summaries)
    (out_dir / "batch_scan_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def cmd_batch_patch(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    files = selected_wsc_files(Path(args.input_dir), args.terms, args.files)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict] = []
    for p in files:
        out_path = out_dir / p.name
        report = patch_one(p, out_path, root, args)
        summaries.append({
            "input": str(p),
            "status": report.get("status"),
            "replacements": report.get("patch", {}).get("replacements", 0),
            "chosen_format": report.get("patch", {}).get("chosen_format", args.int_format),
            "output": report.get("output", str(out_path) if report.get("status") == "patched" else ""),
            "report_json": str(out_path.with_suffix(out_path.suffix + ".report.json")),
        })
    summary = {
        "status": "complete",
        "input_dir": str(Path(args.input_dir)),
        "out_dir": str(out_dir),
        "terms": args.terms,
        "preview_only": args.preview_only,
        "files_considered": len(files),
        "summaries": summaries,
    }
    write_csv(out_dir / "batch_patch_summary.csv", summaries)
    (out_dir / "batch_patch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def add_common_patch_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--old-low", type=int, default=DEFAULT_OLD_LOW)
    p.add_argument("--old-high", type=int, default=DEFAULT_OLD_HIGH)
    p.add_argument("--target-id", type=int, default=DEFAULT_TARGET_ID)
    p.add_argument("--int-format", choices=["auto", *INT_FORMATS.keys()], default="u16be")
    p.add_argument("--max-replacements", type=int, default=48)
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--allow-noop", action="store_true")
    p.add_argument("--allow-grow", action="store_true")
    p.add_argument("--allow-many", action="store_true")
    p.add_argument("--patch-existing-target", action="store_true")
    p.add_argument("--rdr-exe")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Patch escort/transport WSC vehicle IDs to Car01 only.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status")
    p.add_argument("--rdr-exe")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("scan")
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="logs/escort_transport_caronly_wsc/scan")
    p.add_argument("--old-low", type=int, default=DEFAULT_OLD_LOW)
    p.add_argument("--old-high", type=int, default=DEFAULT_OLD_HIGH)
    p.add_argument("--target-id", type=int, default=DEFAULT_TARGET_ID)
    p.add_argument("--int-format", choices=["auto", *INT_FORMATS.keys()], default="u16be")
    p.add_argument("--rdr-exe")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("patch")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    add_common_patch_args(p)
    p.set_defaults(func=cmd_patch)

    p = sub.add_parser("batch-scan")
    p.add_argument("--input-dir", default="imports")
    p.add_argument("--out-dir", default="logs/escort_transport_caronly_wsc/batch_scan")
    p.add_argument("--terms", nargs="+", default=["escort", "transport"])
    p.add_argument("--files", nargs="*")
    p.add_argument("--old-low", type=int, default=DEFAULT_OLD_LOW)
    p.add_argument("--old-high", type=int, default=DEFAULT_OLD_HIGH)
    p.add_argument("--target-id", type=int, default=DEFAULT_TARGET_ID)
    p.add_argument("--int-format", choices=["auto", *INT_FORMATS.keys()], default="u16be")
    p.add_argument("--rdr-exe")
    p.set_defaults(func=cmd_batch_scan)

    p = sub.add_parser("batch-patch")
    p.add_argument("--input-dir", default="imports")
    p.add_argument("--out-dir", default="patches/escort_transport_caronly_wsc")
    p.add_argument("--terms", nargs="+", default=["escort", "transport"])
    p.add_argument("--files", nargs="*")
    add_common_patch_args(p)
    p.set_defaults(func=cmd_batch_patch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
