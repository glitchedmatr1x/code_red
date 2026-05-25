#!/usr/bin/env python3
"""Convert XENON RDR .xsc resources into PC-wrapped .wsc candidates.

This is a real decode/rewrap probe, not an extension rename:

1. XENON .xsc header bytes are 32-bit word-swapped RSC85.
2. The encrypted payload is not word-swapped.
3. Payload decrypts with the known RDR AES key.
4. Decrypted payload contains the Xbox LZX wrapper:
   0F F5 12 F1 + big-endian compressed length + LZX bytes.
5. A 32-bit helper calls xcompress32.dll to decompress LZX.
6. The decoded script bytes are rewrapped as PC-style RSC85/WSC using
   Zstandard + AES, then reopened through Code RED's WSC reader.

The output should still be treated as a candidate until runtime proves that
Xbox script bytecode platform semantics are accepted by PC. The converter now
also normalizes the decoded script structure from XENON big-endian tables to
PC/Switch-style little-endian tables while preserving bytecode instruction
bytes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codered_wsc.resource import (  # noqa: E402
    KeyOptions,
    ResourceError,
    aes_crypt_16_passes,
    open_script_from_bytes,
    parse_header,
    resolve_aes_key,
    sha256,
    swap32,
    zstd_compress_variants,
)


DEFAULT_XSC_SOURCE = ROOT / "imports" / "XENON MULTIPLAYER" / "content" / "release64" / "multiplayer"
DEFAULT_OUT = ROOT / "build" / "mp_script_conversion_probe" / "xsc_lzx_pc_wsc_converted"
DEFAULT_REPORTS = ROOT / "reports" / "mp_script_conversion_probe" / "xsc_lzx_to_pc_wsc"
DEFAULT_BRIDGE = ROOT / "build" / "xcompress_bridge32" / "codered_xcompress_bridge32.exe"
DEFAULT_BRIDGE_DLL = ROOT / "build" / "xcompress_bridge32" / "xcompress32.dll"
XBOX_LZX_MAGIC = 0x0FF512F1


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def collect_xsc(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() == ".xsc" else []
    if not source.exists():
        return []
    return sorted((p for p in source.rglob("*.xsc") if p.is_file()), key=lambda p: str(p).lower())


def filter_xsc(paths: list[Path], include_stems: set[str]) -> list[Path]:
    if not include_stems:
        return paths
    lowered = {x.lower() for x in include_stems}
    return [p for p in paths if p.stem.lower() in lowered]


def relative_under(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(path.name)


def header_only_normalize_xsc(data: bytes) -> bytes:
    return swap32(data[:16]) + data[16:]


def expected_unpacked_size(normalized: bytes) -> int:
    header = parse_header(normalized, normalized_from_xsc=True)
    if header.expected_unpacked_size is None:
        raise ResourceError("XSC header did not expose an expected unpacked size")
    return header.expected_unpacked_size


def _rsc85_page_sizes(total_size: int, page0_count: int, page1_count: int, page2_count: int, object_start_page: int) -> list[int]:
    sizes: list[int] = []
    next_size = 524288
    remaining = total_size
    counts = [page0_count, page1_count, page2_count, 2_147_483_647]
    for count in counts:
        for _ in range(count):
            if remaining == 0:
                break
            while next_size > remaining:
                next_size >>= 1
            sizes.append(next_size)
            remaining -= next_size
        next_size >>= 1
    return sizes


def rsc85_object_start(flag1: int, flag2: int) -> int:
    """Mirror Magic RDR's RSC85 object-start calculation."""
    total_v = (flag2 & 0x3FFF) << 12
    object_start_page = (flag2 >> 28) & 7
    object_start_page_size = 4096 << object_start_page
    sizes = _rsc85_page_sizes(
        total_v,
        (flag1 >> 14) & 3,
        (flag1 >> 8) & 0x3F,
        flag1 & 0xFF,
        object_start_page,
    )
    offset = 0
    for size in sizes:
        if size == object_start_page_size:
            return offset
        offset += size
    return 0


