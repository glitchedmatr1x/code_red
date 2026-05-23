#!/usr/bin/env python3
"""
Code RED Roadside Ambush Car/Truck WSC Patcher

Purpose:
  Patch event_roadside_ambush.wsc's active wagon/cart/stagecoach vehicle actor IDs from
  1177..1188 to 1193..1194, using the RDR1 trainer-proven actor IDs:
    1193 Truck01
    1194 Car01

Important:
  RSC85 resource_type 2 scripts are AES-protected. This tool must find the
  RDR1 AES key from rdr.exe before it can safely decode/repack the payload.

No source file is modified. Output is written to --out.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
import struct
import sys
import zlib
import shutil
import subprocess
import tempfile

AES_KEY_HASH = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
AES_KEY_OFFSETS = [0x22A2300, 0x2293500]
DEFAULT_OLD_LOW = 1177
DEFAULT_OLD_HIGH = 1188
DEFAULT_NEW_LOW = 1193
DEFAULT_NEW_HIGH = 1194


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
    # de-dupe while preserving order
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

    # CodeX fallback searches a large window in 4-byte steps.
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
    """AES-256-ECB block crypto. Uses cryptography if available."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except Exception as exc:
        raise RuntimeError(
            "Python package 'cryptography' is required for AES script resources. "
            "Run install_wsc_patch_deps.bat or: py -3 -m pip install cryptography"
        ) from exc

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
    # RDR1 RSC85 compact flags, for the type-2 WSC files we are targeting,
    # encode the useful virtual page count in flag2's low bits. This matches
    # Code RED/CodeX observations: 0x8000000F -> 15 * 4096 = 61440.
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
    """Decompress Zstandard using python-zstandard or zstd.exe."""
    try:
        import zstandard as zstd  # type: ignore
        dctx = zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data, max_output_size=expected_size or 0)
        except Exception:
            # Some RDR resources do not expose content size in the frame. Streaming
            # reader works better and also tolerates skippable padding frames.
            with dctx.stream_reader(data) as reader:
                return reader.read()
    except Exception as py_exc:
        exe = _zstd_cli()
        if exe:
            with tempfile.TemporaryDirectory(prefix="codered_wsc_zstd_") as td:
                inp = Path(td) / "in.zst"
                outp = Path(td) / "out.bin"
                inp.write_bytes(data)
                proc = subprocess.run([exe, "-d", "-f", "-q", str(inp), "-o", str(outp)], capture_output=True, text=True)
                if proc.returncode == 0 and outp.exists():
                    return outp.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd.exe decompression failed")
        raise RuntimeError("zstandard support unavailable or failed: " + str(py_exc))


def zstd_compress(data: bytes, level: int = 12) -> bytes:
    """Compress Zstandard using python-zstandard or zstd.exe."""
    try:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdCompressor(level=level).compress(data)
    except Exception as py_exc:
        exe = _zstd_cli()
        if exe:
            with tempfile.TemporaryDirectory(prefix="codered_wsc_zstd_") as td:
                inp = Path(td) / "in.bin"
                outp = Path(td) / "out.zst"
                inp.write_bytes(data)
                proc = subprocess.run([exe, "-f", "-q", f"-{level}", str(inp), "-o", str(outp)], capture_output=True, text=True)
                if proc.returncode == 0 and outp.exists():
                    return outp.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd.exe compression failed")
        raise RuntimeError("zstandard support unavailable or failed: " + str(py_exc))


def _zstd_skippable_padding(size: int) -> bytes:
    """Return a standards-compliant Zstandard skippable frame of exactly size bytes."""
    if size == 0:
        return b""
    if size < 8:
        raise ValueError("zstd skippable padding needs at least 8 bytes")
    # 0x184D2A50 little-endian magic + uint32 payload size + payload bytes.
    return struct.pack("<II", 0x184D2A50, size - 8) + (b"\x00" * (size - 8))


def try_decompress(blob: bytes, expected_size: int | None = None) -> tuple[bytes | None, str, str | None]:
    errors: list[str] = []

    # RDR1 RSC resources are usually Zstandard after optional AES for scripts.
    try:
        out = zstd_decompress(blob, expected_size)
        if expected_size and len(out) != expected_size:
            return out, f"zstd-size-{len(out)}", None
        return out, "zstd", None
    except Exception as exc:
        errors.append("zstd: " + str(exc))

    attempts = [
        ("zlib", lambda b: zlib.decompress(b)),
        ("raw-deflate", lambda b: zlib.decompress(b, -15)),
    ]
    for name, fn in attempts:
        try:
            out = fn(blob)
            if expected_size and len(out) != expected_size:
                return out, name + f"-size-{len(out)}", None
            return out, name, None
        except Exception as exc:
            errors.append(name + ": " + str(exc))
    return None, "unknown", " | ".join(errors) if errors else "decompress failed"


