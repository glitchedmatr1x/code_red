#!/usr/bin/env python3
"""Code RED RDR1 Resource Lab.

Drop-in read-first RDR1 resource helper inspired by CodeX.Games.RDR1 format research.
It is intentionally conservative:
- Broad view/analyze/export support for RDR1 resource files.
- Editing is staged into replacement files/patch folders.
- Compressed RSC resources are unpacked/repacked only when zstandard support is available.
- Dangerous structural edits are not performed automatically.

This file has no dependency on CodeX. It can optionally call Code RED's existing RPF tools
when it is placed inside a Code RED root.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import zstandard as zstd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "logs" / "rdr1_resource_lab"

RSC_MAGICS = {
    b"RSC\x05": "RSC05",
    b"RSC\x06": "RSC06",
    b"RSC\x85": "RSC85",
    b"RSC\x86": "RSC86",
}

TEXT_EXTENSIONS = {
    ".tr", ".csv", ".cfg", ".refgroup", ".fxlist", ".modellist", ".emitlist",
    ".fullfxlist", ".shaderlist", ".texlist", ".ptxlist", ".xlist", ".list",
    ".expl", ".vehsim", ".vehstuck", ".env", ".hud", ".traffic", ".mtl",
    ".weap", ".fx", ".fxm", ".todlight", ".ppp", ".rmptx", ".tune",
    ".textune", ".xml", ".meta", ".txt",
}

RESOURCE_EXTENSIONS = {
    ".wgd": "Gringo Dictionary",
    ".wtd": "Texture Dictionary",
    ".wst": "String Table",
    ".sst": "String Table",
    ".strtbl": "String Table",
    ".wfd": "Frag Drawable",
    ".wvd": "Visual Dictionary",
    ".wft": "Fragment",
    ".wsi": "Sector Info",
    ".wcg": "Combat Cover Grid",
    ".wsg": "Sector Grass",
    ".wsp": "Speed Tree",
    ".wtb": "Terrain Bounds",
    ".wat": "Action Tree",
    ".wcdt": "Clip Dictionary",
    ".wedt": "Expression Dictionary",
    ".wpfl": "Particle Effects Library",
    ".wnm": "Navmesh",
    ".wsf": "Scaleform/Flash UI",
    ".wbd": "Bounds Dictionary",
    ".was": "Animation Set",
    ".fonttex": "Font Data",
}

SEMANTIC_EDIT_CANDIDATES = {
    ".wtd", ".wst", ".sst", ".strtbl", ".wfd", ".wvd",
}

VIEW_ANALYZE_ONLY_FIRST = {
    ".wgd", ".wft", ".wsi", ".wcg", ".wsg", ".wsp", ".wtb", ".wat",
    ".wcdt", ".wedt", ".wpfl", ".wnm", ".wsf", ".wbd", ".was", ".fonttex",
}

ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
UTF16LE_RE = re.compile((rb"(?:[\x20-\x7e]\x00){4,}"))


@dataclass
class RscInfo:
    magic: str
    resource_type: int
    flag1: int
    flag2: int | None
    header_size: int
    compressed_size: int
    payload_sha1: str
    virtual_size: int | None = None
    physical_size: int | None = None
    expected_unpacked_size: int | None = None
    payload_unpacked_size: int | None = None
    compression: str = "unknown"


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def safe_out_name(path: Path) -> str:
    name = path.name.replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        return int(value, 16 if value.lower().startswith("0x") else 10)
    raise TypeError(f"Cannot parse int from {value!r}")


def _u32(value: int | None) -> int:
    return 0 if value is None else (value & 0xFFFFFFFF)


def _rsc05_sizes(flag1: int) -> tuple[int, int]:
    f1 = _u32(flag1)
    v_shift = ((f1 >> 11) & 0xF) + 8
    p_shift = ((f1 >> 26) & 0xF) + 8
    virtual_size = (f1 & 0x7FF) << v_shift
    physical_size = ((f1 >> 15) & 0x7FF) << p_shift
    return virtual_size, physical_size


def _rsc85_sizes(flag2: int | None) -> tuple[int | None, int | None]:
    if flag2 is None:
        return None, None
    f2 = _u32(flag2)
    virtual_size = (f2 & 0x3FFF) << 12
    physical_size = ((f2 >> 14) & 0x3FFF) << 12
    return virtual_size, physical_size


def expected_rsc_unpacked_size(info: RscInfo | None) -> int | None:
    if info is None:
        return None
    if info.expected_unpacked_size and info.expected_unpacked_size > 0:
        return info.expected_unpacked_size
    parts = [v for v in (info.virtual_size, info.physical_size) if v is not None and v >= 0]
    total = sum(parts)
    return total or None


def detect_rsc(data: bytes) -> RscInfo | None:
    if len(data) < 16:
        return None
    magic_bytes = data[:4]
    magic = RSC_MAGICS.get(magic_bytes)
    if not magic:
        return None
    resource_type = struct.unpack_from("<I", data, 4)[0]
    flag1 = struct.unpack_from("<i", data, 8)[0]
    flag2: int | None = None
    header_size = 12
    if magic in {"RSC85", "RSC86"}:
        flag2 = struct.unpack_from("<i", data, 12)[0]
        header_size = 16
    payload = data[header_size:]
    compression = "zstd" if payload.startswith(b"\x28\xb5\x2f\xfd") else "zlib-or-raw"
    if magic in {"RSC85", "RSC86"}:
        virtual_size, physical_size = _rsc85_sizes(flag2)
    else:
        virtual_size, physical_size = _rsc05_sizes(flag1)
    expected_size = (virtual_size or 0) + (physical_size or 0)
    return RscInfo(
        magic=magic,
        resource_type=resource_type,
        flag1=flag1,
        flag2=flag2,
        header_size=header_size,
        compressed_size=len(payload),
        payload_sha1=sha1(payload),
        virtual_size=virtual_size,
        physical_size=physical_size,
        expected_unpacked_size=expected_size or None,
        compression=compression,
    )


def _zstd_cli() -> str | None:
    return shutil.which("zstd") or shutil.which("zstd.exe")


def zstd_decompress(data: bytes, expected_size: int | None = None) -> bytes:
    if zstd is not None:
        dctx = zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data)
        except Exception as exc:
            # Some RDR1 resource frames omit the decompressed content size.
            # Python-zstandard then needs the expected size from the RSC flags.
            if expected_size and expected_size > 0:
                return dctx.decompress(data, max_output_size=expected_size)
            raise exc
    exe = _zstd_cli()
    if exe:
        with tempfile.TemporaryDirectory(prefix="codered_zstd_") as td:
            src = Path(td) / "in.zst"
            dst = Path(td) / "out.bin"
            src.write_bytes(data)
            proc = subprocess.run([exe, "-q", "-d", "-f", str(src), "-o", str(dst)], capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd failed")
            return dst.read_bytes()
    raise RuntimeError("zstandard support unavailable. Install Python package 'zstandard' or put zstd.exe on PATH.")


def zstd_compress(data: bytes, level: int = 12) -> bytes:
    if zstd is not None:
        return zstd.ZstdCompressor(level=level).compress(data)
    exe = _zstd_cli()
    if exe:
        with tempfile.TemporaryDirectory(prefix="codered_zstd_") as td:
            src = Path(td) / "in.bin"
            dst = Path(td) / "out.zst"
            src.write_bytes(data)
            proc = subprocess.run([exe, "-q", f"-{level}", "-f", str(src), "-o", str(dst)], capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd failed")
            return dst.read_bytes()
    raise RuntimeError("zstandard support unavailable. Install Python package 'zstandard' or put zstd.exe on PATH.")


def try_decompress_payload(payload: bytes, info: RscInfo | None = None) -> tuple[bytes | None, str, str | None]:
    if not payload:
        return b"", "empty", None
    if payload.startswith(b"\x28\xb5\x2f\xfd"):
        try:
            return zstd_decompress(payload, expected_rsc_unpacked_size(info)), "zstd", None
        except Exception as exc:
            return None, "zstd", str(exc)
    attempts = [(-15, "zlib-raw"), (15, "zlib"), (31, "gzip")]
    for wbits, label in attempts:
        try:
            return zlib.decompress(payload, wbits), label, None
        except Exception:
            pass
    return None, "raw-or-unknown", "payload is not recognized as zstd/zlib, or dependency is missing"


def unpack_rsc(data: bytes) -> tuple[RscInfo | None, bytes, dict[str, Any]]:
    info = detect_rsc(data)
    meta: dict[str, Any] = {"input_is_rsc": bool(info)}
    if not info:
        meta["payload_source"] = "raw-file"
        return None, data, meta
    payload = data[info.header_size:]
    unpacked, codec, error = try_decompress_payload(payload, info)
    meta.update({"codec": codec, "decompress_error": error})
    if unpacked is None:
        meta["payload_source"] = "compressed-or-unknown"
        return info, payload, meta
    info.payload_unpacked_size = len(unpacked)
    info.compression = codec
    meta["payload_source"] = "rsc-decompressed"
    return info, unpacked, meta


def repack_rsc(original: bytes, new_payload: bytes, zstd_level: int = 12) -> bytes:
    info = detect_rsc(original)
    if info is None:
        return new_payload
    old_payload = original[info.header_size:]
    if old_payload.startswith(b"\x28\xb5\x2f\xfd"):
        packed = zstd_compress(new_payload, zstd_level)
    else:
        # Keep zlib/deflate files zlib-packed. For unknown payloads, require same-size raw patch.
        unpacked, codec, error = try_decompress_payload(old_payload, info)
        if unpacked is not None and codec.startswith("zlib"):
            packed = zlib.compress(new_payload)
        else:
            if len(new_payload) != len(old_payload):
                raise RuntimeError("Cannot raw-repack unknown RSC payload unless size is unchanged")
            packed = new_payload
    return original[:info.header_size] + packed


def _zstd_skippable_padding(size: int) -> bytes:
    """Return a Zstandard skippable frame of exactly *size* bytes."""
    if size < 0:
        raise ValueError("padding size cannot be negative")
    if size == 0:
        return b""
    if size < 8:
        raise RuntimeError(
            "Cannot exact-pad a zstd resource by fewer than 8 bytes without trailing garbage. "
            "Try a different compression level."
        )
    # 0x184D2A50 is the first valid Zstandard skippable-frame magic.
    return struct.pack("<II", 0x184D2A50, size - 8) + (b"\x00" * (size - 8))


def repack_rsc_fit_size(
    original: bytes,
    new_payload: bytes,
    zstd_level: int = 22,
    target_size: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Repack an RSC and, when possible, keep the full file at target_size.

    For zstd-backed RSC resources this tries several compression levels, then
    appends a standards-compliant zstd skippable frame if the compressed stream is
    smaller than the target. This lets copied-archive patching overwrite the exact
    same byte span without touching RPF table-of-contents sizes.
    """
    if target_size is None:
        target_size = len(original)
    info = detect_rsc(original)
    if info is None:
        if len(new_payload) != target_size:
            raise RuntimeError("Raw files must already match target size for exact-size patching")
        return new_payload, {"fit_mode": "raw-exact", "target_size": target_size}

    old_payload = original[info.header_size:]
    if not old_payload.startswith(b"\x28\xb5\x2f\xfd"):
        final = repack_rsc(original, new_payload, zstd_level)
        if len(final) != target_size:
            raise RuntimeError(
                f"Non-zstd RSC repack produced {len(final)} bytes, not required exact size {target_size}."
            )
        return final, {"fit_mode": "non-zstd-exact", "target_size": target_size}

    levels: list[int] = []
    for level in [zstd_level, 22, 21, 20, 19, 18, 15, 12, 9, 6, 3, 1]:
        if 1 <= int(level) <= 22 and int(level) not in levels:
            levels.append(int(level))

    best: bytes | None = None
    best_level: int | None = None
    attempts: list[dict[str, Any]] = []
    for level in levels:
        packed = zstd_compress(new_payload, level)
        final = original[:info.header_size] + packed
        delta = target_size - len(final)
        attempts.append({"level": level, "size": len(final), "delta_to_target": delta})
        if len(final) == target_size:
            return final, {"fit_mode": "zstd-exact", "level": level, "target_size": target_size, "attempts": attempts}
        if len(final) < target_size and (best is None or len(final) > len(best)):
            best = final
            best_level = level

    if best is None:
        raise RuntimeError(
            f"Repacked RSC is larger than target size {target_size} at all tested zstd levels: {attempts}"
        )
    pad_size = target_size - len(best)
    padded = best + _zstd_skippable_padding(pad_size)
    # Validate the exact-size output before returning it.
    _, verify_payload, verify_meta = unpack_rsc(padded)
    if verify_meta.get("payload_source") != "rsc-decompressed" or verify_payload != new_payload:
        raise RuntimeError(f"Exact-size padded RSC failed validation: {verify_meta}")
    return padded, {
        "fit_mode": "zstd-exact-with-skippable-padding",
        "level": best_level,
        "target_size": target_size,
        "unpadded_size": len(best),
        "skippable_padding_bytes": pad_size,
        "attempts": attempts,
    }


