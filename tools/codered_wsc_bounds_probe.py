#!/usr/bin/env python3
"""
Code RED WSC Bounds Probe

Focused, rollback-safe tool for the proven Code RED WSC workflow:
  RSC85 type-2 WSC -> AES from rdr.exe -> Zstandard decode -> scan u16be/u16le/etc
  -> patch low/high vehicle actor bounds only -> Zstandard repack -> AES encrypt -> validate.

This intentionally avoids the failed generic GUI idea. It is for controlled event/beat scripts.
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
import sys
import tempfile
import zlib

AES_KEY_HASH = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
AES_KEY_OFFSETS = [0x22A2300, 0x2293500]
VEHICLE_IDS = {
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
DEFAULT_FORMATS = ["u16be", "u16le", "i16be", "i16le", "u32be", "u32le", "i32be", "i32le"]
INDEX_FORMATS = ["u8", "u16be", "u16le", "i16be", "i16le", "u32be", "u32le", "i32be", "i32le"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()


def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for cur in [p, *p.parents]:
        if (cur / "tools").exists() or (cur / "Code_RED.bat").exists() or (cur / "main.py").exists():
            return cur
    return Path.cwd()


def likely_rdr_exe_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("CODERED_RDR_EXE")
    if env:
        paths.append(Path(env))
    paths.extend([
        root / "rdr.exe",
        root.parent / "rdr.exe",
        Path.cwd() / "rdr.exe",
        Path.cwd().parent / "rdr.exe",
    ])
    out: list[Path] = []
    seen: set[str] = set()
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
        raise RuntimeError("Install dependency first: py -3 -m pip install cryptography") from exc
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
    flag1 = struct.unpack_from("<i", data, 8)[0]
    flag2 = struct.unpack_from("<i", data, 12)[0]
    f1u = struct.unpack_from("<I", data, 8)[0]
    f2u = struct.unpack_from("<I", data, 12)[0]
    virtual_size = (f2u & 0x7FF) * 4096
    physical_size = (f1u & 0x7FF) * 4096
    return {
        "is_rsc": True,
        "magic": "RSC" + f"{magic[3]:02X}",
        "resource_type": resource_type,
        "flag1_signed": flag1,
        "flag2_signed": flag2,
        "flag1_hex": f"0x{f1u:08X}",
        "flag2_hex": f"0x{f2u:08X}",
        "header_size": 16,
        "payload_size": len(data) - 16,
        "virtual_size": virtual_size,
        "physical_size": physical_size,
        "expected_unpacked_size": virtual_size + physical_size,
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
            with tempfile.TemporaryDirectory(prefix="codered_bounds_zstd_") as td:
                inp = Path(td) / "in.zst"
                outp = Path(td) / "out.bin"
                inp.write_bytes(data)
                proc = subprocess.run([exe, "-d", "-f", "-q", str(inp), "-o", str(outp)], capture_output=True, text=True)
                if proc.returncode == 0 and outp.exists():
                    return outp.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd.exe decompression failed")
        raise RuntimeError("zstandard support unavailable or failed: " + str(py_exc))


def zstd_compress(data: bytes, level: int = 22, *, write_content_size: bool | None = None, write_checksum: bool = False, write_dict_id: bool = False) -> bytes:
    try:
        import zstandard as zstd  # type: ignore
        kwargs = {"level": level, "write_checksum": write_checksum, "write_dict_id": write_dict_id}
        if write_content_size is not None:
            kwargs["write_content_size"] = write_content_size
        return zstd.ZstdCompressor(**kwargs).compress(data)
    except Exception as py_exc:
        exe = _zstd_cli()
        if exe and write_content_size is None and not write_checksum and not write_dict_id:
            with tempfile.TemporaryDirectory(prefix="codered_bounds_zstd_") as td:
                inp = Path(td) / "in.bin"
                outp = Path(td) / "out.zst"
                inp.write_bytes(data)
                proc = subprocess.run([exe, "-f", "-q", f"-{level}", str(inp), "-o", str(outp)], capture_output=True, text=True)
                if proc.returncode == 0 and outp.exists():
                    return outp.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd.exe compression failed")
        raise RuntimeError("zstandard support unavailable or failed: " + str(py_exc))


def zstd_compression_candidates(data: bytes, levels: list[int], fit_sweep: bool) -> list[tuple[str, bytes]]:
    """Return labeled zstd frames to try for fitting into an existing RSC payload slot."""
    candidates: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    variants: list[tuple[str, dict]] = [("default", {})]
    if fit_sweep:
        # Smaller frame headers sometimes save exactly the few bytes needed for WSC exact/padded fit.
        variants.extend([
            ("no-content-size", {"write_content_size": False}),
            ("content-size", {"write_content_size": True}),
            ("no-content-size-no-dict", {"write_content_size": False, "write_dict_id": False}),
        ])
    for level in levels:
        for label, kwargs in variants:
            try:
                blob = zstd_compress(data, level, **kwargs)
            except Exception:
                continue
            h = sha256(blob)
            if h in seen:
                continue
            seen.add(h)
            candidates.append((f"zstd-level-{level}-{label}", blob))
    # Prefer smaller first, with stable tiebreaker.
    candidates.sort(key=lambda item: (len(item[1]), item[0]))
    return candidates


def zstd_skippable_padding(size: int) -> bytes:
    if size == 0:
        return b""
    if size < 8:
        raise ValueError("zstd skippable padding needs at least 8 bytes")
    return struct.pack("<II", 0x184D2A50, size - 8) + (b"\x00" * (size - 8))


def decode_wsc(path: Path, root: Path, explicit_exe: str | None = None) -> tuple[bytes, bytes, dict]:
    raw = path.read_bytes()
    rsc = parse_rsc_header(raw)
    report = {
        "input": str(path),
        "input_size": len(raw),
        "input_sha256": sha256(raw),
        "rsc": rsc,
    }
    if not rsc.get("is_rsc"):
        raise RuntimeError("Input is not an RSC resource")
    if rsc.get("resource_type") != 2:
        raise RuntimeError("Input is not RSC resource_type 2 script data")
    key, attempts = get_aes_key(root, explicit_exe)
    report["aes_key_attempts"] = attempts
    if key is None:
        report["status"] = "blocked-no-aes-key"
        raise RuntimeError(json.dumps(report, indent=2))
    encrypted_payload = raw[16:]
    decrypted = aes_crypt_block(encrypted_payload, key, decrypt=True)
    expected = int(rsc.get("expected_unpacked_size") or 0) or None
    try:
        decoded = zstd_decompress(decrypted, expected)
        codec = "zstd"
        err = None
    except Exception as exc:
        decoded = b""
        codec = "unknown"
        err = str(exc)
    report["decode"] = {
        "encrypted_payload_size": len(encrypted_payload),
        "decrypted_payload_sha256": sha256(decrypted),
        "codec": codec,
        "decompress_error": err,
        "decoded_size": len(decoded),
    }
    if not decoded or err:
        report["status"] = "blocked-decode-failed"
        raise RuntimeError(json.dumps(report, indent=2))
    return raw, decoded, report


def pack_int(value: int, fmt: str) -> bytes:
    if fmt == "u8":
        return struct.pack("B", value)
    if fmt == "u16be":
        return struct.pack(">H", value)
    if fmt == "u16le":
        return struct.pack("<H", value)
    if fmt == "i16be":
        return struct.pack(">h", value)
    if fmt == "i16le":
        return struct.pack("<h", value)
    if fmt == "u32be":
        return struct.pack(">I", value)
    if fmt == "u32le":
        return struct.pack("<I", value)
    if fmt == "i32be":
        return struct.pack(">i", value)
    if fmt == "i32le":
        return struct.pack("<i", value)
    raise ValueError(f"Unsupported integer format: {fmt}")


def iter_hits(data: bytes, value: int, fmt: str) -> list[int]:
    # Some formats cannot represent the requested value (for example u8 cannot
    # represent actor IDs like 1183). Treat those as zero hits instead of
    # aborting the entire scan.
    try:
        needle = pack_int(value, fmt)
    except (struct.error, ValueError):
        return []
    hits: list[int] = []
    start = 0
    while True:
        i = data.find(needle, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    return hits


def parse_byte_value(text: str | None, default: int = 0x41) -> int:
    if text is None or text == "":
        return default
    t = str(text).strip().lower()
    if t.startswith("0x"):
        v = int(t, 16)
    else:
        v = int(t, 10)
    if not (0 <= v <= 255):
        raise ValueError(f"Byte value out of range: {text}")
    return v


def hit_context(data: bytes, offset: int, width: int, radius: int = 16) -> str:
    a = max(0, offset - radius)
    b = min(len(data), offset + width + radius)
    return data[a:b].hex(" ").upper()


def hit_has_literal_prev(data: bytes, offset: int, prev_byte: int) -> bool:
    return offset > 0 and data[offset - 1] == prev_byte


def is_ascii_digit_boundary(data: bytes, start: int, width: int) -> bool:
    # Used only for literal ASCII digit scans. Ensures #### is not part of 123#### or ####99.
    before_ok = start == 0 or not (48 <= data[start - 1] <= 57)
    after = start + width
    after_ok = after >= len(data) or not (48 <= data[after] <= 57)
    return before_ok and after_ok


def scan_vehicle_hits(decoded: bytes, formats: list[str]) -> list[dict]:
    rows: list[dict] = []
    for fmt in formats:
        for value, name in VEHICLE_IDS.items():
            hits = iter_hits(decoded, value, fmt)
            if hits:
                rows.append({
                    "format": fmt,
                    "value": value,
                    "name": name,
                    "count": len(hits),
                    "offsets_hex": ";".join(f"0x{x:X}" for x in hits[:100]),
                })
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        keys: list[str] = []
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(k)
        fieldnames = keys or ["empty"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def candidate_bounds(rows: list[dict], fmt_filter: str = "u16be") -> list[dict]:
    counts: dict[int, int] = {}
    for r in rows:
        if r.get("format") == fmt_filter:
            counts[int(r["value"])] = int(r["count"])
    candidates: list[dict] = []
    values = sorted(counts)
    for low in values:
        for high in values:
            if high <= low:
                continue
            if not (1177 <= low <= 1202 and 1177 <= high <= 1202):
                continue
            span = high - low
            if 1 <= span <= 25:
                candidates.append({
                    "format": fmt_filter,
                    "old_low": low,
                    "old_low_name": VEHICLE_IDS.get(low, ""),
                    "old_low_count": counts.get(low, 0),
                    "old_high": high,
                    "old_high_name": VEHICLE_IDS.get(high, ""),
                    "old_high_count": counts.get(high, 0),
                    "span": span,
                    "suggest_new_low": 1193,
                    "suggest_new_low_name": "Truck01",
                    "suggest_new_high": 1194,
                    "suggest_new_high_name": "Car01",
                    "patch_hint": f"--old-low {low} --old-high {high} --new-low 1193 --new-high 1194 --int-format {fmt_filter}",
                })
    # Prefer ranges with cart/wagon/stagecoach endpoints and small hit counts.
    def score(c: dict) -> tuple[int, int, int]:
        low = int(c["old_low"]); high = int(c["old_high"]); span = int(c["span"])
        vehicleish = 0
        for v in (low, high):
            n = VEHICLE_IDS.get(v, "").lower()
            if any(t in n for t in ["wagon", "coach", "cart", "stagecoach"]):
                vehicleish -= 5
        if low <= 1194 <= high:
            vehicleish += 3
        return (vehicleish, abs(span - 14), int(c["old_low_count"]) + int(c["old_high_count"]))
    candidates.sort(key=score)
    return candidates


def repack_wsc(
    raw: bytes,
    decoded_patched: bytes,
    key: bytes,
    level: int,
    allow_padding: bool,
    *,
    fit_sweep: bool = False,
    allow_variable_size: bool = False,
    max_growth: int = 256,
) -> tuple[bytes | None, dict]:
    rsc = parse_rsc_header(raw)
    original_payload_size = int(rsc["payload_size"])
    levels = list(range(1, 23)) if fit_sweep else [level]
    candidates = zstd_compression_candidates(decoded_patched, levels, fit_sweep)
    attempts: list[dict] = []
    fit_report = {
        "compress_codec": "zstd-fit-sweep" if fit_sweep else f"zstd-level-{level}",
        "original_payload_size": original_payload_size,
        "attempts": attempts,
    }

    best_exact: tuple[str, bytes] | None = None
    best_pad: tuple[str, bytes, int] | None = None
    best_variable: tuple[str, bytes, int] | None = None

    for label, compressed in candidates:
        size = len(compressed)
        delta = size - original_payload_size
        item = {"codec": label, "size": size, "delta": delta}
        if len(attempts) < 80:
            attempts.append(item)
        if size == original_payload_size and best_exact is None:
            best_exact = (label, compressed)
            break
        if size < original_payload_size and allow_padding:
            pad = original_payload_size - size
            if pad == 0:
                best_exact = (label, compressed)
                break
            if pad >= 8 and best_pad is None:
                best_pad = (label, compressed, pad)
        if allow_variable_size and 0 < delta <= max_growth and best_variable is None:
            best_variable = (label, compressed, delta)

    payload = None
    chosen_label = None
    if best_exact is not None:
        chosen_label, payload = best_exact
        fit_report["fit_mode"] = "exact"
    elif best_pad is not None:
        chosen_label, compressed, pad = best_pad
        payload = compressed + zstd_skippable_padding(pad)
        fit_report["fit_mode"] = "zstd-skippable-padding"
        fit_report["pad"] = pad
    elif best_variable is not None:
        chosen_label, payload, growth = best_variable
        fit_report["fit_mode"] = "variable-size-rpf-required"
        fit_report["growth"] = growth
        fit_report["warning"] = "Output WSC size changes; inject with an RPF path that updates entry size/TOC. Do not raw-overwrite fixed-size slots."
    else:
        smallest = min((len(c) for _, c in candidates), default=None)
        largest_under = max((len(c) for _, c in candidates if len(c) < original_payload_size), default=None)
        fit_report["smallest_candidate_size"] = smallest
        fit_report["largest_under_original_size"] = largest_under
        if smallest is None:
            fit_report["fit_mode"] = "blocked-no-compression-candidates"
        elif smallest > original_payload_size:
            fit_report["fit_mode"] = "blocked-compressed-output-too-large"
            fit_report["smallest_over_by"] = smallest - original_payload_size
        else:
            fit_report["fit_mode"] = "blocked-padding-too-small-or-disabled"
            fit_report["under_by"] = original_payload_size - smallest

    if payload is None:
        return None, fit_report

    encrypted = aes_crypt_block(payload, key, decrypt=False)
    out = raw[:16] + encrypted
    fit_report["chosen_codec"] = chosen_label
    fit_report["compressed_or_padded_size"] = len(payload)
    fit_report["output_size"] = len(out)
    fit_report["output_sha256"] = sha256(out)

    # validate
    decrypted = aes_crypt_block(out[16:], key, decrypt=True)
    try:
        validate_decoded = zstd_decompress(decrypted, int(rsc.get("expected_unpacked_size") or 0) or None)
        fit_report["validate_ok"] = validate_decoded == decoded_patched
        fit_report["validate_decoded_size"] = len(validate_decoded)
        fit_report["validate_error"] = None
    except Exception as exc:
        fit_report["validate_ok"] = False
        fit_report["validate_error"] = str(exc)
    return out, fit_report


def command_status(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    key, attempts = get_aes_key(root, args.rdr_exe)
    print(json.dumps({
        "tool": "Code RED WSC Bounds Probe",
        "version": "1.3",
        "cwd": str(Path.cwd()),
        "repo_root_guess": str(root),
        "aes_key_available": key is not None,
        "aes_key_attempts": attempts,
        "vehicle_range": {str(k): v for k, v in VEHICLE_IDS.items()},
        "notes": [
            "Use this for controlled event/beat WSC bounds patching, not broad GUI replacement.",
            "Known-good format for beat_crime_wagonthief was u16be bounds patch.",
            "v1.3 removes the bad hardcoded 0x41 default guard and adds preview/max-replacement/context reporting for safer bounds patch review.",
        ],
    }, indent=2))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    rows = []
    for input_str in args.input:
        p = Path(input_str)
        data = p.read_bytes()
        rows.append({"input": str(p), "size": len(data), "sha256": sha256(data), "rsc": parse_rsc_header(data)})
    print(json.dumps({"files": rows}, indent=2))
    return 0


def command_scan(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    inputs: list[Path] = []
    for s in args.input:
        p = Path(s)
        if p.is_dir():
            inputs.extend(sorted([x for x in p.rglob("*.wsc")]))
        else:
            inputs.append(p)
    out_root = Path(args.out)
    summary_rows = []
    for p in inputs:
        file_out = out_root / p.stem
        file_out.mkdir(parents=True, exist_ok=True)
        try:
            raw, decoded, report = decode_wsc(p, root, args.rdr_exe)
            formats = args.formats or DEFAULT_FORMATS
            rows = scan_vehicle_hits(decoded, formats)
            cands = candidate_bounds(rows, args.candidate_format)
            decoded_path = file_out / f"{p.name}.decoded_payload.bin"
            decoded_path.write_bytes(decoded)
            hits_path = file_out / f"{p.name}.vehicle_hits.csv"
            cand_path = file_out / f"{p.name}.candidate_bounds.csv"
            report_path = file_out / f"{p.name}.scan_report.json"
            write_csv(hits_path, rows)
            write_csv(cand_path, cands)
            report.update({
                "status": "decoded",
                "decoded_payload_sha256": sha256(decoded),
                "vehicle_hits": len(rows),
                "candidate_bounds": len(cands),
                "top_candidates": cands[:10],
                "outputs": {"decoded_payload_bin": str(decoded_path), "vehicle_hits_csv": str(hits_path), "candidate_bounds_csv": str(cand_path), "scan_report_json": str(report_path)},
            })
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            summary_rows.append({"input": str(p), "status": "decoded", "vehicle_hits": len(rows), "candidate_bounds": len(cands), "top_hint": cands[0].get("patch_hint") if cands else ""})
        except Exception as exc:
            err = str(exc)
            err_path = file_out / f"{p.name}.scan_error.txt"
            file_out.mkdir(parents=True, exist_ok=True)
            err_path.write_text(err, encoding="utf-8")
            summary_rows.append({"input": str(p), "status": "error", "vehicle_hits": 0, "candidate_bounds": 0, "top_hint": err[:200]})
    write_csv(out_root / "summary.csv", summary_rows)
    print(json.dumps({"out": str(out_root), "files": summary_rows}, indent=2))
    return 0


def command_patch_bounds(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    p = Path(args.input)
    raw, decoded, report = decode_wsc(p, root, args.rdr_exe)
    key, attempts = get_aes_key(root, args.rdr_exe)
    if key is None:
        raise RuntimeError("AES key not found")
    fmt = args.int_format
    mapping = {args.old_low: args.new_low, args.old_high: args.new_high}
    patched = bytearray(decoded)
    replacements = []
    context_mode = getattr(args, "context_mode", "none")
    literal_prev_byte = parse_byte_value(getattr(args, "literal_prev_byte", ""), 0x41)
    preview_rows: list[dict] = []
    skipped_context = []
    # Important: decoded WSC vehicle IDs are binary operands, not ASCII digit strings.
    # There is no safe text boundary test like ,1188, here.  The safest general
    # guard is: exact selected integer format + exact selected low/high values +
    # small replacement count + reviewable context rows.
    for old, new in mapping.items():
        old_bytes = pack_int(old, fmt)
        new_bytes = pack_int(new, fmt)
        start = 0
        while True:
            i = bytes(patched).find(old_bytes, start)
            if i < 0:
                break
            width = len(old_bytes)
            prev_byte = patched[i - 1] if i > 0 else None
            next_byte = patched[i + width] if i + width < len(patched) else None
            context_ok = True
            reason = ""
            if context_mode == "prev-byte" and fmt != "u8":
                context_ok = hit_has_literal_prev(patched, i, literal_prev_byte)
                if not context_ok:
                    reason = f"previous byte is {prev_byte:#04x} not {literal_prev_byte:#04x}" if prev_byte is not None else "no previous byte"
            row = {
                "offset_hex": f"0x{i:X}",
                "format": fmt,
                "old": old,
                "old_name": VEHICLE_IDS.get(old, ""),
                "new": new,
                "new_name": VEHICLE_IDS.get(new, ""),
                "prev_byte_hex": f"0x{prev_byte:02X}" if prev_byte is not None else "",
                "next_byte_hex": f"0x{next_byte:02X}" if next_byte is not None else "",
                "context_mode": context_mode,
                "context_ok": context_ok,
                "context_hex": hit_context(decoded, i, width),
            }
            preview_rows.append(row)
            if not context_ok:
                row2 = dict(row)
                row2["reason"] = reason
                skipped_context.append(row2)
                start = i + width
                continue
            replacements.append(row)
            start = i + width

    if len(replacements) > int(args.max_replacements):
        out_path = Path(args.out)
        report_out = out_path.with_suffix(out_path.suffix + ".report.json")
        report_out.parent.mkdir(parents=True, exist_ok=True)
        write_csv(out_path.with_suffix(out_path.suffix + ".preview_hits.csv"), preview_rows)
        patch_report = {
            "status": "blocked-too-many-replacements",
            "reason": "Patch would change more hits than the configured safety limit.",
            "input": str(p),
            "int_format": fmt,
            "old_low": args.old_low,
            "old_high": args.old_high,
            "replacements": len(replacements),
            "max_replacements": int(args.max_replacements),
            "preview_hits_csv": str(out_path.with_suffix(out_path.suffix + ".preview_hits.csv")),
        }
        report_out.write_text(json.dumps(patch_report, indent=2), encoding="utf-8")
        print(json.dumps(patch_report, indent=2))
        return 2

    if getattr(args, "preview_only", False):
        out_path = Path(args.out)
        report_out = out_path.with_suffix(out_path.suffix + ".report.json")
        report_out.parent.mkdir(parents=True, exist_ok=True)
        write_csv(out_path.with_suffix(out_path.suffix + ".preview_hits.csv"), preview_rows)
        patch_report = {
            "status": "preview-only",
            "input": str(p),
            "int_format": fmt,
            "old_bounds": {"low": args.old_low, "low_name": VEHICLE_IDS.get(args.old_low, ""), "high": args.old_high, "high_name": VEHICLE_IDS.get(args.old_high, "")},
            "new_bounds": {"low": args.new_low, "low_name": VEHICLE_IDS.get(args.new_low, ""), "high": args.new_high, "high_name": VEHICLE_IDS.get(args.new_high, "")},
            "candidate_replacements": len(replacements),
            "skipped_context_hits": len(skipped_context),
            "preview_hits_csv": str(out_path.with_suffix(out_path.suffix + ".preview_hits.csv")),
        }
        report_out.write_text(json.dumps(patch_report, indent=2), encoding="utf-8")
        print(json.dumps(patch_report, indent=2))
        return 0
    before_rows = scan_vehicle_hits(decoded, [fmt])
    after_rows = scan_vehicle_hits(bytes(patched), [fmt])
    out_path = Path(args.out)
    report_out = out_path.with_suffix(out_path.suffix + ".report.json")
    if not replacements and not args.allow_noop:
        status = "blocked-no-replacements"
        write_csv(out_path.with_suffix(out_path.suffix + ".preview_hits.csv"), preview_rows)
        write_csv(out_path.with_suffix(out_path.suffix + ".skipped_context_hits.csv"), skipped_context)
        patch_report = {"status": status, "reason": "No low/high bounds values found in chosen format/context", "input": str(p), "old_low": args.old_low, "old_high": args.old_high, "int_format": fmt, "context_mode": context_mode, "literal_prev_byte_hex": f"0x{literal_prev_byte:02X}", "preview_hits": len(preview_rows), "skipped_context_hits": len(skipped_context), "preview_hits_csv": str(out_path.with_suffix(out_path.suffix + ".preview_hits.csv")), "skipped_context_hits_csv": str(out_path.with_suffix(out_path.suffix + ".skipped_context_hits.csv"))}
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(json.dumps(patch_report, indent=2), encoding="utf-8")
        print(json.dumps(patch_report, indent=2))
        return 2
    out_bytes, fit = repack_wsc(raw, bytes(patched), key, args.zstd_level, args.allow_padding, fit_sweep=args.fit_sweep, allow_variable_size=args.allow_variable_size, max_growth=args.max_growth)
    patch_report = {
        **report,
        "mode": "patch-bounds",
        "int_format": fmt,
        "old_bounds": {"low": args.old_low, "low_name": VEHICLE_IDS.get(args.old_low, ""), "high": args.old_high, "high_name": VEHICLE_IDS.get(args.old_high, "")},
        "new_bounds": {"low": args.new_low, "low_name": VEHICLE_IDS.get(args.new_low, ""), "high": args.new_high, "high_name": VEHICLE_IDS.get(args.new_high, "")},
        "replacements": len(replacements),
        "context_mode": context_mode,
        "literal_prev_byte_hex": f"0x{literal_prev_byte:02X}",
        "preview_hits": len(preview_rows),
        "skipped_context_hits": len(skipped_context),
        "max_replacements": int(args.max_replacements),
        "fit_report": fit,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out_path.with_suffix(out_path.suffix + ".preview_hits.csv"), preview_rows)
    write_csv(out_path.with_suffix(out_path.suffix + ".replacements.csv"), replacements)
    write_csv(out_path.with_suffix(out_path.suffix + ".skipped_context_hits.csv"), skipped_context)
    write_csv(out_path.with_suffix(out_path.suffix + ".before_hits.csv"), before_rows)
    write_csv(out_path.with_suffix(out_path.suffix + ".after_hits.csv"), after_rows)
    out_path.with_suffix(out_path.suffix + ".decoded_payload_before.bin").write_bytes(decoded)
    out_path.with_suffix(out_path.suffix + ".decoded_payload_after.bin").write_bytes(bytes(patched))
    if out_bytes is None:
        patch_report["status"] = "blocked-repack-fit-failed"
        report_out.write_text(json.dumps(patch_report, indent=2), encoding="utf-8")
        print(json.dumps(patch_report, indent=2))
        return 3
    if not fit.get("validate_ok"):
        patch_report["status"] = "blocked-validation-failed"
        report_out.write_text(json.dumps(patch_report, indent=2), encoding="utf-8")
        print(json.dumps(patch_report, indent=2))
        return 4
    out_path.write_bytes(out_bytes)
    patch_report["status"] = "patched"
    patch_report["output"] = str(out_path)
    report_out.write_text(json.dumps(patch_report, indent=2), encoding="utf-8")
    print(json.dumps(patch_report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Code RED WSC Bounds Probe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("status")
    sp.add_argument("--rdr-exe")
    sp.set_defaults(func=command_status)
    sp = sub.add_parser("inspect")
    sp.add_argument("--input", nargs="+", required=True)
    sp.set_defaults(func=command_inspect)
    sp = sub.add_parser("scan")
    sp.add_argument("--input", nargs="+", required=True, help="WSC file(s) or directories")
    sp.add_argument("--out", default="logs/wsc_bounds_probe/scan")
    sp.add_argument("--rdr-exe")
    sp.add_argument("--formats", nargs="*", choices=INDEX_FORMATS)
    sp.add_argument("--candidate-format", default="u16be", choices=INDEX_FORMATS)
    sp.set_defaults(func=command_scan)
    sp = sub.add_parser("patch-bounds")
    sp.add_argument("--input", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--rdr-exe")
    sp.add_argument("--int-format", default="u16be", choices=INDEX_FORMATS)
    sp.add_argument("--old-low", type=int, required=True)
    sp.add_argument("--old-high", type=int, required=True)
    sp.add_argument("--new-low", type=int, default=1193)
    sp.add_argument("--new-high", type=int, default=1194)
    sp.add_argument("--zstd-level", type=int, default=22)
    sp.add_argument("--allow-padding", action="store_true", default=True)
    sp.add_argument("--no-padding", action="store_false", dest="allow_padding")
    sp.add_argument("--fit-sweep", action="store_true", help="Try zstd levels 1-22 plus smaller frame-header variants before blocking.")
    sp.add_argument("--allow-variable-size", action="store_true", help="Write a larger/smaller validated WSC for RPF reinjection with entry-size update if exact/padded fit fails.")
    sp.add_argument("--max-growth", type=int, default=256, help="Maximum byte growth allowed with --allow-variable-size.")
    sp.add_argument("--context-mode", choices=["none", "prev-byte"], default="none", help="Binary WSC IDs are not ASCII text. Default patches exact selected low/high values in the chosen integer format. Use prev-byte only for research if a known opcode context is proven.")
    sp.add_argument("--literal-prev-byte", default="", help="Required previous byte for --context-mode prev-byte, for example 0x41.")
    sp.add_argument("--max-replacements", type=int, default=16, help="Safety limit for candidate replacements before blocking.")
    sp.add_argument("--preview-only", action="store_true", help="Decode and list candidate replacement contexts without writing a patched WSC.")
    sp.add_argument("--allow-noop", action="store_true")
    sp.set_defaults(func=command_patch_bounds)
    return ap


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