def _read_u32_be(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _write_u32_le(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value & 0xFFFFFFFF)


def _script_offset(value: int) -> int:
    return value & 0x0FFFFFFF if (value >> 28) == 5 else value


def xenon_script_tables_to_pc_little(decoded: bytes, flag1: int, flag2: int) -> tuple[bytes, dict[str, Any]]:
    """Convert XENON script tables to PC/Switch table endianness.

    Magic RDR's script decompiler always treats bytecode operands as big-endian
    byte sequences, even when its container/platform mode is Switch. The parts
    that change between XENON and PC/Switch are the script header, page-pointer
    table, native hash table, and static table words read through IOReader.
    """
    out = bytearray(decoded)
    object_start = rsc85_object_start(flag1, flag2)
    report: dict[str, Any] = {
        "pc_table_normalization": "xenon-big-tables-to-pc-little",
        "object_start": object_start,
        "converted_header_words": 0,
        "converted_page_pointer_words": 0,
        "converted_native_hash_words": 0,
        "converted_static_words": 0,
        "warning": "",
    }
    if object_start < 0 or object_start + 40 > len(out):
        raise ResourceError(f"script object_start {object_start} is outside decoded payload size {len(out)}")

    header_words = [_read_u32_be(out, object_start + i * 4) for i in range(10)]
    code_size = header_words[3]
    parameter_count = header_words[4]
    static_count = header_words[5]
    static_pointer = _script_offset(header_words[6])
    native_count = _script_offset(header_words[8])
    native_pointer = _script_offset(header_words[9])
    page_pointer_table = _script_offset(header_words[2])
    page_count = (code_size + 16383) // 16384 if code_size > 0 else 0
    report.update(
        {
            "script_header_words_be": [f"0x{x:08X}" for x in header_words],
            "code_size": code_size,
            "parameter_count": parameter_count,
            "static_count": static_count,
            "static_pointer": static_pointer,
            "native_count": native_count,
            "native_pointer": native_pointer,
            "page_pointer_table": page_pointer_table,
            "page_count": page_count,
        }
    )
    if code_size <= 0 or code_size > len(out):
        raise ResourceError(f"implausible XENON script code size {code_size}")
    if static_count < 0 or static_count > 1_000_000:
        raise ResourceError(f"implausible XENON static count {static_count}")
    if native_count < 0 or native_count > 100_000:
        raise ResourceError(f"implausible XENON native count {native_count}")
    for label, offset, count in (
        ("page_pointer_table", page_pointer_table, page_count),
        ("native_pointer", native_pointer, native_count),
        ("static_pointer", static_pointer, static_count),
    ):
        if count and (offset < 0 or offset + count * 4 > len(out)):
            raise ResourceError(f"{label} range {offset}+{count * 4} is outside decoded payload size {len(out)}")

    for i, value in enumerate(header_words):
        _write_u32_le(out, object_start + i * 4, value)
    report["converted_header_words"] = len(header_words)

    for i in range(page_count):
        _write_u32_le(out, page_pointer_table + i * 4, _read_u32_be(out, page_pointer_table + i * 4))
    report["converted_page_pointer_words"] = page_count

    for i in range(native_count):
        _write_u32_le(out, native_pointer + i * 4, _read_u32_be(out, native_pointer + i * 4))
    report["converted_native_hash_words"] = native_count

    for i in range(static_count):
        _write_u32_le(out, static_pointer + i * 4, _read_u32_be(out, static_pointer + i * 4))
    report["converted_static_words"] = static_count

    return bytes(out), report


def run_lzx_bridge(bridge: Path, decrypted_payload: bytes, expected_size: int, temp_dir: Path) -> tuple[bytes, dict[str, Any]]:
    input_path = temp_dir / "payload_decrypted_lzx.bin"
    output_path = temp_dir / "payload_decoded.bin"
    input_path.write_bytes(decrypted_payload)
    command = [str(bridge), "decompress", str(input_path), str(output_path), str(expected_size), "--skip", "8"]
    proc = subprocess.run(command, cwd=str(bridge.parent), text=True, capture_output=True)
    report = {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    if proc.returncode != 0 or not output_path.exists():
        raise ResourceError("xcompress bridge failed: " + (proc.stderr.strip() or proc.stdout.strip()))
    decoded = output_path.read_bytes()
    return decoded, report


def build_pc_wsc(normalized_header: bytes, decoded: bytes, key: bytes, source_path: Path) -> tuple[bytes, dict[str, Any]]:
    variants = zstd_compress_variants(decoded)
    compressed_size, codec, compressed = variants[0]
    encrypted = aes_crypt_16_passes(compressed, key, decrypt=False)
    output = normalized_header[:16] + encrypted
    reopened = open_script_from_bytes(output, source_path.with_suffix(".wsc"), key, originally_xsc=False)
    validate_ok = reopened.decoded == decoded
    if not validate_ok:
        raise ResourceError("PC WSC candidate did not reopen to the decoded Xbox payload")
    return output, {
        "codec": codec,
        "compressed_size": compressed_size,
        "decoded_size": len(decoded),
        "output_size": len(output),
        "decoded_sha256": sha256(decoded),
        "output_sha256": sha256(output),
        "validate_ok": validate_ok,
        "runtime_note": "PC wrapper validates and script tables are PC/Switch-endian. Runtime compatibility is still game-unproven.",
    }


def convert_one(path: Path, source_root: Path, out_root: Path, bridge: Path, key: bytes, keep_decoded: bool) -> dict[str, Any]:
    rel = relative_under(path, source_root)
    dst = out_root / rel.with_suffix(".wsc")
    decoded_dst = out_root / "_decoded_xbox_payloads" / rel.with_suffix(".decoded.bin")
    rec: dict[str, Any] = {
        "source": str(path),
        "relative_path": str(rel).replace("\\", "/"),
        "source_size": path.stat().st_size,
        "source_sha1": sha1_file(path),
        "output": str(dst),
        "output_relative_path": str(relative_under(dst, out_root)).replace("\\", "/"),
        "status": "not_attempted",
        "error": "",
        "decoded_size": 0,
        "decoded_sha256": "",
        "output_size": 0,
        "output_sha1": "",
        "bridge_stdout": "",
        "bridge_stderr": "",
        "runtime_compatibility": "unproven",
    }
    data = path.read_bytes()
    if not data.startswith(b"\x85CSR"):
        rec.update({"status": "blocked_not_xsc_swapped_rsc85", "error": "expected 85 43 53 52 header"})
        return rec

    try:
        normalized = header_only_normalize_xsc(data)
        expected_size = expected_unpacked_size(normalized)
        decrypted_payload = aes_crypt_16_passes(normalized[16:], key, decrypt=True)
        if len(decrypted_payload) < 8:
            raise ResourceError("decrypted payload too small for LZX wrapper")
        magic, compressed_size = struct.unpack_from(">II", decrypted_payload, 0)
        rec["lzx_magic"] = f"0x{magic:08X}"
        rec["lzx_compressed_size"] = compressed_size
        rec["expected_unpacked_size"] = expected_size
        if magic != XBOX_LZX_MAGIC:
            raise ResourceError(f"decrypted payload did not start with Xbox LZX wrapper, got 0x{magic:08X}")
        if compressed_size != len(decrypted_payload) - 8:
            rec["warning"] = f"LZX size header {compressed_size} did not match payload remainder {len(decrypted_payload) - 8}"

        with tempfile.TemporaryDirectory(prefix="codered_xsc_lzx_") as tmp:
            decoded, bridge_report = run_lzx_bridge(bridge, decrypted_payload, expected_size, Path(tmp))
        rec["bridge_stdout"] = bridge_report["stdout"]
        rec["bridge_stderr"] = bridge_report["stderr"]

        _, flag1, flag2 = struct.unpack_from("<III", normalized, 4)
        pc_decoded, endian_report = xenon_script_tables_to_pc_little(decoded, flag1, flag2)
        output, pack_report = build_pc_wsc(normalized[:16], pc_decoded, key, path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(output)
        if keep_decoded:
            decoded_dst.parent.mkdir(parents=True, exist_ok=True)
            decoded_dst.write_bytes(pc_decoded)
            rec["decoded_output"] = str(decoded_dst)

        rec.update(pack_report)
        rec.update(endian_report)
        rec.update(
            {
                "status": "pc_wsc_magicrdr_table_candidate_runtime_unproven",
                "output_size": len(output),
                "output_sha1": sha1_file(dst),
            }
        )
    except Exception as exc:
        rec.update({"status": "blocked", "error": str(exc)})
    return rec


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_reports(report_root: Path, out_root: Path, rows: list[dict[str, Any]]) -> None:
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "xsc_lzx_to_pc_wsc_report.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_csv(report_root / "xsc_lzx_to_pc_wsc_report.csv", rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = [
        "# XSC LZX to PC WSC Candidate Conversion",
        "",
        "No live game files or RPFs were modified.",
        "",
        f"- Output folder: `{out_root}`",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This pass performs a real unwrap/decrypt/LZX-decompress/Zstandard-rewrap cycle for XENON `.xsc` resources. "
            "A successful row means Code RED can reopen the produced PC `.wsc` wrapper and recover the same decoded payload.",
            "",
            "Runtime compatibility is still not guaranteed. The decoded script payload came from Xbox/XENON, so bytecode endianness, native table layout, and platform assumptions must be tested before using these in a gameplay RPF.",
            "",
            "## Core Multiplayer Scripts",
            "",
        ]
    )
    for row in rows:
        stem = Path(row["relative_path"]).stem.lower()
        if stem in {"freemode", "multiplayer_system_thread", "multiplayer_update_thread", "pr_multiplayer", "mp_idle", "deathmatch", "ctf_base_game", "mp_actorpicker"}:
            lines.append(f"- `{row['relative_path']}` -> `{row['status']}` size=`{row.get('output_size', 0)}` error=`{row.get('error', '')}`")
    (report_root / "xsc_lzx_to_pc_wsc_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert XENON .xsc files into PC-wrapped .wsc candidates using xcompress32.")
    parser.add_argument("--source", default=str(DEFAULT_XSC_SOURCE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--reports", default=str(DEFAULT_REPORTS))
    parser.add_argument("--bridge", default=str(DEFAULT_BRIDGE))
    parser.add_argument("--rdr-exe", default=str(ROOT.parent / "RDR.exe"))
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--keep-decoded", action="store_true", help="Also write decoded Xbox script payloads for inspection. Do not commit these.")
    parser.add_argument("--include-stem", action="append", default=[], help="Convert only XSC files whose stem matches this value. May be repeated.")
    parser.add_argument("--core-subset", action="store_true", help="Convert only multiplayer_update_thread, freemode, pr_multiplayer, and multiplayer_system_thread.")
    args = parser.parse_args()

    source = Path(args.source)
    out_root = Path(args.out)
    report_root = Path(args.reports)
    bridge = Path(args.bridge)
    if not bridge.exists():
        raise SystemExit(f"Missing xcompress bridge: {bridge}")
    if not DEFAULT_BRIDGE_DLL.exists() and bridge == DEFAULT_BRIDGE:
        raise SystemExit(f"Missing xcompress32.dll beside bridge: {DEFAULT_BRIDGE_DLL}")

    if args.clean and out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    key, attempts = resolve_aes_key(KeyOptions(rdr_exe=args.rdr_exe))
    if key is None:
        raise SystemExit("Could not resolve RDR AES key from --rdr-exe or environment")

    include_stems = set(args.include_stem or [])
    if args.core_subset:
        include_stems.update({"multiplayer_update_thread", "freemode", "pr_multiplayer", "multiplayer_system_thread"})
    rows = [convert_one(path, source, out_root, bridge, key, args.keep_decoded) for path in filter_xsc(collect_xsc(source), include_stems)]
    write_reports(report_root, out_root, rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(json.dumps({"status": "complete", "rows": len(rows), "counts": counts, "out": str(out_root), "reports": str(report_root), "key_attempts": attempts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