def _read_ascii_cstring(data: bytes, offset: int, max_len: int = 256) -> str | None:
    if offset < 0 or offset >= len(data):
        return None
    end = min(len(data), offset + max_len)
    raw = data[offset:end].split(b"\x00", 1)[0]
    if len(raw) < 3:
        return None
    if not all(32 <= b < 127 for b in raw):
        return None
    text = raw.decode("ascii", errors="replace")
    if not any(ch.isalnum() for ch in text):
        return None
    return text


def extract_referenced_strings(data: bytes, limit: int = 2000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    n = len(data)
    for off in range(0, max(0, n - 3), 4):
        val = struct.unpack_from("<I", data, off)[0]
        if 0x50000000 <= val < 0x50000000 + n:
            target = val - 0x50000000
            space = "virtual"
        elif 0x60000000 <= val < 0x60000000 + n:
            target = val - 0x60000000
            space = "physical"
        else:
            continue
        text = _read_ascii_cstring(data, target)
        if not text:
            continue
        key = (target, text)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "pointer_offset": off,
            "pointer_offset_hex": f"0x{off:X}",
            "pointer_value_hex": f"0x{val:08X}",
            "target_offset": target,
            "target_offset_hex": f"0x{target:X}",
            "target_space": space,
            "text": text,
        })
        if len(rows) >= limit:
            break
    return rows