def compress_candidates(payload: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    # Try Zstandard first because CodeX RDR1 resource writer uses Zstandard.
    for level in [22, 21, 20, 19, 18, 15, 12, 9, 6, 3, 1]:
        try:
            out.append((f"zstd-level-{level}", zstd_compress(payload, level)))
        except Exception as exc:
            out.append((f"zstd-unavailable-{level}:{exc}", b""))
            break
    for level in range(9, -1, -1):
        out.append((f"zlib-level-{level}", zlib.compress(payload, level)))
    # Raw deflate candidates.
    for level in range(9, -1, -1):
        co = zlib.compressobj(level, zlib.DEFLATED, -15)
        out.append((f"raw-deflate-level-{level}", co.compress(payload) + co.flush()))
    return [(name, data) for name, data in out if data]


def fit_compressed_payload(compressed_candidates: list[tuple[str, bytes]], target_size: int) -> tuple[str, bytes, dict] | None:
    """Pick a candidate that can be fit exactly to target_size.

    For Zstandard candidates, prefer exact size or standards-compliant skippable
    padding. For zlib/raw fallback, exact size or zero padding is used only if
    our own validator can reopen it later.
    """
    attempts = []
    for cname, comp in compressed_candidates:
        if len(comp) > target_size:
            attempts.append({"codec": cname, "size": len(comp), "fit": "too-large"})
            continue
        pad = target_size - len(comp)
        if pad == 0:
            attempts.append({"codec": cname, "size": len(comp), "fit": "exact"})
            return cname, comp, {"fit_mode": "exact", "codec": cname, "pad": 0, "attempts": attempts}
        if cname.startswith("zstd") and pad >= 8:
            try:
                final = comp + _zstd_skippable_padding(pad)
                attempts.append({"codec": cname, "size": len(comp), "pad": pad, "fit": "zstd-skippable"})
                return cname, final, {"fit_mode": "zstd-skippable-padding", "codec": cname, "pad": pad, "attempts": attempts}
            except Exception as exc:
                attempts.append({"codec": cname, "size": len(comp), "pad": pad, "fit": "pad-failed", "error": str(exc)})
        else:
            attempts.append({"codec": cname, "size": len(comp), "pad": pad, "fit": "candidate-pad-not-preferred"})
    return None


def u32_hits(data: bytes, values: set[int]) -> list[dict]:
    # Backward-compatible u32-le hit helper used by older reports.
    return int_hits(data, values, formats=["u32le"])


INT_FORMATS = {
    "u8": (1, "B", "u8"),
    "u16le": (2, "<H", "u16le"),
    "u16be": (2, ">H", "u16be"),
    "u32le": (4, "<I", "u32le"),
    "u32be": (4, ">I", "u32be"),
    "i16le": (2, "<h", "i16le"),
    "i32le": (4, "<i", "i32le"),
}


def int_hits(data: bytes, values: set[int], formats: list[str] | None = None) -> list[dict]:
    hits: list[dict] = []
    fmts = formats or ["u8", "u16le", "u16be", "u32le", "u32be", "i16le", "i32le"]
    for fmt_name in fmts:
        width, fmt, label = INT_FORMATS[fmt_name]
        if len(data) < width:
            continue
        for off in range(0, len(data) - width + 1):
            try:
                v = struct.unpack_from(fmt, data, off)[0]
            except struct.error:
                continue
            if v in values:
                hits.append({
                    "offset": off,
                    "hex_offset": f"0x{off:X}",
                    "value": int(v),
                    "format": label,
                    "width": width,
                    "aligned2": off % 2 == 0,
                    "aligned4": off % 4 == 0,
                    "context_hex": data[max(0, off-16):min(len(data), off+width+16)].hex(" ").upper(),
                })
    return hits


def summarize_hits(rows: list[dict]) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        key = str(r.get("format", "unknown"))
        out[key] = out.get(key, 0) + 1
    return out


def _is_digit_byte(b: int | None) -> bool:
    return b is not None and 48 <= b <= 57


def _is_ascii_token_byte(b: int | None) -> bool:
    return b is not None and ((48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122) or b == 95)


def _ascii_boundary_ok(data: bytes, start: int, end: int, boundary: str) -> bool:
    prev_b = data[start - 1] if start > 0 else None
    next_b = data[end] if end < len(data) else None
    if boundary == "digit":
        return (not _is_digit_byte(prev_b)) and (not _is_digit_byte(next_b))
    if boundary == "token":
        return (not _is_ascii_token_byte(prev_b)) and (not _is_ascii_token_byte(next_b))
    raise ValueError(f"unknown ASCII boundary mode: {boundary}")


def ascii_isolated_hits(data: bytes, values: set[int], boundary: str = "token") -> list[dict]:
    """Find standalone ASCII 4-digit vehicle IDs in the decoded payload.

    This is intentionally stricter than integer scanning. It only sees literal
    byte tokens like b"1188" and refuses matches embedded in longer digit
    chains, e.g. b"111888" or b"11880". In the default token mode it also
    refuses matches embedded in ASCII words/identifiers.
    """
    needles = {str(v).encode("ascii"): v for v in sorted(values) if 1000 <= v <= 9999}
    hits: list[dict] = []
    for needle, value in needles.items():
        start = 0
        while True:
            off = data.find(needle, start)
            if off < 0:
                break
            end = off + len(needle)
            if _ascii_boundary_ok(data, off, end, boundary):
                prev_b = data[off - 1] if off > 0 else None
                next_b = data[end] if end < len(data) else None
                hits.append({
                    "offset": off,
                    "hex_offset": f"0x{off:X}",
                    "value": value,
                    "format": f"ascii4-isolated-{boundary}",
                    "width": 4,
                    "prev_byte_hex": "BOF" if prev_b is None else f"0x{prev_b:02X}",
                    "next_byte_hex": "EOF" if next_b is None else f"0x{next_b:02X}",
                    "context_ascii_safe": _safe_ascii_context(data[max(0, off-24):min(len(data), end+24)]),
                    "context_hex": data[max(0, off-16):min(len(data), end+16)].hex(" ").upper(),
                })
            start = off + 1
    hits.sort(key=lambda r: int(r["offset"]))
    return hits


def _safe_ascii_context(blob: bytes) -> str:
    chars = []
    for b in blob:
        if 32 <= b <= 126:
            chars.append(chr(b))
        elif b == 0:
            chars.append("\\0")
        else:
            chars.append(".")
    return "".join(chars)


def range_mapping(old_low: int, old_high: int, new_low: int, new_high: int, strategy: str) -> dict[int, int]:
    if strategy == "alternating":
        return {v: (new_low if ((v - old_low) % 2 == 0) else new_high) for v in range(old_low, old_high + 1)}
    if strategy == "low":
        return {v: new_low for v in range(old_low, old_high + 1)}
    if strategy == "high":
        return {v: new_high for v in range(old_low, old_high + 1)}
    raise ValueError(f"unknown range mapping strategy: {strategy}")


def patch_ascii_isolated_range(payload: bytes, old_low: int, old_high: int, new_low: int, new_high: int, boundary: str = "token", strategy: str = "alternating") -> tuple[bytes, list[dict], str]:
    mapping = range_mapping(old_low, old_high, new_low, new_high, strategy)
    values = set(mapping.keys())
    hits = ascii_isolated_hits(payload, values, boundary=boundary)
    buf = bytearray(payload)
    replacements: list[dict] = []
    for h in hits:
        off = int(h["offset"])
        old = int(h["value"])
        new = int(mapping[old])
        old_bytes = f"{old:04d}".encode("ascii")
        new_bytes = f"{new:04d}".encode("ascii")
        if len(old_bytes) != 4 or len(new_bytes) != 4:
            continue
        if bytes(buf[off:off+4]) != old_bytes:
            continue
        # Re-check boundaries against the current buffer before writing. This
        # avoids a previous replacement changing the safety conditions around a
        # later candidate.
        if not _ascii_boundary_ok(bytes(buf), off, off + 4, boundary):
            continue
        buf[off:off+4] = new_bytes
        row = dict(h)
        row.update({
            "old": old,
            "new": new,
            "old_ascii": f"{old:04d}",
            "new_ascii": f"{new:04d}",
            "boundary": boundary,
            "range_mapping_strategy": strategy,
            "safety": "standalone 4-digit ASCII token only; no integer/opcode/hash replacement",
        })
        replacements.append(row)
    return bytes(buf), replacements, f"ascii4-isolated-{boundary}-{strategy}"


def patch_mapping_by_format(payload: bytes, mapping: dict[int, int], fmt_name: str) -> tuple[bytes, list[dict]]:
    if fmt_name not in INT_FORMATS:
        raise ValueError(f"unsupported integer format: {fmt_name}")
    width, fmt, label = INT_FORMATS[fmt_name]
    unsigned = fmt[-1] in ("B", "H", "I")
    buf = bytearray(payload)
    replacements: list[dict] = []
    for off in range(0, len(buf) - width + 1):
        v = struct.unpack_from(fmt, buf, off)[0]
        if v in mapping:
            nv = mapping[int(v)]
            if unsigned and nv < 0:
                continue
            try:
                struct.pack_into(fmt, buf, off, nv)
            except struct.error:
                continue
            replacements.append({
                "offset": off,
                "hex_offset": f"0x{off:X}",
                "old": int(v),
                "new": int(nv),
                "format": label,
                "width": width,
                "aligned2": off % 2 == 0,
                "aligned4": off % 4 == 0,
            })
    return bytes(buf), replacements


def patch_bounds(payload: bytes, old_low: int, old_high: int, new_low: int, new_high: int, int_format: str = "auto") -> tuple[bytes, list[dict], str]:
    mapping = {old_low: new_low, old_high: new_high}
    formats = ["u32le", "u16le", "u32be", "u16be", "i32le", "i16le"] if int_format == "auto" else [int_format]
    attempts: list[dict] = []
    for fmt in formats:
        patched, reps = patch_mapping_by_format(payload, mapping, fmt)
        attempts.append({"format": fmt, "replacements": len(reps)})
        if reps:
            for r in reps:
                r["auto_attempts"] = attempts
            return patched, reps, fmt
    return payload, [], int_format


def patch_all_range_split(payload: bytes, old_low: int, old_high: int, new_low: int, new_high: int, int_format: str = "auto") -> tuple[bytes, list[dict], str]:
    mapping = {v: (new_low if ((v - old_low) % 2 == 0) else new_high) for v in range(old_low, old_high + 1)}
    formats = ["u32le", "u16le", "u32be", "u16be", "i32le", "i16le"] if int_format == "auto" else [int_format]
    attempts: list[dict] = []
    for fmt in formats:
        patched, reps = patch_mapping_by_format(payload, mapping, fmt)
        attempts.append({"format": fmt, "replacements": len(reps)})
        if reps:
            for r in reps:
                r["auto_attempts"] = attempts
            return patched, reps, fmt
    return payload, [], int_format


def patch_index_bounds(payload: bytes, base_id: int, old_low: int, old_high: int, new_low: int, new_high: int, int_format: str = "auto") -> tuple[bytes, list[dict], str]:
    # Some scripts store vehicle-list indexes instead of absolute actor IDs.
    # For trainer actor IDs, index = actor_id - 1177. So 1183..1197 becomes 6..20;
    # 1193..1194 becomes 16..17. This mode is intentionally explicit because
    # tiny constants can be common in script bytecode.
    old_index_low = old_low - base_id
    old_index_high = old_high - base_id
    new_index_low = new_low - base_id
    new_index_high = new_high - base_id
    mapping = {old_index_low: new_index_low, old_index_high: new_index_high}
    formats = ["u8", "u16le", "u32le"] if int_format == "auto" else [int_format]
    attempts: list[dict] = []
    for fmt in formats:
        patched, reps = patch_mapping_by_format(payload, mapping, fmt)
        attempts.append({"format": fmt, "replacements": len(reps)})
        if reps:
            for r in reps:
                r["base_id"] = base_id
                r["old_actor_range"] = f"{old_low}-{old_high}"
                r["new_actor_range"] = f"{new_low}-{new_high}"
                r["old_index_range"] = f"{old_index_low}-{old_index_high}"
                r["new_index_range"] = f"{new_index_low}-{new_index_high}"
                r["auto_attempts"] = attempts
            return patched, reps, fmt
    return payload, [], int_format



def count_int_values_by_format(data: bytes, values: set[int], formats: list[str] | None = None) -> dict:
    """Return per-format/per-value counts for exact binary integer hits.

    This is a reporting helper, not proof of control flow. It is useful here
    because the decoded WSC has no literal ASCII "1188" style tokens; the
    values appear as compact binary constants instead.
    """
    hits = int_hits(data, values, formats=formats)
    out: dict[str, dict[str, int]] = {}
    for h in hits:
        fmt = str(h.get("format", "unknown"))
        val = str(h.get("value", ""))
        out.setdefault(fmt, {})[val] = out.setdefault(fmt, {}).get(val, 0) + 1
    return {fmt: dict(sorted(vals.items(), key=lambda kv: int(kv[0]))) for fmt, vals in sorted(out.items())}


def undesired_values(old_low: int, old_high: int, new_low: int, new_high: int) -> set[int]:
    desired = set(range(new_low, new_high + 1))
    return {v for v in range(old_low, old_high + 1) if v not in desired}


def patch_binary_range(payload: bytes, old_low: int, old_high: int, new_low: int, new_high: int, int_format: str = "u16be", strategy: str = "alternating", patch_existing_desired: bool = False) -> tuple[bytes, list[dict], str]:
    """Patch exact binary actor IDs in a decoded WSC payload.

    This mode intentionally does not perform byte-substring or ASCII replacement.
    It only replaces complete integer operands in the selected storage format
    (default u16be, because the decoded wagon thief scan showed the strongest
    actor-ID signal there). Values already in the desired target range may be
    left untouched unless patch_existing_desired is explicitly requested.
    """
    mapping = range_mapping(old_low, old_high, new_low, new_high, strategy)
    if not patch_existing_desired:
        desired = set(range(new_low, new_high + 1))
        mapping = {k: v for k, v in mapping.items() if k not in desired}
    patched, reps = patch_mapping_by_format(payload, mapping, int_format)
    for r in reps:
        r["safety"] = "exact decoded binary integer only; no ASCII substring, no longer digit-chain replacement"
        r["range_mapping_strategy"] = strategy
        r["patch_existing_desired"] = patch_existing_desired
        r["note"] = "Default format u16be matches the strongest actor-ID signal from decode-scan. Review replacements CSV before shipping."
    return patched, reps, f"binary-range-{int_format}-{strategy}"

def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Union fieldnames so rows with extra metadata do not crash CSV writing.
    fields: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def decode_wsc_resource(data: bytes, root: Path, rdr_exe: str | None = None) -> tuple[bytes | None, dict, bytes | None]:
    rsc = parse_rsc_header(data)
    report: dict = {"rsc": rsc}
    if not rsc.get("is_rsc") or rsc.get("resource_type") != 2:
        report["error"] = "not an RSC type-2 script resource"
        return None, report, None
    key, attempts = get_aes_key(root, rdr_exe)
    report["aes_key_attempts"] = attempts
    if key is None:
        report["error"] = "no AES key"
        return None, report, None
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
    return decoded, report, decrypted_compressed


def analyze(args: argparse.Namespace) -> int:
    path = Path(args.input)
    data = path.read_bytes()
    rsc = parse_rsc_header(data)
    values = set(range(args.old_low, args.old_high + 1)) | {args.new_low, args.new_high}
    index_values = {args.old_low - args.base_id, args.old_high - args.base_id, args.new_low - args.base_id, args.new_high - args.base_id}
    raw_hits = int_hits(data, values)
    payload = data[16:] if rsc.get("is_rsc") else data
    payload_hits = int_hits(payload, values)
    raw_index_hits = int_hits(data, index_values, formats=["u8", "u16le", "u32le"])
    payload_index_hits = int_hits(payload, index_values, formats=["u8", "u16le", "u32le"])
    report = {
        "input": str(path),
        "size": len(data),
        "sha256": sha256(data),
        "rsc": rsc,
        "scan_values_actor_ids": sorted(values),
        "scan_values_index_bounds": sorted(index_values),
        "raw_integer_hits": len(raw_hits),
        "raw_integer_hits_by_format": summarize_hits(raw_hits),
        "payload_region_integer_hits": len(payload_hits),
        "payload_region_integer_hits_by_format": summarize_hits(payload_hits),
        "raw_index_hits": len(raw_index_hits),
        "payload_index_hits": len(payload_index_hits),
        "note": "For RSC85 type-2 WSC, useful IDs are usually inside AES/decompressed payload, not raw bytes. Use decode-scan for the real payload.",
    }
    out = Path(args.out) if args.out else Path("logs/ambush_cartruck_wsc/analyze")
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / (path.name + ".raw_integer_hits.csv"), raw_hits)
    write_csv(out / (path.name + ".payload_region_integer_hits.csv"), payload_hits)
    write_csv(out / (path.name + ".raw_index_hits.csv"), raw_index_hits)
    write_csv(out / (path.name + ".payload_region_index_hits.csv"), payload_index_hits)
    (out / (path.name + ".analyze.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def decode_scan(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    path = Path(args.input)
    data = path.read_bytes()
    decoded, dec_report, decrypted_compressed = decode_wsc_resource(data, root, args.rdr_exe)
    values = set(range(args.old_low, args.old_high + 1)) | {args.new_low, args.new_high}
    index_values = set(range(args.old_low - args.base_id, args.old_high - args.base_id + 1)) | {args.new_low - args.base_id, args.new_high - args.base_id}
    out = Path(args.out) if args.out else Path("logs/ambush_cartruck_wsc/decode_scan")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "input": str(path),
        "input_size": len(data),
        "input_sha256": sha256(data),
        **dec_report,
        "actor_id_scan_values": sorted(values),
        "index_scan_values": sorted(index_values),
    }
    if decoded is None:
        report["status"] = "blocked-decode-failed"
    else:
        actor_hits = int_hits(decoded, values)
        index_hits = int_hits(decoded, index_values, formats=["u8", "u16le", "u32le", "i16le", "i32le"])
        ascii_digit_hits = ascii_isolated_hits(decoded, values, boundary="digit")
        ascii_token_hits = ascii_isolated_hits(decoded, values, boundary="token")
        report.update({
            "status": "decoded",
            "decoded_payload_sha256": sha256(decoded),
            "actor_id_hits": len(actor_hits),
            "actor_id_hits_by_format": summarize_hits(actor_hits),
            "actor_id_counts_by_format_value": count_int_values_by_format(decoded, values),
            "undesired_actor_id_counts_by_format_value": count_int_values_by_format(decoded, undesired_values(args.old_low, args.old_high, args.new_low, args.new_high)),
            "isolated_ascii4_digit_boundary_hits": len(ascii_digit_hits),
            "isolated_ascii4_token_boundary_hits": len(ascii_token_hits),
            "index_hits": len(index_hits),
            "index_hits_by_format": summarize_hits(index_hits),
            "decoded_payload_bin": str(out / (path.name + ".decoded_payload.bin")),
            "integer_hits_csv": str(out / (path.name + ".actor_id_hits.csv")),
            "isolated_ascii4_digit_csv": str(out / (path.name + ".isolated_ascii4_digit_hits.csv")),
            "isolated_ascii4_token_csv": str(out / (path.name + ".isolated_ascii4_token_hits.csv")),
            "index_hits_csv": str(out / (path.name + ".index_hits.csv")),
        })
        (out / (path.name + ".decoded_payload.bin")).write_bytes(decoded)
        if decrypted_compressed is not None:
            (out / (path.name + ".decrypted_compressed.bin")).write_bytes(decrypted_compressed)
        write_csv(out / (path.name + ".actor_id_hits.csv"), actor_hits)
        write_csv(out / (path.name + ".isolated_ascii4_digit_hits.csv"), ascii_digit_hits)
        write_csv(out / (path.name + ".isolated_ascii4_token_hits.csv"), ascii_token_hits)
        write_csv(out / (path.name + ".index_hits.csv"), index_hits)
    (out / (path.name + ".decode_scan.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "decoded" else 2


def patch(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    in_path = Path(args.input)
    out_path = Path(args.out)
    data = in_path.read_bytes()
    rsc = parse_rsc_header(data)
    report: dict = {
        "input": str(in_path),
        "input_size": len(data),
        "input_sha256": sha256(data),
        "rsc": rsc,
        "mode": args.mode,
        "old_range": [args.old_low, args.old_high],
        "new_range": [args.new_low, args.new_high],
    }

    if not rsc.get("is_rsc") or rsc.get("resource_type") != 2:
        raise SystemExit("This tool expects an RSC85/RSC05 type-2 WSC script resource.")

    key, attempts = get_aes_key(root, args.rdr_exe)
    report["aes_key_attempts"] = attempts
    if key is None:
        report["status"] = "blocked-no-aes-key"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        raise SystemExit(
            "Blocked: could not find RDR1 AES key in rdr.exe. Place Code_RED next to rdr.exe or set CODERED_RDR_EXE."
        )

    header = data[:16]
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
    if decoded is None:
        report["status"] = "blocked-decompress-failed"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        raise SystemExit("Blocked: AES key found, but script payload did not decompress with zstd/zlib/raw-deflate.")

    actor_values = set(range(args.old_low, args.old_high + 1))
    index_values = set(range(args.old_low - args.base_id, args.old_high - args.base_id + 1))
    before_hits = int_hits(decoded, actor_values)
    before_ascii_digit_hits = ascii_isolated_hits(decoded, actor_values, boundary="digit")
    before_ascii_token_hits = ascii_isolated_hits(decoded, actor_values, boundary="token")
    before_index_hits = int_hits(decoded, index_values, formats=["u8", "u16le", "u32le", "i16le", "i32le"])
    if args.mode == "bounds":
        patched, replacements, used_format = patch_bounds(decoded, args.old_low, args.old_high, args.new_low, args.new_high, args.int_format)
    elif args.mode == "all-alternating":
        patched, replacements, used_format = patch_all_range_split(decoded, args.old_low, args.old_high, args.new_low, args.new_high, args.int_format)
    elif args.mode == "ascii-isolated-range":
        patched, replacements, used_format = patch_ascii_isolated_range(decoded, args.old_low, args.old_high, args.new_low, args.new_high, boundary=args.ascii_boundary, strategy=args.range_map)
    elif args.mode == "binary-range":
        fmt = "u16be" if args.int_format == "auto" else args.int_format
        patched, replacements, used_format = patch_binary_range(decoded, args.old_low, args.old_high, args.new_low, args.new_high, fmt, strategy=args.range_map, patch_existing_desired=args.patch_existing_desired)
    elif args.mode == "index-bounds":
        patched, replacements, used_format = patch_index_bounds(decoded, args.base_id, args.old_low, args.old_high, args.new_low, args.new_high, args.int_format)
    else:
        raise SystemExit(f"Unknown patch mode: {args.mode}")
    after_hits = int_hits(patched, actor_values)
    after_ascii_digit_hits = ascii_isolated_hits(patched, actor_values, boundary="digit")
    after_ascii_token_hits = ascii_isolated_hits(patched, actor_values, boundary="token")
    after_index_hits = int_hits(patched, index_values, formats=["u8", "u16le", "u32le", "i16le", "i32le"])

    report["patch"] = {
        "before_old_range_hits": len(before_hits),
        "before_old_range_hits_by_format": summarize_hits(before_hits),
        "before_old_range_counts_by_format_value": count_int_values_by_format(decoded, actor_values),
        "before_undesired_old_counts_by_format_value": count_int_values_by_format(decoded, undesired_values(args.old_low, args.old_high, args.new_low, args.new_high)),
        "before_isolated_ascii4_digit_hits": len(before_ascii_digit_hits),
        "before_isolated_ascii4_token_hits": len(before_ascii_token_hits),
        "before_index_range_hits": len(before_index_hits),
        "before_index_range_hits_by_format": summarize_hits(before_index_hits),
        "replacements": len(replacements),
        "used_integer_format": used_format,
        "after_old_range_hits": len(after_hits),
        "after_old_range_hits_by_format": summarize_hits(after_hits),
        "after_old_range_counts_by_format_value": count_int_values_by_format(patched, actor_values),
        "after_undesired_old_counts_by_format_value": count_int_values_by_format(patched, undesired_values(args.old_low, args.old_high, args.new_low, args.new_high)),
        "after_isolated_ascii4_digit_hits": len(after_ascii_digit_hits),
        "after_isolated_ascii4_token_hits": len(after_ascii_token_hits),
        "after_index_range_hits": len(after_index_hits),
        "after_index_range_hits_by_format": summarize_hits(after_index_hits),
        "bounds_mapping": {str(args.old_low): args.new_low, str(args.old_high): args.new_high},
        "index_bounds_mapping": {str(args.old_low - args.base_id): args.new_low - args.base_id, str(args.old_high - args.base_id): args.new_high - args.base_id},
        "base_id": args.base_id,
        "cartruck_ids": {"Truck01": 1193, "Car01": 1194},
        "ascii_boundary": getattr(args, "ascii_boundary", None),
        "range_map": getattr(args, "range_map", None),
    }

    if not replacements and not args.allow_noop:
        report["status"] = "blocked-no-replacements"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_actor_hits.csv"), before_hits)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_ascii4_digit_hits.csv"), before_ascii_digit_hits)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_ascii4_token_hits.csv"), before_ascii_token_hits)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_index_hits.csv"), before_index_hits)
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        raise SystemExit("Blocked: decoded payload had no matching IDs to patch. Use --allow-noop only for testing.")

    if getattr(args, "preview_only", False):
        report["status"] = "preview-only"
        report["preview_note"] = "No WSC written. Review replacements CSV; rerun without --preview-only to patch."
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_actor_hits.csv"), before_hits)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_ascii4_digit_hits.csv"), before_ascii_digit_hits)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_ascii4_token_hits.csv"), before_ascii_token_hits)
        write_csv(out_path.with_suffix(out_path.suffix + ".before_index_hits.csv"), before_index_hits)
        write_csv(out_path.with_suffix(out_path.suffix + ".replacements.csv"), replacements)
        (out_path.with_suffix(out_path.suffix + ".decoded_payload_before.bin")).write_bytes(decoded)
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    original_payload_size = len(encrypted_payload)
    candidates = compress_candidates(patched)
    fit = fit_compressed_payload(candidates, original_payload_size)
    if fit is None:
        report["status"] = "blocked-compressed-output-too-large"
        smallest = min(candidates, key=lambda x: len(x[1])) if candidates else ("none", b"")
        report["smallest_compressed_candidate"] = {"codec": smallest[0], "size": len(smallest[1]), "max_allowed": original_payload_size}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        raise SystemExit("Blocked: recompressed payload does not fit original WSC payload size.")

    cname, padded, fit_report = fit
    encrypted_new = aes_crypt_block(padded, key, decrypt=False)
    output_data = header + encrypted_new

    # Validate by decrypting and decompressing our own output.
    check_dec = aes_crypt_block(output_data[16:], key, decrypt=True)
    check_payload, check_codec, check_err = try_decompress(check_dec, expected)
    report["repack"] = {
        "compress_codec": cname,
        "fit_report": fit_report,
        "compressed_or_padded_size": len(padded),
        "padded_encrypted_payload_size": len(encrypted_new),
        "output_size": len(output_data),
        "output_sha256": sha256(output_data),
        "validate_codec": check_codec,
        "validate_error": check_err,
        "validate_decoded_size": len(check_payload) if check_payload is not None else 0,
        "validate_ok": check_payload == patched,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(output_data)
    write_csv(out_path.with_suffix(out_path.suffix + ".before_actor_hits.csv"), before_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".before_ascii4_digit_hits.csv"), before_ascii_digit_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".before_ascii4_token_hits.csv"), before_ascii_token_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".before_index_hits.csv"), before_index_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".replacements.csv"), replacements)
    write_csv(out_path.with_suffix(out_path.suffix + ".after_actor_hits.csv"), after_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".after_ascii4_digit_hits.csv"), after_ascii_digit_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".after_ascii4_token_hits.csv"), after_ascii_token_hits)
    write_csv(out_path.with_suffix(out_path.suffix + ".after_index_hits.csv"), after_index_hits)
    (out_path.with_suffix(out_path.suffix + ".decoded_payload_before.bin")).write_bytes(decoded)
    (out_path.with_suffix(out_path.suffix + ".decoded_payload_after.bin")).write_bytes(patched)
    report["status"] = "patched" if report["repack"]["validate_ok"] else "patched-validation-warning"
    report["output"] = str(out_path)
    (out_path.with_suffix(out_path.suffix + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["repack"]["validate_ok"] else 2


def status(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    key, attempts = get_aes_key(root, args.rdr_exe)
    out = {
        "tool": "Code RED Roadside Ambush 1177-1188 to Car/Truck WSC Patcher",
        "version": "1.4",
        "cwd": str(Path.cwd()),
        "repo_root_guess": str(root),
        "target_default": "imports\\event_roadside_ambush.wsc",
        "patch_default": "binary-range 1177..1188 -> alternating 1193/1194 using u16be",
        "extra_modes": ["decode-scan", "bounds", "binary-range", "all-alternating", "ascii-isolated-range", "index-bounds"],
        "cartruck_ids": {"Truck01": 1193, "Car01": 1194},
        "aes_key_available": key is not None,
        "aes_key_attempts": attempts,
        "needs_python_package": "cryptography and zstandard when patching/decrypting RSC85 scripts",
    }
    print(json.dumps(out, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Patch event_roadside_ambush WSC vehicle ID range to Truck01/Car01.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status")
    p.add_argument("--rdr-exe")
    p.set_defaults(func=status)

    p = sub.add_parser("analyze")
    p.add_argument("--input", default="imports/event_roadside_ambush.wsc")
    p.add_argument("--out", default="logs/ambush_cartruck_wsc/analyze")
    p.add_argument("--old-low", type=int, default=DEFAULT_OLD_LOW)
    p.add_argument("--old-high", type=int, default=DEFAULT_OLD_HIGH)
    p.add_argument("--new-low", type=int, default=DEFAULT_NEW_LOW)
    p.add_argument("--new-high", type=int, default=DEFAULT_NEW_HIGH)
    p.add_argument("--base-id", type=int, default=1177)
    p.set_defaults(func=analyze)

    p = sub.add_parser("decode-scan")
    p.add_argument("--input", default="imports/event_roadside_ambush.wsc")
    p.add_argument("--out", default="logs/ambush_cartruck_wsc/decode_scan")
    p.add_argument("--old-low", type=int, default=DEFAULT_OLD_LOW)
    p.add_argument("--old-high", type=int, default=DEFAULT_OLD_HIGH)
    p.add_argument("--new-low", type=int, default=DEFAULT_NEW_LOW)
    p.add_argument("--new-high", type=int, default=DEFAULT_NEW_HIGH)
    p.add_argument("--base-id", type=int, default=1177)
    p.add_argument("--rdr-exe")
    p.set_defaults(func=decode_scan)

    p = sub.add_parser("patch")
    p.add_argument("--input", default="imports/event_roadside_ambush.wsc")
    p.add_argument("--out", default="patches/event_roadside_ambush_1177_1188_to_1193_1194.wsc")
    p.add_argument("--old-low", type=int, default=DEFAULT_OLD_LOW)
    p.add_argument("--old-high", type=int, default=DEFAULT_OLD_HIGH)
    p.add_argument("--new-low", type=int, default=DEFAULT_NEW_LOW)
    p.add_argument("--new-high", type=int, default=DEFAULT_NEW_HIGH)
    p.add_argument("--mode", choices=["bounds", "binary-range", "all-alternating", "ascii-isolated-range", "index-bounds"], default="binary-range",
                   help="bounds patches actor-ID bounds 1183->1193 and 1197->1194. binary-range remaps exact decoded binary actor IDs in range, defaulting to u16be. all-alternating remaps every decoded integer actor ID in range using auto format. ascii-isolated-range only patches standalone 4-digit ASCII tokens 1183..1197. index-bounds patches list indexes 6->16 and 20->17 when scripts store selected vehicle indexes instead of actor IDs.")
    p.add_argument("--int-format", choices=["auto", "u32le", "u16le", "u16be", "u32be", "i16le", "i32le", "u8"], default="u16be",
                   help="Integer storage format to patch. auto tries u32le first, then u16le, then big-endian/signed fallbacks.")
    p.add_argument("--base-id", type=int, default=1177, help="Trainer vehicle base ID used by index-bounds mode. Actor ID = menu index + base ID.")
    p.add_argument("--ascii-boundary", choices=["token", "digit"], default="token", help="Boundary rule for ascii-isolated-range. token refuses matches inside letters/digits/underscore; digit only refuses longer digit chains.")
    p.add_argument("--range-map", choices=["alternating", "low", "high"], default="alternating", help="Mapping for ascii-isolated-range and binary-range. alternating maps 1183->1193, 1184->1194, etc.; low maps all to 1193; high maps all to 1194.")
    p.add_argument("--patch-existing-desired", action="store_true", help="For binary-range only: also rewrite values already in the desired target range 1193-1194. Default leaves them untouched.")
    p.add_argument("--preview-only", action="store_true", help="Decode and list exact binary replacement candidates without writing a patched WSC.")
    p.add_argument("--rdr-exe")
    p.add_argument("--allow-noop", action="store_true")
    p.set_defaults(func=patch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
