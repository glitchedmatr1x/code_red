#!/usr/bin/env python3
"""
Code RED WSC Vehicle Replacer

Generic, careful RDR1 WSC vehicle actor-ID scanner/patcher.

This is based on the proven wagon-thief path:
  RSC85 type 2 script -> AES decrypt with local rdr.exe key -> Zstandard decode
  -> patch decoded binary vehicle actor IDs -> Zstandard repack -> AES encrypt
  -> exact-size output validation.

No source file is modified. The tool always writes a new patched copy.
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
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import zlib

AES_KEY_HASH = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
AES_KEY_OFFSETS = [0x22A2300, 0x2293500]
SCRIPT_EXTS = {".wsc", ".xsc", ".csc", ".sco"}

VEHICLES = [
    (1177, "Stagecoach"),
    (1178, "Stagecoach002"),
    (1179, "Stagecoach003"),
    (1180, "Stagecoach004"),
    (1181, "dlc_Vehicle01x"),
    (1182, "StagecoachGatling01"),
    (1183, "Cart01"),
    (1184, "Cart02"),
    (1185, "Cart003"),
    (1186, "Cart004"),
    (1187, "Cart005"),
    (1188, "Cart006"),
    (1189, "Canoe01"),
    (1190, "Raft02"),
    (1191, "Raft03"),
    (1192, "Raft01"),
    (1193, "Truck01"),
    (1194, "Car01"),
    (1195, "Wagon04"),
    (1196, "Wagon05"),
    (1197, "WagonPrison01"),
    (1198, "WagonGatling01"),
    (1199, "Wagon02"),
    (1200, "Chuckwagon"),
    (1201, "Chuckwagon02"),
    (1202, "Coach01"),
]
VEHICLE_BY_ID = dict(VEHICLES)
VEHICLE_IDS = {vid for vid, _ in VEHICLES}

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
DEFAULT_FORMATS = ["u16be", "u16le", "u32le", "u32be", "i16le", "i16be", "u8", "i32le", "i32be"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()


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
    paths: list[Path] = []
    if explicit_exe:
        ex = Path(explicit_exe)
        paths.append(ex)
        # Users often browse to launchers such as PlayRDR.exe. If that exact exe
        # does not contain the key, automatically try rdr.exe in the same folder.
        if ex.name.lower() != "rdr.exe":
            paths.append(ex.parent / "rdr.exe")
    paths.extend(likely_rdr_exe_paths(root))
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        try:
            key_s = str(path.resolve()) if path.exists() else str(path)
        except Exception:
            key_s = str(path)
        if key_s.lower() not in seen:
            deduped.append(path)
            seen.add(key_s.lower())
    for path in deduped:
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
        raise RuntimeError("Python package 'cryptography' is required. Run install_wsc_vehicle_replacer_deps.bat") from exc
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
            with tempfile.TemporaryDirectory(prefix="codered_wsc_vehicle_zstd_") as td:
                inp = Path(td) / "in.zst"
                outp = Path(td) / "out.bin"
                inp.write_bytes(data)
                proc = subprocess.run([exe, "-d", "-f", "-q", str(inp), "-o", str(outp)], capture_output=True, text=True)
                if proc.returncode == 0 and outp.exists():
                    return outp.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd.exe decompression failed")
        raise RuntimeError("zstandard support unavailable or failed: " + str(py_exc))


def zstd_compress(data: bytes, level: int = 12) -> bytes:
    try:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdCompressor(level=level).compress(data)
    except Exception as py_exc:
        exe = _zstd_cli()
        if exe:
            with tempfile.TemporaryDirectory(prefix="codered_wsc_vehicle_zstd_") as td:
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
        if expected_size and len(out) != expected_size:
            return out, f"zstd-size-{len(out)}", None
        return out, "zstd", None
    except Exception as exc:
        errors.append("zstd: " + str(exc))
    for name, fn in [("zlib", lambda b: zlib.decompress(b)), ("raw-deflate", lambda b: zlib.decompress(b, -15))]:
        try:
            out = fn(blob)
            if expected_size and len(out) != expected_size:
                return out, name + f"-size-{len(out)}", None
            return out, name, None
        except Exception as exc:
            errors.append(name + ": " + str(exc))
    return None, "unknown", " | ".join(errors)


def compress_candidates(payload: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for level in [22, 21, 20, 19, 18, 15, 12, 9, 6, 3, 1]:
        try:
            out.append((f"zstd-level-{level}", zstd_compress(payload, level)))
        except Exception as exc:
            out.append((f"zstd-unavailable-{level}:{exc}", b""))
            break
    for level in range(9, -1, -1):
        out.append((f"zlib-level-{level}", zlib.compress(payload, level)))
    for level in range(9, -1, -1):
        co = zlib.compressobj(level, zlib.DEFLATED, -15)
        out.append((f"raw-deflate-level-{level}", co.compress(payload) + co.flush()))
    return [(name, data) for name, data in out if data]


def fit_compressed_payload(candidates: list[tuple[str, bytes]], target_size: int, allow_skippable_padding: bool = False) -> tuple[str, bytes, dict] | None:
    """Fit compressed payload back into the original RSC payload byte length.

    Game-safe default is exact-size only. Earlier builds allowed appending a
    Zstandard skippable frame when the compressed output was smaller. CodeX and
    Python can decode that, but the retail game may reject the chained/skippable
    trailing frame, especially for startup-loaded WSC files. Therefore padding is
    now opt-in only.
    """
    attempts: list[dict] = []
    best_smaller: dict | None = None
    best_larger: dict | None = None
    for cname, comp in candidates:
        size = len(comp)
        if size == target_size:
            attempts.append({"codec": cname, "size": size, "fit": "exact"})
            return cname, comp, {"fit_mode": "exact-game-safe", "codec": cname, "pad": 0, "attempts": attempts}
        if size > target_size:
            over = size - target_size
            attempts.append({"codec": cname, "size": size, "over_by": over, "fit": "too-large"})
            if best_larger is None or over < best_larger.get("over_by", 10**9):
                best_larger = {"codec": cname, "size": size, "over_by": over}
            continue
        pad = target_size - size
        attempts.append({"codec": cname, "size": size, "pad": pad, "fit": "smaller-needs-padding"})
        if best_smaller is None or pad < best_smaller.get("pad", 10**9):
            best_smaller = {"codec": cname, "size": size, "pad": pad}
        if allow_skippable_padding and cname.startswith("zstd") and pad >= 8:
            final = comp + _zstd_skippable_padding(pad)
            attempts.append({"codec": cname, "size": size, "pad": pad, "fit": "zstd-skippable-EXPERIMENTAL"})
            return cname, final, {
                "fit_mode": "experimental-zstd-skippable-padding",
                "game_safe": False,
                "warning": "This validates in tools but may crash the game. Use exact-size outputs for retail testing.",
                "codec": cname,
                "pad": pad,
                "attempts": attempts,
            }
    attempts_summary = {"best_smaller": best_smaller, "best_larger": best_larger, "attempts": attempts}
    return None if not attempts else ("NO_EXACT_FIT", b"", attempts_summary)



def choose_variable_size_payload(candidates: list[tuple[str, bytes]]) -> tuple[str, bytes, dict] | None:
    """Choose a normal single-frame compressed payload without exact-size padding.

    This is intended for RPF replacement workflows where the archive writer updates
    the entry size. It must not be used for raw in-place/exact-slot overwrites.
    """
    attempts: list[dict] = []
    best: tuple[str, bytes] | None = None
    # Prefer Zstandard because CodeX RDR1 resource writer uses Zstandard.
    for cname, comp in candidates:
        attempts.append({"codec": cname, "size": len(comp)})
        if cname.startswith("zstd-level-"):
            # Try a high-compression output first, but avoid skippable padding.
            best = (cname, comp)
            break
    if best is None and candidates:
        best = candidates[0]
    if best is None:
        return None
    cname, comp = best
    return cname, comp, {
        "fit_mode": "variable-size-rpf-replacement",
        "game_safe": "requires-rpf-size-update",
        "warning": "This output may have a different byte size. Inject it with an RPF tool/path that updates the archive entry size/TOC. Do not raw-overwrite an old same-size slot.",
        "codec": cname,
        "size": len(comp),
        "attempts": attempts[:8],
    }

def int_hits(data: bytes, values: set[int], formats: list[str] | None = None) -> list[dict]:
    hits: list[dict] = []
    fmts = formats or DEFAULT_FORMATS
    for fmt_name in fmts:
        if fmt_name not in INT_FORMATS:
            continue
        width, fmt = INT_FORMATS[fmt_name]
        if len(data) < width:
            continue
        for off in range(0, len(data) - width + 1):
            try:
                v = struct.unpack_from(fmt, data, off)[0]
            except struct.error:
                continue
            if int(v) in values:
                hits.append({
                    "offset": off,
                    "hex_offset": f"0x{off:X}",
                    "value": int(v),
                    "vehicle_name": VEHICLE_BY_ID.get(int(v), ""),
                    "format": fmt_name,
                    "width": width,
                    "aligned2": off % 2 == 0,
                    "aligned4": off % 4 == 0,
                    "context_hex": data[max(0, off - 16):min(len(data), off + width + 16)].hex(" ").upper(),
                })
    return hits


def count_hits_by_format_value(hits: list[dict]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for h in hits:
        fmt = str(h.get("format", "unknown"))
        val = str(h.get("value", ""))
        out.setdefault(fmt, {})[val] = out.setdefault(fmt, {}).get(val, 0) + 1
    return {fmt: dict(sorted(vals.items(), key=lambda kv: int(kv[0]))) for fmt, vals in sorted(out.items())}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def decode_wsc(data: bytes, root: Path, rdr_exe: str | None = None) -> tuple[bytes | None, dict, bytes | None, bytes | None]:
    rsc = parse_rsc_header(data)
    report: dict = {"rsc": rsc}
    if not rsc.get("is_rsc") or rsc.get("resource_type") != 2:
        report["status"] = "blocked-not-rsc85-type2-script"
        return None, report, None, None
    key, attempts = get_aes_key(root, rdr_exe)
    report["aes_key_attempts"] = attempts
    if key is None:
        report["status"] = "blocked-no-aes-key"
        return None, report, None, None
    encrypted_payload = data[16:]
    decrypted_compressed = aes_crypt_block(encrypted_payload, key, decrypt=True)
    expected = rsc.get("expected_unpacked_size") or None
    decoded, codec, err = try_decompress(decrypted_compressed, expected)
    report["decode"] = {
        "encrypted_payload_size": len(encrypted_payload),
        "decrypted_payload_sha256": sha256(decrypted_compressed),
        "codec": codec,
        "decompress_error": err,
        "decoded_size": len(decoded) if decoded is not None else 0,
    }
    report["status"] = "decoded" if decoded is not None else "blocked-decompress-failed"
    return decoded, report, decrypted_compressed, key


def patch_mapping_by_format(payload: bytes, mapping: dict[int, int], fmt_name: str) -> tuple[bytes, list[dict]]:
    if fmt_name not in INT_FORMATS:
        raise ValueError(f"unsupported integer format: {fmt_name}")
    width, fmt = INT_FORMATS[fmt_name]
    unsigned = fmt[-1] in ("B", "H", "I")
    buf = bytearray(payload)
    replacements: list[dict] = []
    for off in range(0, len(buf) - width + 1):
        v = int(struct.unpack_from(fmt, buf, off)[0])
        if v not in mapping:
            continue
        nv = int(mapping[v])
        if unsigned and nv < 0:
            continue
        try:
            struct.pack_into(fmt, buf, off, nv)
        except struct.error:
            continue
        replacements.append({
            "offset": off,
            "hex_offset": f"0x{off:X}",
            "old": v,
            "old_name": VEHICLE_BY_ID.get(v, ""),
            "new": nv,
            "new_name": VEHICLE_BY_ID.get(nv, ""),
            "format": fmt_name,
            "width": width,
            "aligned2": off % 2 == 0,
            "aligned4": off % 4 == 0,
            "safety": "exact decoded binary integer replacement only; no text substring replacement",
        })
    return bytes(buf), replacements


def build_vehicle_mapping(old_ids: list[int], target_ids: list[int]) -> tuple[dict[int, int], str]:
    if len(target_ids) == 1:
        mapping = {oid: target_ids[0] for oid in old_ids if oid != target_ids[0]}
        return mapping, "all-selected-to-one-target"
    mapping = {oid: target_ids[i % len(target_ids)] for i, oid in enumerate(old_ids)}
    mapping = {k: v for k, v in mapping.items() if k != v}
    return mapping, "round-robin-targets"


def find_exact_fit_candidates(input_path: Path, old_ids: list[int], target_ids: list[int], int_format: str, out_dir: Path, rdr_exe: str | None = None, max_subset_size: int = 2, max_candidates: int = 250) -> dict:
    """Try small, game-safe exact-size patches without writing WSC game files.

    This is for startup/population scripts where a padded Zstandard output can
    validate in tools but crash the retail game. It searches one-ID and small
    subset variants and reports only mappings that recompress to the exact
    original encrypted payload size.
    """
    import itertools

    root = find_repo_root(Path.cwd())
    data = input_path.read_bytes()
    decoded, dec_report, _decrypted, _key = decode_wsc(data, root, rdr_exe)
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "input": str(input_path),
        "input_size": len(data),
        "input_sha256": sha256(data),
        "int_format": int_format,
        "selected_old_ids": old_ids,
        "target_ids": target_ids,
        "max_subset_size": max_subset_size,
        **dec_report,
    }
    if decoded is None:
        report["status"] = dec_report.get("status", "blocked-decode-failed")
        (out_dir / (input_path.name + ".fit_search.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    hit_rows = int_hits(decoded, set(old_ids), formats=[int_format])
    found_ids = sorted({int(h["value"]) for h in hit_rows})
    report["found_selected_old_ids"] = found_ids
    report["found_selected_counts"] = count_hits_by_format_value(hit_rows)
    if not found_ids:
        report["status"] = "blocked-no-selected-ids-found"
        (out_dir / (input_path.name + ".fit_search.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    subsets: list[tuple[int, ...]] = []
    for size in range(1, min(max_subset_size, len(found_ids)) + 1):
        subsets.extend(itertools.combinations(found_ids, size))
    if len(found_ids) > max_subset_size:
        subsets.append(tuple(found_ids))
    subsets = subsets[:max_candidates]

    original_payload_size = len(data) - 16
    rows: list[dict] = []
    exact: list[dict] = []
    near: list[dict] = []
    tried = 0
    for subset in subsets:
        tried += 1
        mapping, strategy = build_vehicle_mapping(list(subset), target_ids)
        patched, replacements = patch_mapping_by_format(decoded, mapping, int_format)
        if not replacements:
            continue
        fit = fit_compressed_payload(compress_candidates(patched), original_payload_size, allow_skippable_padding=False)
        status = "no-fit"
        best_smaller = None
        best_larger = None
        if fit is None:
            fit_info = {}
        else:
            cname, _payload, fit_info = fit
            if cname == "NO_EXACT_FIT":
                best_smaller = fit_info.get("best_smaller") if isinstance(fit_info, dict) else None
                best_larger = fit_info.get("best_larger") if isinstance(fit_info, dict) else None
            else:
                status = "exact-fit"
        row = {
            "status": status,
            "subset_old_ids": " ".join(map(str, subset)),
            "target_ids": " ".join(map(str, target_ids)),
            "mapping": json.dumps({str(k): v for k, v in mapping.items()}, sort_keys=True),
            "mapping_strategy": strategy,
            "replacements": len(replacements),
            "best_smaller_pad": (best_smaller or {}).get("pad"),
            "best_smaller_codec": (best_smaller or {}).get("codec"),
            "best_larger_over_by": (best_larger or {}).get("over_by"),
            "best_larger_codec": (best_larger or {}).get("codec"),
        }
        rows.append(row)
        if status == "exact-fit":
            exact.append(row)
        else:
            near.append(row)

    write_csv(out_dir / (input_path.name + ".fit_search_candidates.csv"), rows)
    report.update({
        "status": "exact-fit-candidates-found" if exact else "no-game-safe-exact-fit-candidate",
        "tried_variants": tried,
        "exact_fit_candidates": len(exact),
        "candidate_csv": str(out_dir / (input_path.name + ".fit_search_candidates.csv"),),
        "exact_candidates_sample": exact[:20],
        "nearest_non_exact_sample": sorted(near, key=lambda r: min(
            int(r.get("best_smaller_pad") or 10**9),
            int(r.get("best_larger_over_by") or 10**9)
        ))[:20],
        "explanation": "No WSC game file is written by fit-search. If no exact-fit candidate exists, this script/mapping should be left unpatched or handled through an ASI/native override rather than a padded WSC.",
    })
    (out_dir / (input_path.name + ".fit_search.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def patch_wsc_file(input_path: Path, output_path: Path, old_ids: list[int], target_ids: list[int], int_format: str, rdr_exe: str | None = None, allow_noop: bool = False, allow_skippable_padding: bool = False, variable_size_output: bool = False) -> dict:
    root = find_repo_root(Path.cwd())
    data = input_path.read_bytes()
    decoded, dec_report, _decrypted, key = decode_wsc(data, root, rdr_exe)
    report: dict = {
        "input": str(input_path),
        "output": str(output_path),
        "input_size": len(data),
        "input_sha256": sha256(data),
        "old_ids": old_ids,
        "target_ids": target_ids,
        "int_format": int_format,
        "allow_skippable_padding": allow_skippable_padding,
        "variable_size_output": variable_size_output,
        **dec_report,
    }
    if decoded is None or key is None:
        report["status"] = dec_report.get("status", "blocked-decode-failed")
        return report
    values = set(old_ids) | set(target_ids)
    before_hits = int_hits(decoded, values, formats=[int_format])
    mapping, mapping_strategy = build_vehicle_mapping(old_ids, target_ids)
    patched, replacements = patch_mapping_by_format(decoded, mapping, int_format)
    after_hits = int_hits(patched, values, formats=[int_format])
    report["patch"] = {
        "mapping_strategy": mapping_strategy,
        "mapping": {str(k): v for k, v in mapping.items()},
        "before_hits": len(before_hits),
        "before_counts_by_value": count_hits_by_format_value(before_hits),
        "replacements": len(replacements),
        "after_hits": len(after_hits),
        "after_counts_by_value": count_hits_by_format_value(after_hits),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(output_path.with_suffix(output_path.suffix + ".before_hits.csv"), before_hits)
    write_csv(output_path.with_suffix(output_path.suffix + ".replacements.csv"), replacements)
    write_csv(output_path.with_suffix(output_path.suffix + ".after_hits.csv"), after_hits)
    (output_path.with_suffix(output_path.suffix + ".decoded_payload_before.bin")).write_bytes(decoded)
    (output_path.with_suffix(output_path.suffix + ".decoded_payload_after.bin")).write_bytes(patched)
    if not replacements and not allow_noop:
        report["status"] = "blocked-no-replacements"
        (output_path.with_suffix(output_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    original_payload_size = len(data) - 16
    candidates = compress_candidates(patched)
    fit = fit_compressed_payload(candidates, original_payload_size, allow_skippable_padding=allow_skippable_padding)
    if fit is None:
        report["status"] = "blocked-compression-fit-failed"
        (output_path.with_suffix(output_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    cname, padded, fit_report = fit
    report["compression_fit"] = fit_report
    variable_mode_used = False
    if cname == "NO_EXACT_FIT":
        if variable_size_output:
            var_fit = choose_variable_size_payload(candidates)
            if var_fit is None:
                report["status"] = "blocked-variable-compression-failed"
                (output_path.with_suffix(output_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
                return report
            cname, padded, fit_report = var_fit
            report["compression_fit"] = fit_report
            variable_mode_used = True
        else:
            report["status"] = "blocked-game-safe-exact-compression-not-met"
            report["explanation"] = "The decoded patch was possible, but recompression did not produce the exact original payload size. No game file was written in exact-size mode. Use variable-size RPF replacement output only when you will inject with an RPF tool that updates the archive entry size/TOC."
            (output_path.with_suffix(output_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report
    encrypted_new = aes_crypt_block(padded, key, decrypt=False)
    output_data = data[:16] + encrypted_new
    check_dec = aes_crypt_block(output_data[16:], key, decrypt=True)
    expected = report.get("rsc", {}).get("expected_unpacked_size") or None
    check_payload, check_codec, check_err = try_decompress(check_dec, expected)
    report["repack"] = {
        "compress_codec": cname,
        "fit_report": fit_report,
        "compressed_or_padded_size": len(padded),
        "output_size": len(output_data),
        "output_size_delta_vs_input": len(output_data) - len(data),
        "output_sha256": sha256(output_data),
        "validate_codec": check_codec,
        "validate_error": check_err,
        "validate_decoded_size": len(check_payload) if check_payload is not None else 0,
        "validate_ok": check_payload == patched,
        "variable_size_output": variable_mode_used,
    }
    output_path.write_bytes(output_data)
    if report["repack"]["validate_ok"]:
        report["status"] = "patched-variable-size-rpf-replacement" if variable_mode_used else "patched"
    else:
        report["status"] = "patched-validation-warning"
    (output_path.with_suffix(output_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def scan_file(input_path: Path, out_dir: Path, formats: list[str] | None = None, rdr_exe: str | None = None) -> dict:
    root = find_repo_root(Path.cwd())
    data = input_path.read_bytes()
    decoded, dec_report, decrypted, _key = decode_wsc(data, root, rdr_exe)
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "input": str(input_path),
        "input_size": len(data),
        "input_sha256": sha256(data),
        **dec_report,
    }
    if decoded is None:
        (out_dir / (input_path.name + ".scan.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    fmts = formats or DEFAULT_FORMATS
    hits = int_hits(decoded, VEHICLE_IDS, formats=fmts)
    report.update({
        "decoded_payload_sha256": sha256(decoded),
        "vehicle_hits": len(hits),
        "vehicle_hits_by_format_value": count_hits_by_format_value(hits),
        "decoded_payload_bin": str(out_dir / (input_path.name + ".decoded_payload.bin")),
        "vehicle_hits_csv": str(out_dir / (input_path.name + ".vehicle_hits.csv")),
    })
    (out_dir / (input_path.name + ".decoded_payload.bin")).write_bytes(decoded)
    if decrypted is not None:
        (out_dir / (input_path.name + ".decrypted_compressed.bin")).write_bytes(decrypted)
    write_csv(out_dir / (input_path.name + ".vehicle_hits.csv"), hits)
    (out_dir / (input_path.name + ".scan.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def status_cmd(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    key, attempts = get_aes_key(root, args.rdr_exe)
    report = {
        "tool": "Code RED WSC Vehicle Replacer",
        "version": "1.7",
        "cwd": str(Path.cwd()),
        "repo_root_guess": str(root),
        "aes_key_available": key is not None,
        "aes_key_attempts": attempts,
        "vehicle_count": len(VEHICLES),
        "default_format": "u16be",
        "guardrails": [
            "source files are never modified",
            "RSC85 type-2 scripts are AES-decrypted and Zstandard-decoded before scanning",
            "patch mode replaces exact decoded integer operands only",
            "output is validated; exact-size is safest, variable-size is for RPF reinjection with size/TOC update",
            "game-safe mode blocks padded Zstandard WSC output by default",
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


def scan_cmd(args: argparse.Namespace) -> int:
    report = scan_file(Path(args.input), Path(args.out), formats=args.formats.split(",") if args.formats else None, rdr_exe=args.rdr_exe)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "decoded" else 2


def patch_cmd(args: argparse.Namespace) -> int:
    target_ids = [int(x) for x in args.target_ids]
    old_ids = [int(x) for x in args.old_ids]
    report = patch_wsc_file(Path(args.input), Path(args.out), old_ids, target_ids, args.int_format, rdr_exe=args.rdr_exe, allow_noop=args.allow_noop, allow_skippable_padding=args.allow_skippable_padding, variable_size_output=args.variable_size_output)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in ("patched", "patched-variable-size-rpf-replacement") else 2


def fit_search_cmd(args: argparse.Namespace) -> int:
    target_ids = [int(x) for x in args.target_ids]
    old_ids = [int(x) for x in args.old_ids]
    report = find_exact_fit_candidates(Path(args.input), old_ids, target_ids, args.int_format, Path(args.out), rdr_exe=args.rdr_exe, max_subset_size=args.max_subset_size)
    print(json.dumps(report, indent=2))
    return 0 if report.get("exact_fit_candidates", 0) else 2


class VehicleReplacerGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Code RED WSC Vehicle Replacer v7")
        self.geometry("1280x820")
        self.minsize(1180, 740)
        self.input_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value=str(Path("patches") / "patched_vehicle_replace.wsc"))
        self.rdr_exe_var = tk.StringVar(value=os.environ.get("CODERED_RDR_EXE", ""))
        self.format_var = tk.StringVar(value="u16be")
        self.status_var = tk.StringVar(value="Ready")
        self.old_vars: dict[int, tk.BooleanVar] = {}
        self.target_var = tk.StringVar(value="1194 Car01")
        self.second_target_var = tk.StringVar(value="1193 Truck01")
        self.round_robin_var = tk.BooleanVar(value=True)
        self.show_selected_format_only_var = tk.BooleanVar(value=True)
        self.hide_targets_var = tk.BooleanVar(value=False)
        self.allow_padding_var = tk.BooleanVar(value=False)
        self.variable_size_var = tk.BooleanVar(value=False)
        self.hit_rows: list[dict] = []
        self.hit_counts: dict[tuple[str, int], int] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.configure("Treeview", rowheight=24, font=("Segoe UI", 10))
            style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
            style.configure("TButton", padding=(6, 3))
        except Exception:
            pass
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        paths = ttk.LabelFrame(outer, text="Files")
        paths.pack(fill="x")
        self._path_row(paths, "Input WSC", self.input_var, self._browse_input, row=0)
        self._path_row(paths, "Output WSC", self.output_var, self._browse_output, row=1)
        self._path_row(paths, "rdr.exe override", self.rdr_exe_var, self._browse_rdr, row=2)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(8, 8))
        ttk.Label(controls, text="Integer format").pack(side="left")
        ttk.Combobox(controls, textvariable=self.format_var, values=list(INT_FORMATS.keys()), width=10, state="readonly").pack(side="left", padx=(6, 8))
        ttk.Checkbutton(controls, text="Show selected format only", variable=self.show_selected_format_only_var, command=self._populate_hits_tree).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(controls, text="Hide target IDs", variable=self.hide_targets_var, command=self._populate_hits_tree).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(controls, text="Variable-size RPF output", variable=self.variable_size_var).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(controls, text="Experimental padded output", variable=self.allow_padding_var).pack(side="left", padx=(0, 18))
        ttk.Button(controls, text="Status", command=self.on_status).pack(side="left", padx=3)
        ttk.Button(controls, text="Scan selected WSC", command=self.on_scan).pack(side="left", padx=3)
        ttk.Button(controls, text="Patch selected IDs", command=self.on_patch).pack(side="left", padx=3)
        ttk.Button(controls, text="Find exact-fit variants", command=self.on_fit_search).pack(side="left", padx=3)
        ttk.Button(controls, text="Open output folder", command=self.on_open_output_folder).pack(side="left", padx=3)

        main = ttk.Panedwindow(outer, orient="horizontal")
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main, padding=(0, 0, 8, 0))
        right = ttk.Frame(main)
        main.add(left, weight=1)
        main.add(right, weight=2)

        old_box = ttk.LabelFrame(left, text="Old vehicle IDs to replace")
        old_box.pack(fill="both", expand=True)
        canvas = tk.Canvas(old_box, highlightthickness=0)
        scroll = ttk.Scrollbar(old_box, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for vid, name in VEHICLES:
            var = tk.BooleanVar(value=False)
            self.old_vars[vid] = var
            ttk.Checkbutton(inner, text=f"{vid}  {name}", variable=var).pack(anchor="w", pady=1)
        quick = ttk.Frame(left)
        quick.pack(fill="x", pady=(6, 0))
        ttk.Button(quick, text="Select found IDs", command=self.select_found).pack(side="left", padx=2)
        ttk.Button(quick, text="Select found carts/wagons", command=self.select_found_carts_wagons).pack(side="left", padx=2)
        ttk.Button(quick, text="Clear", command=self.clear_old).pack(side="left", padx=2)

        target_box = ttk.LabelFrame(left, text="Target vehicle")
        target_box.pack(fill="x", pady=(8, 0))
        vehicle_labels = [f"{vid} {name}" for vid, name in VEHICLES]
        ttk.Label(target_box, text="Primary target").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(target_box, textvariable=self.target_var, values=vehicle_labels, width=25, state="readonly").grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Checkbutton(target_box, text="Alternate with second target", variable=self.round_robin_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=4)
        ttk.Label(target_box, text="Second target").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(target_box, textvariable=self.second_target_var, values=vehicle_labels, width=25, state="readonly").grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        target_box.columnconfigure(1, weight=1)

        hits_box = ttk.LabelFrame(right, text="Decoded vehicle hits")
        hits_box.pack(fill="both", expand=True)
        columns = ("format", "value", "name", "count")
        self.tree = ttk.Treeview(hits_box, columns=columns, show="headings", height=14)
        for col, text, width in [("format", "Format", 90), ("value", "ID", 80), ("name", "Vehicle", 180), ("count", "Count", 70)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, side="left")
        yscroll = ttk.Scrollbar(hits_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side="right", fill="y")

        log_box = ttk.LabelFrame(right, text="Log")
        log_box.pack(fill="both", expand=True, pady=(8, 0))
        self.log = tk.Text(log_box, height=12, wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True)
        status = ttk.Label(outer, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", pady=(6, 0))

    def _path_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, browse_cmd, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(parent, text="Browse", command=browse_cmd).grid(row=row, column=2, padx=4, pady=4)
        parent.columnconfigure(1, weight=1)

    def log_msg(self, msg: str) -> None:
        self.log.insert("end", msg.rstrip() + "\n")
        self.log.see("end")
        self.update_idletasks()

    def _browse_input(self) -> None:
        p = filedialog.askopenfilename(title="Choose WSC script", filetypes=[("Script files", "*.wsc *.xsc *.csc *.sco"), ("All files", "*.*")])
        if p:
            self.input_var.set(p)
            stem = Path(p).stem
            self.output_var.set(str(Path("patches") / f"{stem}_vehicle_replaced.wsc"))

    def _browse_output(self) -> None:
        p = filedialog.asksaveasfilename(title="Save patched WSC as", defaultextension=".wsc", filetypes=[("WSC", "*.wsc"), ("All files", "*.*")])
        if p:
            self.output_var.set(p)

    def _browse_rdr(self) -> None:
        p = filedialog.askopenfilename(title="Choose rdr.exe", filetypes=[("rdr.exe", "rdr.exe"), ("Executables", "*.exe"), ("All files", "*.*")])
        if p:
            self.rdr_exe_var.set(p)

    def on_open_output_folder(self) -> None:
        folder = Path(self.output_var.get()).expanduser().resolve().parent
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def select_found_carts_wagons(self) -> None:
        # Generic helper: select only vehicle-like IDs that were actually found
        # in this file and current integer format. This avoids applying the
        # wagon thief range assumption to unrelated scripts.
        found = {int(r["value"]) for r in self.hit_rows if r.get("format") == self.format_var.get()}
        targets = set(self._target_ids())
        keywords = ("stagecoach", "cart", "wagon", "coach", "chuckwagon")
        selected = []
        for vid, var in self.old_vars.items():
            name = VEHICLE_BY_ID.get(vid, "").lower()
            should = (vid in found) and (vid not in targets) and any(k in name for k in keywords)
            var.set(should)
            if should:
                selected.append(vid)
        if not selected:
            messagebox.showinfo(
                "No matching found IDs",
                "No cart/wagon/coach/stagecoach IDs were found in the currently selected integer format. Scan first or choose another integer format."
            )

    def select_wagons_carts(self) -> None:
        # Kept for CLI/backward compatibility only. The GUI no longer exposes this
        # as a general button because it only applies to beat_crime_wagonthief.wsc.
        for vid, var in self.old_vars.items():
            var.set(1183 <= vid <= 1197 and vid not in (1193, 1194))
        self.round_robin_var.set(True)
        self.target_var.set("1194 Car01")
        self.second_target_var.set("1193 Truck01")

    def clear_old(self) -> None:
        for var in self.old_vars.values():
            var.set(False)

    def select_found(self) -> None:
        # Generic mode: only select IDs actually found in the decoded file for
        # the currently selected integer format, excluding chosen target vehicles.
        found = {int(r["value"]) for r in self.hit_rows if r.get("format") == self.format_var.get()}
        targets = set(self._target_ids())
        for vid, var in self.old_vars.items():
            var.set((vid in found) and (vid not in targets))
        if not found:
            messagebox.showinfo("No scan hits", "No vehicle IDs were found in the selected integer format. Scan the file first, or choose another integer format.")

    def _target_ids(self) -> list[int]:
        ids = [int(self.target_var.get().split()[0])]
        if self.round_robin_var.get():
            second = int(self.second_target_var.get().split()[0])
            if second not in ids:
                ids.append(second)
        return ids

    def _old_ids(self) -> list[int]:
        return [vid for vid, var in self.old_vars.items() if var.get()]

    def _is_wagonthief_input(self) -> bool:
        return "beat_crime_wagonthief" in Path(self.input_var.get()).name.lower()

    def on_status(self) -> None:
        try:
            root = find_repo_root(Path.cwd())
            key, attempts = get_aes_key(root, self.rdr_exe_var.get() or None)
            self.log_msg(json.dumps({"aes_key_available": key is not None, "attempts": attempts}, indent=2))
            self.status_var.set("AES key available" if key else "AES key not found — choose rdr.exe, not PlayRDR.exe")
        except Exception as exc:
            messagebox.showerror("Status failed", str(exc))

    def on_scan(self) -> None:
        try:
            if not self.input_var.get().strip():
                messagebox.showwarning("No input file", "Choose a .wsc/.xsc/.csc/.sco file first.")
                return
            path = Path(self.input_var.get())
            out_dir = Path("logs") / "wsc_vehicle_replacer" / (path.stem + "_scan")
            report = scan_file(path, out_dir, formats=DEFAULT_FORMATS, rdr_exe=self.rdr_exe_var.get() or None)
            self.log_msg(json.dumps(report, indent=2))
            self.tree.delete(*self.tree.get_children())
            self.hit_rows = []
            self.hit_counts = {}
            if report.get("status") == "decoded":
                # Load CSV rows so we can summarize and select found IDs.
                csv_path = Path(report["vehicle_hits_csv"])
                with csv_path.open("r", newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        fmt = row.get("format", "")
                        val = int(row.get("value", 0))
                        self.hit_rows.append({"format": fmt, "value": val})
                        self.hit_counts[(fmt, val)] = self.hit_counts.get((fmt, val), 0) + 1
                self._populate_hits_tree()
                self.status_var.set(f"Decoded and scanned: {report.get('vehicle_hits', 0)} hits. Showing filtered table.")
            else:
                self.status_var.set(("AES key not found — choose rdr.exe, not PlayRDR.exe") if report.get("status") == "blocked-no-aes-key" else str(report.get("status")))
        except Exception as exc:
            messagebox.showerror("Scan failed", str(exc))
            self.log_msg("ERROR: " + str(exc))

    def _populate_hits_tree(self) -> None:
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        fmt_filter = self.format_var.get() if self.show_selected_format_only_var.get() else None
        targets = set(self._target_ids())
        for (fmt, val), count in sorted(self.hit_counts.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            if fmt_filter and fmt != fmt_filter:
                continue
            if self.hide_targets_var.get() and val in targets:
                continue
            self.tree.insert("", "end", values=(fmt, val, VEHICLE_BY_ID.get(val, ""), count))

    def on_fit_search(self) -> None:
        try:
            old_ids = self._old_ids()
            target_ids = self._target_ids()
            if not old_ids:
                messagebox.showwarning("No old IDs selected", "Select at least one old vehicle ID to test.")
                return
            if not self.hit_counts:
                messagebox.showwarning("Scan first", "Scan the selected WSC first, then run exact-fit search.")
                return
            path = Path(self.input_var.get())
            out_dir = Path("logs") / "wsc_vehicle_replacer" / (path.stem + "_exact_fit_search")
            report = find_exact_fit_candidates(
                path,
                old_ids,
                target_ids,
                self.format_var.get(),
                out_dir,
                rdr_exe=self.rdr_exe_var.get() or None,
                max_subset_size=2,
            )
            self.log_msg(json.dumps(report, indent=2))
            self.status_var.set(str(report.get("status")))
            if report.get("exact_fit_candidates", 0):
                messagebox.showinfo(
                    "Exact-fit candidates found",
                    f"Found {report.get('exact_fit_candidates')} game-safe exact-fit candidate(s).\nOpen the CSV and patch that smaller set intentionally.\n\n{report.get('candidate_csv')}"
                )
            else:
                messagebox.showinfo(
                    "No exact-fit candidate",
                    "No game-safe exact-size candidate was found for the selected IDs/targets.\nNo file was written. For this script, use a smaller target set, leave it unchanged, or use an ASI/native override instead of a WSC patch."
                )
        except Exception as exc:
            messagebox.showerror("Exact-fit search failed", str(exc))
            self.log_msg("ERROR: " + str(exc))


    def on_patch(self) -> None:
        try:
            old_ids = self._old_ids()
            target_ids = self._target_ids()
            if not old_ids:
                messagebox.showwarning("No old IDs selected", "Select at least one old vehicle ID to replace.")
                return
            if not target_ids:
                messagebox.showwarning("No target selected", "Select a target vehicle.")
                return
            selected_fmt = self.format_var.get()
            if not self.hit_counts:
                messagebox.showwarning("Scan first", "Scan the selected WSC first. The patcher needs decoded vehicle hits from this specific file before it can safely patch it.")
                return
            found_selected = {val for (fmt, val), count in self.hit_counts.items() if fmt == selected_fmt and count > 0}
            missing = [vid for vid in old_ids if vid not in found_selected]
            if len(missing) == len(old_ids):
                messagebox.showwarning("Selected IDs not found", "None of the selected old IDs were found in the selected integer format for this file. Choose IDs from the scan table or change integer format.")
                return
            notes = []
            if missing:
                notes.append("Selected IDs not found in the scanned file/selected format will make no replacements: " + ", ".join(map(str, missing)))
            if self._is_wagonthief_input():
                outside_safe = [vid for vid in old_ids if not (1183 <= vid <= 1197)]
                if outside_safe:
                    notes.append("For beat_crime_wagonthief only, these selected IDs are outside the proven 1183-1197 test range: " + ", ".join(map(str, outside_safe)))
            if not self.round_robin_var.get() and len(old_ids) > 1:
                notes.append("Multiple old IDs will be replaced with the same single target vehicle.")
            if notes:
                msg = "Patch review:\n\n" + "\n\n".join(notes) + "\n\nContinue anyway?"
                if not messagebox.askyesno("Patch review", msg):
                    return
            report = patch_wsc_file(
                Path(self.input_var.get()),
                Path(self.output_var.get()),
                old_ids,
                target_ids,
                self.format_var.get(),
                rdr_exe=self.rdr_exe_var.get() or None,
                allow_noop=False,
                allow_skippable_padding=self.allow_padding_var.get(),
                variable_size_output=self.variable_size_var.get(),
            )
            self.log_msg(json.dumps(report, indent=2))
            self.status_var.set(str(report.get("status")))
            if report.get("status") == "patched":
                messagebox.showinfo("Patched", f"Patched WSC written to:\n{report.get('output')}\n\nReplacements: {report.get('patch', {}).get('replacements')}")
            else:
                extra = ""
                if report.get("status") in ("blocked-compressed-output-too-large", "blocked-game-safe-exact-compression-not-met"):
                    extra = "\n\nThe decoded patch was possible, but recompression did not make an exact original-size WSC payload. No game file was written. This is intentional because padded Zstandard WSCs can validate in tools but crash in the retail game. Try fewer IDs, one-ID-at-a-time variants, or enable Variable-size RPF output if you will inject with an RPF tool that updates entry size/TOC. Experimental padded output is research-only."
                elif report.get("status") == "blocked-no-replacements":
                    extra = "\n\nNo selected IDs were present in the selected integer format. Use the scan table and current format to select actual found IDs."
                messagebox.showwarning("Patch blocked", f"Status: {report.get('status')}\nSee report JSON beside the output path.{extra}")
        except Exception as exc:
            messagebox.showerror("Patch failed", str(exc))
            self.log_msg("ERROR: " + str(exc))


def gui_cmd(_args: argparse.Namespace) -> int:
    app = VehicleReplacerGUI()
    app.mainloop()
    return 0


def list_vehicles_cmd(_args: argparse.Namespace) -> int:
    print(json.dumps([{"id": vid, "name": name} for vid, name in VEHICLES], indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generic Code RED RDR1 WSC vehicle scanner/replacer.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("gui", help="Open the mini GUI")
    p.set_defaults(func=gui_cmd)

    p = sub.add_parser("status")
    p.add_argument("--rdr-exe")
    p.set_defaults(func=status_cmd)

    p = sub.add_parser("list-vehicles")
    p.set_defaults(func=list_vehicles_cmd)

    p = sub.add_parser("scan")
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="logs/wsc_vehicle_replacer/scan")
    p.add_argument("--formats", default=",".join(DEFAULT_FORMATS))
    p.add_argument("--rdr-exe")
    p.set_defaults(func=scan_cmd)

    p = sub.add_parser("patch")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--old-ids", type=int, nargs="+", required=True)
    p.add_argument("--target-ids", type=int, nargs="+", required=True)
    p.add_argument("--int-format", choices=list(INT_FORMATS.keys()), default="u16be")
    p.add_argument("--rdr-exe")
    p.add_argument("--allow-noop", action="store_true")
    p.add_argument("--allow-skippable-padding", action="store_true", help="Experimental: permit Zstandard skippable padding when exact compression size is not possible. Can crash in-game.")
    p.add_argument("--variable-size-output", action="store_true", help="Write a normal variable-size WSC when exact-size compression is impossible. Use only with RPF replacement/injection that updates entry size/TOC.")
    p.set_defaults(func=patch_cmd)

    p = sub.add_parser("fit-search", help="Search for small exact-size, game-safe patch variants without writing WSC game files")
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="logs/wsc_vehicle_replacer/exact_fit_search")
    p.add_argument("--old-ids", type=int, nargs="+", required=True)
    p.add_argument("--target-ids", type=int, nargs="+", required=True)
    p.add_argument("--int-format", choices=list(INT_FORMATS.keys()), default="u16be")
    p.add_argument("--rdr-exe")
    p.add_argument("--max-subset-size", type=int, default=2)
    p.set_defaults(func=fit_search_cmd)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