def extract_strings(data: bytes, limit: int = 2000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for m in ASCII_RE.finditer(data):
        text = m.group(0).decode("ascii", errors="replace")
        key = (m.start(), "ascii", text)
        if key not in seen:
            rows.append({"offset": m.start(), "offset_hex": f"0x{m.start():X}", "encoding": "ascii", "length_bytes": len(m.group(0)), "text": text})
            seen.add(key)
            if len(rows) >= limit:
                return rows
    for m in UTF16LE_RE.finditer(data):
        raw = m.group(0)
        try:
            text = raw.decode("utf-16le", errors="replace")
        except Exception:
            continue
        key = (m.start(), "utf-16le", text)
        if key not in seen:
            rows.append({"offset": m.start(), "offset_hex": f"0x{m.start():X}", "encoding": "utf-16le", "length_bytes": len(raw), "text": text})
            seen.add(key)
            if len(rows) >= limit:
                return rows
    rows.sort(key=lambda r: int(r["offset"]))
    return rows[:limit]


def scan_pointers(data: bytes, limit: int = 4000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = len(data)
    for off in range(0, max(0, n - 3), 4):
        val = struct.unpack_from("<I", data, off)[0]
        if 0x50000000 <= val < 0x50000000 + n:
            rows.append({"offset": off, "offset_hex": f"0x{off:X}", "value_hex": f"0x{val:08X}", "target_offset": val - 0x50000000, "target_space": "virtual"})
        elif 0x60000000 <= val < 0x60000000 + n:
            rows.append({"offset": off, "offset_hex": f"0x{off:X}", "value_hex": f"0x{val:08X}", "target_offset": val - 0x60000000, "target_space": "physical"})
        if len(rows) >= limit:
            break
    return rows


def scan_float32(data: bytes, limit: int = 3000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for off in range(0, max(0, len(data) - 3), 4):
        val = struct.unpack_from("<f", data, off)[0]
        if math.isfinite(val) and ((abs(val) >= 0.001 and abs(val) <= 100000.0) or val == 0.0):
            # Filter common integer/hash noise a bit by requiring sane alignment and not too many zeros.
            if val == 0.0 and len(rows) > 500:
                continue
            rows.append({"offset": off, "offset_hex": f"0x{off:X}", "value": val})
            if len(rows) >= limit:
                break
    return rows


def first_u32s(data: bytes, count: int = 32) -> list[dict[str, Any]]:
    rows = []
    for i in range(min(count, len(data) // 4)):
        off = i * 4
        val = struct.unpack_from("<I", data, off)[0]
        rows.append({"offset": off, "offset_hex": f"0x{off:X}", "u32_hex": f"0x{val:08X}", "u32": val})
    return rows


def classify_extension(path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    return {
        "extension": ext,
        "known_name": RESOURCE_EXTENSIONS.get(ext, "Text/Generic" if ext in TEXT_EXTENSIONS else "Unknown"),
        "semantic_edit_candidate": ext in SEMANTIC_EDIT_CANDIDATES,
        "view_analyze_first": ext in VIEW_ANALYZE_ONLY_FIRST,
        "text_direct_edit": ext in TEXT_EXTENSIONS,
        "safe_binary_patch": ext in RESOURCE_EXTENSIONS or ext not in TEXT_EXTENSIONS,
    }


def analyze_file(path: Path, out_dir: Path | None = None, string_limit: int = 2000) -> dict[str, Any]:
    data = read_bytes(path)
    rsc, payload, unpack_meta = unpack_rsc(data)
    ext_info = classify_extension(path)
    strings = extract_strings(payload, limit=string_limit)
    referenced_strings = extract_referenced_strings(payload, limit=string_limit)
    pointers = scan_pointers(payload)
    floats = scan_float32(payload)
    summary: dict[str, Any] = {
        "file": str(path),
        "name": path.name,
        "size": len(data),
        "sha1": sha1(data),
        **ext_info,
        "rsc": asdict(rsc) if rsc else None,
        "payload": {
            "source": unpack_meta.get("payload_source"),
            "codec": unpack_meta.get("codec"),
            "decompress_error": unpack_meta.get("decompress_error"),
            "size": len(payload),
            "sha1": sha1(payload),
        },
        "counts": {
            "strings": len(strings),
            "referenced_strings": len(referenced_strings),
            "pointer_candidates": len(pointers),
            "float_candidates": len(floats),
        },
        "first_u32s": first_u32s(payload),
        "sample_strings": strings[:50],
        "sample_referenced_strings": referenced_strings[:50],
        "sample_pointers": pointers[:50],
        "sample_floats": floats[:50],
        "edit_policy": edit_policy_for(path, bool(rsc), unpack_meta),
    }
    if path.suffix.lower() == ".wgd":
        summary["wgd_probe"] = probe_wgd(payload)
    if out_dir is not None:
        write_analysis_outputs(path, out_dir, summary, strings, referenced_strings, pointers, floats, payload)
    return summary


def edit_policy_for(path: Path, is_rsc: bool, unpack_meta: dict[str, Any]) -> dict[str, Any]:
    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return {
            "mode": "direct-text",
            "can_stage_patch_folder": True,
            "notes": "Direct text replacement is allowed; output is staged into a patch folder if requested.",
        }
    if ext in SEMANTIC_EDIT_CANDIDATES:
        return {
            "mode": "binary-safe-plus-format-candidate",
            "can_stage_patch_folder": True,
            "notes": "Use same-size binary/string edits now. Semantic XML round-trip can be added after per-format validation.",
        }
    if is_rsc:
        can_payload = unpack_meta.get("payload_source") == "rsc-decompressed"
        return {
            "mode": "rsc-safe-patch",
            "can_stage_patch_folder": True,
            "payload_editing_available": can_payload,
            "notes": "Compressed RSC resources can be payload-patched/repacked when zstd/zlib support is available. Structural array growth is blocked.",
        }
    return {
        "mode": "binary-safe-patch",
        "can_stage_patch_folder": True,
        "notes": "Same-size byte/int/float/string patches are allowed. Structural editing is blocked.",
    }


def probe_wgd(payload: bytes) -> dict[str, Any]:
    probe: dict[str, Any] = {"recognized": False, "notes": []}
    if len(payload) < 32:
        probe["notes"].append("Payload too small for Rsc6GringoDictionary header.")
        return probe
    vals = [struct.unpack_from("<I", payload, i * 4)[0] for i in range(8)]
    probe["header_u32"] = [f"0x{v:08X}" for v in vals]
    # CodeX references Rsc6GringoDictionary VFT 0x0091BC40 and virtual pointers 0x50000000.
    probe["possible_dictionary_vft"] = vals[0] in {0x0091BC40, 0x015B4D40, 0x01979634}
    probe["virtual_pointer_count"] = sum(1 for row in scan_pointers(payload, limit=100000) if row["target_space"] == "virtual")
    referenced = extract_referenced_strings(payload, limit=100)
    strings = referenced if referenced else extract_strings(payload, limit=100)
    probe["first_names"] = [s["text"] for s in strings[:25]]
    probe["recognized"] = bool(probe["possible_dictionary_vft"] or probe["virtual_pointer_count"] > 4)
    if probe["recognized"]:
        probe["notes"].append("Looks compatible with CodeX Rsc6GringoDictionary-style virtual pointer layout.")
        probe["notes"].append("Use same-size string/float/bool patches only until full gringo block round-trip is validated.")
    return probe


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        if not rows:
            fh.write("")
            return
        fieldnames: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_analysis_outputs(path: Path, out_dir: Path, summary: dict[str, Any], strings: list[dict[str, Any]], referenced_strings: list[dict[str, Any]], pointers: list[dict[str, Any]], floats: list[dict[str, Any]], payload: bytes) -> None:
    stem = safe_out_name(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.analysis.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out_dir / f"{stem}.strings.csv", strings)
    write_csv(out_dir / f"{stem}.referenced_strings.csv", referenced_strings)
    write_csv(out_dir / f"{stem}.pointers.csv", pointers)
    write_csv(out_dir / f"{stem}.floats.csv", floats)
    (out_dir / f"{stem}.payload.bin").write_bytes(payload)
    md = [
        f"# Code RED RDR1 Resource Analysis: `{path.name}`",
        "",
        f"- Size: `{summary['size']}` bytes",
        f"- SHA1: `{summary['sha1']}`",
        f"- Type: `{summary['known_name']}` (`{summary['extension']}`)",
        f"- Payload size: `{summary['payload']['size']}` bytes",
        f"- Payload source: `{summary['payload']['source']}`",
        f"- Codec: `{summary['payload']['codec']}`",
        f"- Strings: `{summary['counts']['strings']}`",
        f"- Referenced strings: `{summary['counts'].get('referenced_strings', 0)}`",
        f"- Pointer candidates: `{summary['counts']['pointer_candidates']}`",
        f"- Float candidates: `{summary['counts']['float_candidates']}`",
        "",
        "## Edit policy",
        "",
        f"Mode: `{summary['edit_policy']['mode']}`",
        "",
        summary['edit_policy'].get('notes', ''),
        "",
        "## Outputs",
        "",
        f"- `{stem}.analysis.json`",
        f"- `{stem}.strings.csv`",
        f"- `{stem}.referenced_strings.csv`",
        f"- `{stem}.pointers.csv`",
        f"- `{stem}.floats.csv`",
        f"- `{stem}.payload.bin`",
    ]
    if summary.get("payload", {}).get("decompress_error"):
        md += ["", "## Decompression note", "", str(summary["payload"]["decompress_error"])]
    (out_dir / f"{stem}.analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def apply_edits_to_payload(payload: bytes, edits: list[dict[str, Any]], same_size_default: bool = True) -> tuple[bytes, list[dict[str, Any]]]:
    buf = bytearray(payload)
    log: list[dict[str, Any]] = []
    for i, edit in enumerate(edits):
        kind = edit.get("kind")
        same_size = bool(edit.get("same_size", same_size_default))
        if kind == "replace_bytes":
            off = parse_int(edit["offset"])
            new = bytes.fromhex(str(edit["new_hex"]).replace(" ", ""))
            old_hex = edit.get("old_hex")
            if old_hex is not None:
                old = bytes.fromhex(str(old_hex).replace(" ", ""))
                if bytes(buf[off:off + len(old)]) != old:
                    raise RuntimeError(f"edit {i}: old_hex mismatch at 0x{off:X}")
                if same_size and len(old) != len(new):
                    raise RuntimeError(f"edit {i}: same-size replace_bytes requires equal old/new sizes")
                buf[off:off + len(old)] = new
            else:
                if same_size and off + len(new) > len(buf):
                    raise RuntimeError(f"edit {i}: write extends past payload")
                buf[off:off + len(new)] = new
            log.append({"edit": i, "kind": kind, "offset": off, "new_size": len(new)})
        elif kind == "replace_string":
            old = str(edit["old"])
            new = str(edit["new"])
            encoding = str(edit.get("encoding", "ascii"))
            old_b = old.encode(encoding)
            new_b = new.encode(encoding)
            if same_size and len(old_b) != len(new_b):
                # Allow shorter new string padded with NULs, useful for in-place game strings.
                if len(new_b) < len(old_b) and edit.get("pad", "nul") == "nul":
                    new_b = new_b + (b"\x00" * (len(old_b) - len(new_b)))
                else:
                    raise RuntimeError(f"edit {i}: replacement string must be same encoded size or shorter with NUL padding")
            start_at = parse_int(edit.get("start_at", 0))
            count = int(edit.get("count", 1))
            pos = -1
            search_from = start_at
            for _ in range(count):
                pos = bytes(buf).find(old_b, search_from)
                if pos < 0:
                    raise RuntimeError(f"edit {i}: old string not found: {old!r}")
                search_from = pos + len(old_b)
            buf[pos:pos + len(old_b)] = new_b
            log.append({"edit": i, "kind": kind, "offset": pos, "old": old, "new": new, "encoding": encoding})
        elif kind in {"set_u8", "set_u16", "set_u32", "set_i32", "set_float32"}:
            off = parse_int(edit["offset"])
            val = edit["value"]
            endian = "<" if str(edit.get("endian", "little")).lower().startswith("little") else ">"
            fmt = {"set_u8": "B", "set_u16": "H", "set_u32": "I", "set_i32": "i", "set_float32": "f"}[kind]
            packed = struct.pack(endian + fmt, float(val) if kind == "set_float32" else int(val))
            if off + len(packed) > len(buf):
                raise RuntimeError(f"edit {i}: write past end at 0x{off:X}")
            old_hex = edit.get("old_hex")
            if old_hex is not None:
                old = bytes.fromhex(str(old_hex).replace(" ", ""))
                if bytes(buf[off:off + len(old)]) != old:
                    raise RuntimeError(f"edit {i}: old_hex mismatch at 0x{off:X}")
            buf[off:off + len(packed)] = packed
            log.append({"edit": i, "kind": kind, "offset": off, "value": val})
        else:
            raise RuntimeError(f"edit {i}: unknown edit kind {kind!r}")
    return bytes(buf), log



def search_references(input_path: Path, query: str, out: Path | None = None, limit: int = 5000, case_sensitive: bool = False) -> dict[str, Any]:
    """Search referenced virtual/physical strings in an RSC/payload file."""
    data = input_path.read_bytes()
    rsc, payload, unpack_meta = unpack_rsc(data)
    refs = extract_referenced_strings(payload, limit=limit)
    q = query if case_sensitive else query.lower()
    matches = []
    for row in refs:
        text = str(row.get("text", ""))
        hay = text if case_sensitive else text.lower()
        if q in hay:
            matches.append(row)
    result = {
        "input": str(input_path),
        "query": query,
        "case_sensitive": case_sensitive,
        "payload_source": unpack_meta.get("payload_source"),
        "payload_size": len(payload),
        "rsc": asdict(rsc) if rsc else None,
        "total_referenced_strings_scanned": len(refs),
        "match_count": len(matches),
        "matches": matches,
    }
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        base = safe_out_name(input_path)
        (out / f"{base}.ref_search.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        write_csv(out / f"{base}.ref_search.csv", matches)
    return result


def _cstring_bytes(text: str, encoding: str = "ascii") -> bytes:
    raw = text.encode(encoding)
    if b"\x00" in raw:
        raise ValueError("Replacement strings cannot contain embedded NUL bytes")
    return raw


def _unique_referenced_cstring_targets(payload: bytes, text: str, encoding: str = "ascii", limit: int = 200000) -> list[dict[str, Any]]:
    refs = extract_referenced_strings(payload, limit=limit)
    targets: dict[int, dict[str, Any]] = {}
    for row in refs:
        if row.get("text") == text:
            targets[int(row["target_offset"])] = row
    # Fallback: exact raw C-string scan. This catches unreferenced but valid strings.
    needle = _cstring_bytes(text, encoding) + b"\x00"
    pos = 0
    while True:
        idx = payload.find(needle, pos)
        if idx < 0:
            break
        targets.setdefault(idx, {
            "pointer_offset": None,
            "pointer_offset_hex": "",
            "pointer_value_hex": "",
            "target_offset": idx,
            "target_offset_hex": f"0x{idx:X}",
            "target_space": "raw-scan",
            "text": text,
        })
        pos = idx + 1
    return [targets[k] for k in sorted(targets)]


def override_referenced_string(
    input_path: Path,
    old: str,
    new: str,
    output: Path | None = None,
    patch_root: Path | None = None,
    internal_path: str | None = None,
    occurrence: str = "all",
    encoding: str = "ascii",
    zstd_level: int = 12,
) -> dict[str, Any]:
    """Replace a referenced C-string in payload and repack/stage the resource.

    This is intentionally conservative: the new string must be the same encoded
    length or shorter. Shorter values are padded with NUL bytes, so offsets and
    arrays do not move.
    """
    data = input_path.read_bytes()
    rsc, payload, unpack_meta = unpack_rsc(data)
    if rsc and unpack_meta.get("payload_source") != "rsc-decompressed":
        raise RuntimeError("Cannot override string because the RSC payload did not decompress")
    old_b = _cstring_bytes(old, encoding)
    new_b = _cstring_bytes(new, encoding)
    if len(new_b) > len(old_b):
        raise RuntimeError(
            f"New string is longer than old string ({len(new_b)} > {len(old_b)}). "
            "Use an equal/shorter replacement until structural rebuild support exists."
        )
    replacement = new_b + (b"\x00" * (len(old_b) - len(new_b)))
    targets = _unique_referenced_cstring_targets(payload, old, encoding=encoding)
    if not targets:
        raise RuntimeError(f"String was not found as a referenced/raw C-string: {old!r}")
    if occurrence.lower() in {"all", "*"}:
        selected = targets
    else:
        idx = int(occurrence)
        if idx < 1 or idx > len(targets):
            raise RuntimeError(f"Occurrence {idx} is out of range; found {len(targets)} target(s)")
        selected = [targets[idx - 1]]
    buf = bytearray(payload)
    edits = []
    for target in selected:
        off = int(target["target_offset"])
        current = bytes(buf[off:off + len(old_b)])
        if current != old_b:
            raise RuntimeError(f"Guard mismatch at 0x{off:X}; expected {old!r}")
        buf[off:off + len(old_b)] = replacement
        edits.append({
            "target_offset": off,
            "target_offset_hex": f"0x{off:X}",
            "old": old,
            "new": new,
            "old_size": len(old_b),
            "new_size": len(new_b),
            "nul_padded_bytes": len(old_b) - len(new_b),
            "source_ref": target,
        })
    edited_payload = bytes(buf)
    fit_report: dict[str, Any] | None = None
    if rsc:
        final, fit_report = repack_rsc_fit_size(data, edited_payload, zstd_level=zstd_level, target_size=len(data))
    else:
        final = edited_payload
    if output is None:
        output = input_path.with_name(input_path.stem + f".override_{safe_out_name(Path(new)).replace('.', '_')}" + input_path.suffix)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(final)
    staged_path = None
    if patch_root is not None:
        if not internal_path:
            internal_path = input_path.name
        staged_path = stage_patch_file(output, patch_root, internal_path)
    verify_rsc, verify_payload, verify_meta = unpack_rsc(final)
    verification = {
        "can_reopen": True,
        "payload_source": verify_meta.get("payload_source"),
        "payload_size": len(verify_payload),
        "payload_sha1": sha1(verify_payload),
        "new_string_targets": _unique_referenced_cstring_targets(verify_payload, new, encoding=encoding)[:20],
    }
    result = {
        "input": str(input_path),
        "output": str(output),
        "patch_root": str(patch_root) if patch_root else None,
        "internal_path": internal_path,
        "staged_path": str(staged_path) if staged_path else None,
        "old": old,
        "new": new,
        "occurrence": occurrence,
        "source_sha1": sha1(data),
        "output_sha1": sha1(final),
        "source_size": len(data),
        "output_size": len(final),
        "exact_size_preserved": len(final) == len(data),
        "rsc_fit": fit_report,
        "rsc": asdict(rsc) if rsc else None,
        "payload_before_sha1": sha1(payload),
        "payload_after_sha1": sha1(edited_payload),
        "targets_found": len(targets),
        "targets_modified": len(edits),
        "edits": edits,
        "verification": verification,
        "guardrails": [
            "source RPF was not modified",
            "replacement string was same-size or shorter with NUL padding",
            "no arrays, pointers, or resource sizes were structurally grown",
        ],
    }
    report = output.with_suffix(output.suffix + ".override_report.json")
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result



def override_referenced_substrings(
    input_path: Path,
    replacements: list[tuple[str, str]],
    output: Path | None = None,
    patch_root: Path | None = None,
    internal_path: str | None = None,
    encoding: str = "ascii",
    zstd_level: int = 12,
    case_sensitive: bool = False,
    search_limit: int = 200000,
) -> dict[str, Any]:
    """Batch replace substrings inside referenced C-strings without moving data.

    This is meant for resource/model path overrides such as replacing
    revolver_cattleman01x -> melee_lasso01x inside strings like
    $\\fragments\\revolver_cattleman01x.

    Replacement values must be equal-length or shorter than the matched old
    substring. Shorter values are NUL padded at the match point, truncating the
    remaining original C-string so pointers and arrays remain stable.
    """
    if not replacements:
        raise RuntimeError("No replacements were supplied")
    data = input_path.read_bytes()
    rsc, payload, unpack_meta = unpack_rsc(data)
    if rsc and unpack_meta.get("payload_source") != "rsc-decompressed":
        raise RuntimeError("Cannot override strings because the RSC payload did not decompress")

    normalized: list[dict[str, Any]] = []
    for old, new in replacements:
        if not old:
            raise RuntimeError("Old string cannot be empty")
        old_b = _cstring_bytes(old, encoding)
        new_b = _cstring_bytes(new, encoding)
        if len(new_b) > len(old_b):
            raise RuntimeError(
                f"New string {new!r} is longer than old string {old!r} "
                f"({len(new_b)} > {len(old_b)}). Use equal/shorter replacements only."
            )
        normalized.append({
            "old": old,
            "new": new,
            "old_b": old_b,
            "new_b": new_b,
            "replacement_b": new_b + (b"\x00" * (len(old_b) - len(new_b))),
            "old_cmp": old if case_sensitive else old.lower(),
        })

    refs = extract_referenced_strings(payload, limit=search_limit)
    planned: dict[tuple[int, str], dict[str, Any]] = {}
    for row in refs:
        text = str(row.get("text", ""))
        hay = text if case_sensitive else text.lower()
        for repl in normalized:
            pos = hay.find(repl["old_cmp"])
            if pos < 0:
                continue
            target_offset = int(row["target_offset"])
            patch_offset = target_offset + pos
            key = (patch_offset, repl["old"])
            planned[key] = {
                "patch_offset": patch_offset,
                "patch_offset_hex": f"0x{patch_offset:X}",
                "referenced_string_target": target_offset,
                "referenced_string_target_hex": f"0x{target_offset:X}",
                "old": repl["old"],
                "new": repl["new"],
                "old_size": len(repl["old_b"]),
                "new_size": len(repl["new_b"]),
                "nul_padded_bytes": len(repl["old_b"]) - len(repl["new_b"]),
                "matched_text_before": text,
                "source_ref": row,
                "replacement_b": repl["replacement_b"],
                "old_b": repl["old_b"],
            }

    if not planned:
        searched = [r[0] for r in replacements]
        raise RuntimeError(f"No referenced strings matched any replacement source: {searched}")

    buf = bytearray(payload)
    edits: list[dict[str, Any]] = []
    for key, edit in sorted(planned.items(), key=lambda kv: kv[1]["patch_offset"]):
        off = int(edit["patch_offset"])
        old_b = edit.pop("old_b")
        replacement_b = edit.pop("replacement_b")
        current = bytes(buf[off:off + len(old_b)])
        if case_sensitive:
            ok = current == old_b
        else:
            ok = current.lower() == old_b.lower()
        if not ok:
            raise RuntimeError(
                f"Guard mismatch at 0x{off:X}; expected {edit['old']!r}, found {current!r}"
            )
        buf[off:off + len(old_b)] = replacement_b
        after = _read_ascii_cstring(bytes(buf), int(edit["referenced_string_target"]), 256)
        edit["matched_text_after"] = after
        edits.append(edit)

    edited_payload = bytes(buf)
    fit_report: dict[str, Any] | None = None
    if rsc:
        final, fit_report = repack_rsc_fit_size(data, edited_payload, zstd_level=zstd_level, target_size=len(data))
    else:
        final = edited_payload
    if output is None:
        output = input_path.with_name(input_path.stem + ".lasso_override" + input_path.suffix)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(final)

    staged_path = None
    if patch_root is not None:
        if not internal_path:
            internal_path = input_path.name
        staged_path = stage_patch_file(output, patch_root, internal_path)

    verify_rsc, verify_payload, verify_meta = unpack_rsc(final)
    verify_refs = extract_referenced_strings(verify_payload, limit=search_limit)
    remaining: dict[str, int] = {}
    created: dict[str, int] = {}
    for old, new in replacements:
        old_cmp = old if case_sensitive else old.lower()
        new_cmp = new if case_sensitive else new.lower()
        remaining[old] = sum(1 for row in verify_refs if old_cmp in (str(row.get("text", "")) if case_sensitive else str(row.get("text", "")).lower()))
        created[new] = sum(1 for row in verify_refs if new_cmp in (str(row.get("text", "")) if case_sensitive else str(row.get("text", "")).lower()))

    result = {
        "input": str(input_path),
        "output": str(output),
        "patch_root": str(patch_root) if patch_root else None,
        "internal_path": internal_path,
        "staged_path": str(staged_path) if staged_path else None,
        "replacements": [
            {"old": old, "new": new, "old_size": len(old.encode(encoding)), "new_size": len(new.encode(encoding))}
            for old, new in replacements
        ],
        "case_sensitive": case_sensitive,
        "source_sha1": sha1(data),
        "output_sha1": sha1(final),
        "source_size": len(data),
        "output_size": len(final),
        "exact_size_preserved": len(final) == len(data),
        "rsc_fit": fit_report,
        "rsc": asdict(rsc) if rsc else None,
        "payload_before_sha1": sha1(payload),
        "payload_after_sha1": sha1(edited_payload),
        "referenced_strings_scanned": len(refs),
        "targets_modified": len(edits),
        "edits": edits,
        "verification": {
            "can_reopen": True,
            "payload_source": verify_meta.get("payload_source"),
            "payload_size": len(verify_payload),
            "payload_sha1": sha1(verify_payload),
            "remaining_old_reference_counts": remaining,
            "new_reference_counts": created,
        },
        "guardrails": [
            "source RPF was not modified",
            "source file was not modified",
            "replacement substrings were same-size or shorter with NUL padding",
            "no arrays, pointers, or resource sizes were structurally grown",
        ],
    }
    report = output.with_suffix(output.suffix + ".batch_override_report.json")
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def weapon_lasso_override(
    input_path: Path,
    output: Path | None = None,
    patch_root: Path | None = None,
    internal_path: str | None = None,
    zstd_level: int = 12,
) -> dict[str, Any]:
    """Replace Cattleman and Schofield gringo weapon fragment refs with lasso refs."""
    replacements = [
        ("revolver_cattleman01x", "melee_lasso01x"),
        ("revolver_schofield01x", "melee_lasso01x"),
    ]
    return override_referenced_substrings(
        input_path=input_path,
        replacements=replacements,
        output=output,
        patch_root=patch_root,
        internal_path=internal_path,
        encoding="ascii",
        zstd_level=zstd_level,
        case_sensitive=False,
    )

def _load_codered_backend_for_rpf():
    workbench = ROOT / "python_workbench.py"
    if not workbench.exists():
        raise FileNotFoundError(f"Missing Code RED backend: {workbench}")
    spec = importlib.util.spec_from_file_location("codered_workbench_backend_rdr1_lab", workbench)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {workbench}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _norm_rpf_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip("/").lower()


def _match_patch_to_entry(entries: list[dict[str, Any]], rel: str) -> tuple[dict[str, Any] | None, str]:
    wanted = _norm_rpf_path(rel)
    wanted_no_root = wanted[5:] if wanted.startswith("root/") else wanted
    files = [e for e in entries if str(e.get("type", "file")).lower() == "file"]
    for ent in files:
        path = _norm_rpf_path(ent.get("path"))
        if path == wanted or path == wanted_no_root:
            return ent, "exact-path"
    for ent in files:
        path = _norm_rpf_path(ent.get("path"))
        if path.endswith("/" + wanted) or path.endswith("/" + wanted_no_root):
            return ent, "suffix-path"
    base = Path(wanted).name
    matches = [ent for ent in files if str(ent.get("name") or "").lower() == base]
    if len(matches) == 1:
        return matches[0], "unique-name"
    return None, "not-found" if not matches else "ambiguous-name"


def _match_rank(mode: str) -> int:
    ranks = {
        "exact-path": 0,
        "suffix-path": 1,
        "unique-name": 2,
        "ambiguous-name": 8,
        "not-found": 9,
    }
    return ranks.get(mode, 9)


def patch_archive_raw_exact(archive: Path, patch_root: Path, out: Path | None = None) -> dict[str, Any]:
    """Apply exact-size replacement files directly to a copied RPF.

    This path is intentionally narrow: it only overwrites entries when the staged
    replacement is exactly the same byte length as the existing RPF entry. That
    avoids structural growth, relocation, and table-of-contents rewrites.

    v8 also handles stale duplicate patch files safely. If the same archive entry
    is matched by multiple staged files, exact-path + exact-size candidates win;
    older suffix/name matches are marked as superseded instead of making the
    whole patch run fail after the valid patch was applied.
    """
    archive = archive if archive.is_absolute() else (ROOT / archive)
    patch_root = patch_root if patch_root.is_absolute() else (ROOT / patch_root)
    if out is not None and not out.is_absolute():
        out = ROOT / out
    if out is None:
        out = archive.with_name(archive.stem + ".codered_patched" + archive.suffix)

    if not archive.exists():
        raise FileNotFoundError(
            f"Source RPF not found: {archive}\n"
            "Put gringores.rpf in Code_RED\\game\\ or pass the real path with --archive."
        )
    if not patch_root.exists():
        raise FileNotFoundError(f"Patch root not found: {patch_root}")
    patch_files = [p for p in patch_root.rglob("*") if p.is_file()]
    if not patch_files:
        raise RuntimeError(f"Patch root has no replacement files: {patch_root}")

    wb = _load_codered_backend_for_rpf()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"Not a readable RPF6 archive: {archive}")
    entries = list(info.get("entries") or [])

    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive, out)

    # Resolve all candidates before writing so duplicate/stale staged files do not
    # cause false failure. This happens when older versions staged both
    # patches/wgd_lasso_override/commongringos.wgd and the newer exact internal
    # path patches/wgd_lasso_override/root/gringores/commongringos.wgd.
    candidates: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    unmatched = 0
    for patch in patch_files:
        rel = patch.relative_to(patch_root).as_posix()
        ent, mode = _match_patch_to_entry(entries, rel)
        if ent is None:
            unmatched += 1
            results.append({"status": "unmatched", "patch": str(patch), "internal_path": rel, "match_mode": mode})
            continue
        size = int(ent.get("size_in_archive") or ent.get("size") or 0)
        data_size = patch.stat().st_size
        internal_path = ent.get("path") or ent.get("name") or rel
        candidates.append({
            "patch": patch,
            "rel": rel,
            "entry": ent,
            "mode": mode,
            "rank": _match_rank(mode),
            "archive_size": size,
            "replacement_size": data_size,
            "exact_size": data_size == size,
            "internal_path": internal_path,
            "offset": int(ent.get("offset") or 0),
            "entry_key": _norm_rpf_path(internal_path),
        })

    best_by_entry: dict[str, dict[str, Any]] = {}
    superseded: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    for cand in candidates:
        key = cand["entry_key"]
        current = best_by_entry.get(key)
        if current is None:
            best_by_entry[key] = cand
            continue
        # Prefer exact-size candidates, then more specific match modes, then
        # deeper paths (root/gringores/file beats stale root-level filename).
        cand_score = (0 if cand["exact_size"] else 1, cand["rank"], -len(cand["rel"]))
        current_score = (0 if current["exact_size"] else 1, current["rank"], -len(current["rel"]))
        if cand_score < current_score:
            superseded.append(current)
            best_by_entry[key] = cand
        else:
            superseded.append(cand)

    applied = blocked = identical = superseded_count = 0
    with out.open("r+b") as fh:
        for cand in sorted(best_by_entry.values(), key=lambda c: (c["offset"], c["rank"], c["rel"])):
            patch = cand["patch"]
            data = patch.read_bytes()
            size = cand["archive_size"]
            offset = cand["offset"]
            if len(data) != size:
                blocked += 1
                blocked_candidates.append(cand)
                results.append({
                    "status": "blocked",
                    "reason": "replacement is not exact-size; rerun the staging command with v7+ so RSC zstd skippable padding is added, or remove stale root-level patch files",
                    "patch": str(patch),
                    "internal_path": cand["internal_path"],
                    "match_mode": cand["mode"],
                    "archive_size": size,
                    "replacement_size": len(data),
                    "offset": offset,
                })
                continue
            fh.seek(offset)
            current = fh.read(size)
            if current == data:
                identical += 1
                status = "identical"
            else:
                fh.seek(offset)
                fh.write(data)
                applied += 1
                status = "applied-raw-exact"
            results.append({
                "status": status,
                "patch": str(patch),
                "internal_path": cand["internal_path"],
                "match_mode": cand["mode"],
                "offset": offset,
                "size": size,
                "sha1": sha1(data),
                "storage_kind": cand["entry"].get("storage_kind") or ("resource" if cand["entry"].get("is_resource") else "binary"),
            })

    for cand in sorted(superseded, key=lambda c: (c["entry_key"], c["rank"], c["rel"])):
        superseded_count += 1
        results.append({
            "status": "superseded",
            "reason": "duplicate staged patch matched the same archive entry; a better exact-path/exact-size staged file was used instead",
            "patch": str(cand["patch"]),
            "internal_path": cand["internal_path"],
            "match_mode": cand["mode"],
            "archive_size": cand["archive_size"],
            "replacement_size": cand["replacement_size"],
            "offset": cand["offset"],
        })

    report = {
        "archive_source": str(archive),
        "working_copy": str(out),
        "patch_root": str(patch_root),
        "mode": "raw-exact-overwrite",
        "scanned": len(patch_files),
        "resolved_candidates": len(candidates),
        "applied": applied,
        "identical": identical,
        "blocked": blocked,
        "superseded": superseded_count,
        "unmatched_count": unmatched,
        "source_rpf_modified": False,
        "results": results,
        "guardrails": [
            "source RPF was copied first",
            "only exact-size replacements were written",
            "duplicate stale patch files are ignored when a better exact-path replacement exists",
            "no RPF entries were relocated",
            "no RPF table-of-contents sizes were changed",
        ],
    }
    report_path = out.with_name(out.stem + "_raw_exact_patch_report.json")
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report

def run_patch_apply_via_existing_codered(archive: Path, patch_root: Path, out: Path | None = None) -> int:
    """Apply a staged patch folder to a copied RPF.

    v7 uses a raw exact-size overwrite path first. This is the right path for
    RDR1 RSC resources that Code RED Resource Lab already repacked to the exact
    original byte length.
    """
    result = patch_archive_raw_exact(archive, patch_root, out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("blocked") or result.get("unmatched_count"):
        raise RuntimeError("One or more staged patch files were blocked or unmatched. See report_path in the JSON output.")
    return 0


def apply_edit_spec(spec_path: Path, output: Path | None = None, patch_root: Path | None = None, internal_path: str | None = None) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    source = Path(spec.get("source") or "")
    if not source.is_absolute():
        source = (spec_path.parent / source).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    data = source.read_bytes()
    rsc, payload, unpack_meta = unpack_rsc(data)
    scope = str(spec.get("scope", "payload" if rsc else "file"))
    edits = spec.get("edits") or []
    same_size = bool(spec.get("same_size", True))
    if scope == "payload" and rsc and unpack_meta.get("payload_source") != "rsc-decompressed":
        raise RuntimeError("Cannot payload-edit this RSC because it did not decompress. Install zstandard or use an unpacked payload.")
    target_bytes = payload if scope == "payload" else data
    edited, edit_log = apply_edits_to_payload(target_bytes, edits, same_size_default=same_size)
    if scope == "payload" and rsc:
        final = repack_rsc(data, edited, int(spec.get("zstd_level", 12)))
    else:
        final = edited
    if output is None:
        raw_out = spec.get("output")
        if raw_out:
            output = Path(raw_out)
            if not output.is_absolute():
                output = (spec_path.parent / output).resolve()
        else:
            output = spec_path.parent / f"{source.stem}.codered_edit{source.suffix}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(final)
    staged_path = None
    if patch_root is None and spec.get("patch_root"):
        patch_root = Path(spec["patch_root"])
        if not patch_root.is_absolute():
            patch_root = (spec_path.parent / patch_root).resolve()
    if internal_path is None:
        internal_path = spec.get("internal_path")
    if patch_root is not None and internal_path:
        staged_path = stage_patch_file(output, patch_root, internal_path)
    result = {
        "source": str(source),
        "output": str(output),
        "source_size": len(data),
        "output_size": len(final),
        "source_sha1": sha1(data),
        "output_sha1": sha1(final),
        "scope": scope,
        "rsc": asdict(rsc) if rsc else None,
        "edits_applied": edit_log,
        "patch_root": str(patch_root) if patch_root else None,
        "staged_path": str(staged_path) if staged_path else None,
    }
    report = output.with_suffix(output.suffix + ".edit_report.json")
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def stage_patch_file(source: Path, patch_root: Path, internal_path: str) -> Path:
    rel = internal_path.replace("\\", "/").strip("/")
    if not rel:
        raise ValueError("internal_path cannot be empty")
    if ".." in Path(rel).parts:
        raise ValueError("internal_path cannot contain '..'")
    dest = patch_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return dest


def write_edit_template(source: Path, out: Path, scope: str | None = None) -> None:
    data = source.read_bytes()
    rsc = detect_rsc(data)
    use_scope = scope or ("payload" if rsc else "file")
    template = {
        "source": str(source),
        "output": str(source.with_name(source.stem + ".edited" + source.suffix)),
        "scope": use_scope,
        "same_size": True,
        "internal_path": f"PUT/RPF/INTERNAL/PATH/{source.name}",
        "patch_root": "patches/rdr1_resource_lab_patch",
        "edits": [
            {
                "kind": "replace_string",
                "old": "OLD_TEXT",
                "new": "NEW_TEXT",
                "encoding": "ascii",
                "pad": "nul",
                "count": 1
            },
            {
                "kind": "set_float32",
                "offset": "0x0",
                "value": 1.0,
                "endian": "little",
                "old_hex": "OPTIONAL_GUARD_HEX_REMOVE_ME"
            }
        ],
        "notes": [
            "Remove example edits you do not use.",
            "For compressed RSC files, scope=payload edits the decompressed payload and repacks the RSC wrapper.",
            "Use same-size edits first. Structural array growth is deliberately blocked for safety."
        ]
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(template, indent=2), encoding="utf-8")


def run_inventory_via_existing_codered(archive: Path, out: Path) -> int:
    tool = ROOT / "tools" / "codered_rpf_utils.py"
    if not tool.exists():
        raise FileNotFoundError("Place this drop-in inside Code RED root to use RPF inventory delegation.")
    cmd = [sys.executable, str(tool), "inventory", "--archive", str(archive), "--out", str(out)]
    return subprocess.call(cmd)


def extract_via_existing_codered(archive: Path, out: Path, entry: str | None = None, all_entries: bool = False) -> int:
    tool = ROOT / "tools" / "codered_rpf_utils.py"
    if not tool.exists():
        raise FileNotFoundError("Place this drop-in inside Code RED root to use RPF extraction delegation.")
    cmd = [sys.executable, str(tool), "extract", "--archive", str(archive), "--out", str(out)]
    if all_entries:
        cmd.append("--all")
    elif entry:
        cmd += ["--entry", entry]
    else:
        raise ValueError("entry or all_entries required")
    return subprocess.call(cmd)


def write_status(out: Path) -> dict[str, Any]:
    rows = []
    for ext, name in sorted(RESOURCE_EXTENSIONS.items()):
        rows.append({
            "extension": ext,
            "name": name,
            "view_analyze": True,
            "safe_patch_edit": True,
            "semantic_edit_candidate": ext in SEMANTIC_EDIT_CANDIDATES,
            "direct_text_edit": ext in TEXT_EXTENSIONS,
            "guardrail": "same-size/patch-folder" if ext in VIEW_ANALYZE_ONLY_FIRST else "candidate semantic + patch-folder",
        })
    report = {
        "tool": "Code RED RDR1 Resource Lab",
        "version": "v6",
        "zstandard_python": zstd is not None,
        "zstd_cli": _zstd_cli(),
        "format_status": rows,
        "policy": {
            "source_rpf_mutation": "blocked by this tool",
            "archive_writeback": "use Code RED copied-archive patch backend after staging patch folder",
            "structural_resource_growth": "blocked until round-trip validators exist",
        }
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report



def parse_replacement_map(raw: str) -> list[tuple[str, str]]:
    path = Path(raw)
    if path.exists():
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return [(str(k), str(v)) for k, v in obj.items()]
        if isinstance(obj, list):
            out: list[tuple[str, str]] = []
            for item in obj:
                if isinstance(item, dict):
                    out.append((str(item["old"]), str(item["new"])))
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    out.append((str(item[0]), str(item[1])))
                else:
                    raise RuntimeError(f"Unsupported replacement item: {item!r}")
            return out
        raise RuntimeError("Replacement map JSON must be an object, list of {old,new}, or list of pairs")
    pairs: list[tuple[str, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise RuntimeError(f"Replacement pair must be old=new: {part!r}")
        old, new = part.split("=", 1)
        pairs.append((old.strip(), new.strip()))
    if not pairs:
        raise RuntimeError("No replacements parsed")
    return pairs

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Code RED RDR1 Resource Lab")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="Analyze one resource/file and export JSON/CSV/MD reports")
    a.add_argument("--input", required=True)
    a.add_argument("--out", default=str(REPORT_ROOT))
    a.add_argument("--string-limit", type=int, default=2000)

    b = sub.add_parser("batch-analyze", help="Analyze all matching files under a folder")
    b.add_argument("--input", required=True)
    b.add_argument("--out", default=str(REPORT_ROOT))
    b.add_argument("--extensions", default=",".join(sorted(RESOURCE_EXTENSIONS)))

    u = sub.add_parser("unpack-rsc", help="Unpack an RSC resource payload if possible")
    u.add_argument("--input", required=True)
    u.add_argument("--out", required=True)

    t = sub.add_parser("template", help="Write a guarded edit spec template")
    t.add_argument("--input", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--scope", choices=["file", "payload"], default=None)

    e = sub.add_parser("edit", help="Apply a JSON edit spec and optionally stage a patch folder")
    e.add_argument("--spec", required=True)
    e.add_argument("--out", default="")
    e.add_argument("--patch-root", default="")
    e.add_argument("--internal-path", default="")

    s = sub.add_parser("stage", help="Copy a replacement file into a patch folder by internal RPF path")
    s.add_argument("--source", required=True)
    s.add_argument("--patch-root", required=True)
    s.add_argument("--internal-path", required=True)


    sr = sub.add_parser("search-refs", help="Search real referenced strings in an RSC/payload file")
    sr.add_argument("--input", required=True)
    sr.add_argument("--query", required=True)
    sr.add_argument("--out", default=str(REPORT_ROOT))
    sr.add_argument("--limit", type=int, default=5000)
    sr.add_argument("--case-sensitive", action="store_true")

    ov = sub.add_parser("override-string", help="Same-size/shorter referenced C-string override, with optional patch staging")
    ov.add_argument("--input", required=True)
    ov.add_argument("--old", required=True)
    ov.add_argument("--new", required=True)
    ov.add_argument("--out", default="")
    ov.add_argument("--patch-root", default="")
    ov.add_argument("--internal-path", default="")
    ov.add_argument("--occurrence", default="all", help="all or 1-based target number")
    ov.add_argument("--encoding", default="ascii")
    ov.add_argument("--zstd-level", type=int, default=12)

    wl = sub.add_parser("weapon-lasso-override", help="Replace Cattleman/Schofield WGD weapon refs with melee_lasso01x and stage the result")
    wl.add_argument("--input", required=True)
    wl.add_argument("--out", default="")
    wl.add_argument("--patch-root", default="")
    wl.add_argument("--internal-path", default="")
    wl.add_argument("--zstd-level", type=int, default=12)

    bo = sub.add_parser("batch-override-refs", help="Batch replace referenced C-string substrings with same-size/shorter values")
    bo.add_argument("--input", required=True)
    bo.add_argument("--map", required=True, help="Comma list old=new,old2=new2 or path to JSON map/list")
    bo.add_argument("--out", default="")
    bo.add_argument("--patch-root", default="")
    bo.add_argument("--internal-path", default="")
    bo.add_argument("--case-sensitive", action="store_true")
    bo.add_argument("--zstd-level", type=int, default=12)

    pa = sub.add_parser("patch-archive", help="Apply a staged patch folder to a copied RPF archive using Code RED backend")
    pa.add_argument("--archive", required=True)
    pa.add_argument("--patch-root", required=True)
    pa.add_argument("--out", default="")

    st = sub.add_parser("status", help="Write resource support/status JSON")
    st.add_argument("--out", default=str(REPORT_ROOT / "rdr1_resource_lab_status.json"))

    ri = sub.add_parser("rpf-inventory", help="Delegate to Code RED's existing RPF inventory tool")
    ri.add_argument("--archive", required=True)
    ri.add_argument("--out", default=str(REPORT_ROOT / "rpf_inventory"))

    rx = sub.add_parser("rpf-extract", help="Delegate to Code RED's existing RPF extract tool")
    rx.add_argument("--archive", required=True)
    rx.add_argument("--out", required=True)
    rx.add_argument("--entry", default="")
    rx.add_argument("--all", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    try:
        if args.cmd == "analyze":
            summary = analyze_file(Path(args.input), Path(args.out), args.string_limit)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "batch-analyze":
            root = Path(args.input)
            out = Path(args.out)
            exts = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
            paths = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts]
            summaries = []
            for path in paths:
                rel_out = out / path.relative_to(root).parent
                summaries.append(analyze_file(path, rel_out, 500))
            manifest = {"input": str(root), "count": len(paths), "files": summaries}
            out.mkdir(parents=True, exist_ok=True)
            (out / "batch_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps({"count": len(paths), "manifest": str(out / "batch_manifest.json")}, indent=2))
            return 0
        if args.cmd == "unpack-rsc":
            data = Path(args.input).read_bytes()
            info, payload, meta = unpack_rsc(data)
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(payload)
            report = {"input": args.input, "out": str(out), "rsc": asdict(info) if info else None, "meta": meta, "payload_size": len(payload), "payload_sha1": sha1(payload)}
            print(json.dumps(report, indent=2))
            return 0
        if args.cmd == "template":
            write_edit_template(Path(args.input), Path(args.out), args.scope)
            print(json.dumps({"template": args.out}, indent=2))
            return 0
        if args.cmd == "edit":
            result = apply_edit_spec(
                Path(args.spec),
                output=Path(args.out) if args.out else None,
                patch_root=Path(args.patch_root) if args.patch_root else None,
                internal_path=args.internal_path or None,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.cmd == "stage":
            staged = stage_patch_file(Path(args.source), Path(args.patch_root), args.internal_path)
            print(json.dumps({"staged_path": str(staged)}, indent=2))
            return 0

        if args.cmd == "search-refs":
            result = search_references(Path(args.input), args.query, Path(args.out), args.limit, bool(args.case_sensitive))
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "override-string":
            result = override_referenced_string(
                Path(args.input),
                args.old,
                args.new,
                output=Path(args.out) if args.out else None,
                patch_root=Path(args.patch_root) if args.patch_root else None,
                internal_path=args.internal_path or None,
                occurrence=args.occurrence,
                encoding=args.encoding,
                zstd_level=args.zstd_level,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "weapon-lasso-override":
            result = weapon_lasso_override(
                Path(args.input),
                output=Path(args.out) if args.out else None,
                patch_root=Path(args.patch_root) if args.patch_root else None,
                internal_path=args.internal_path or None,
                zstd_level=args.zstd_level,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "batch-override-refs":
            result = override_referenced_substrings(
                input_path=Path(args.input),
                replacements=parse_replacement_map(args.map),
                output=Path(args.out) if args.out else None,
                patch_root=Path(args.patch_root) if args.patch_root else None,
                internal_path=args.internal_path or None,
                zstd_level=args.zstd_level,
                case_sensitive=bool(args.case_sensitive),
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "patch-archive":
            return run_patch_apply_via_existing_codered(
                Path(args.archive),
                Path(args.patch_root),
                Path(args.out) if args.out else None,
            )

        if args.cmd == "status":
            report = write_status(Path(args.out))
            print(json.dumps(report, indent=2))
            return 0
        if args.cmd == "rpf-inventory":
            return run_inventory_via_existing_codered(Path(args.archive), Path(args.out))
        if args.cmd == "rpf-extract":
            return extract_via_existing_codered(Path(args.archive), Path(args.out), args.entry or None, bool(args.all))
        p.error("unknown command")
        return 2
    except Exception as exc:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        crash = REPORT_ROOT / "rdr1_resource_lab_crash.log"
        crash.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Crash note: {crash}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
