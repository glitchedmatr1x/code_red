#!/usr/bin/env python3
"""Code RED Vehicle Script Lab.

Read-first helper for RDR1 compiled script/resource research.
It does not claim full WSC decompile/recompile. It extracts/inventories/scans
compiled scripts and resource payloads for strings, target names, hashes, and
vehicle activation clues, then generates reports to guide ASI/ScriptHook work.
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
import traceback
import zlib
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

try:
    import zstandard as zstd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "vehicle_script_lab"
DEFAULT_SCRIPT_EXTENSIONS = {".wsc", ".sco", ".xsc", ".csc"}
TEXTISH_EXTENSIONS = {".xml", ".txt", ".refgroup", ".cfg", ".csv", ".tune", ".vehsim", ".vehmodel", ".vehinput", ".vehgyro", ".vehstuck"}

DEFAULT_TARGETS = [
    # core scripts and vehicle systems
    "playercar", "playercar.wsc", "beat_crime_wagonthief", "beat_crime_wagonthief.wsc",
    "gen_vehicle_brain", "gen_vehicle_brain.wsc", "vehicle_generator", "vehicle_generator.wsc",
    "vehiclegenerator", "vehicle", "vehicles", "wagon", "wagons", "coach", "coaches", "cart", "carts", "stagecoach",
    "wagonthief", "wagon_thief", "beat", "beat_crime", "crime_wagon", "carriage", "buggy",
    "car01x", "truck01x", "stagecoachgatling01x", "horse", "mount", "driver", "pilot", "seat",
    # assets/templates/tune layers
    "template_vehicle", "template_vehiclecar", "template_vehicletruck", "template_vehiclewagon",
    "template_vehiclestagecoach", "vehsim", "vehmodel", "vehinput", "vehgyro", "vehstuck",
    "car01x.vehsim", "truck01x.vehsim", "car01x.vehmodel", "truck01x.vehmodel",
    "t:/rdr2/assets/entity/car01x", "t:/rdr2/assets/entity/truck01x",
    "t:/rdr2/entity/car01x", "t:/rdr2/entity/truck01x",
    # native/behavior clue words
    "create_actor", "create_vehicle", "vehicle_attach", "actor", "layout", "spawn", "control",
    "usecontext", "enter", "exit", "drive", "driving", "brake", "steer", "steering", "mission", "crime", "thief",
    "get_vehicle", "set_vehicle", "mount_vehicle", "put_actor", "actor_in_vehicle", "is_actor_in_vehicle",
    "seat_index", "vehicle_seat", "anim_vehicle", "vehicle_brain", "vehicle_ai",
]

PRIORITY_SCRIPT_NAMES = [
    "playercar",
    "beat_crime_wagonthief",
    "wagonthief",
    "vehicle_generator",
    "gen_vehicle_brain",
    "vehicle",
    "wagon",
    "coach",
    "cart",
    "car",
    "truck",
]

PRINTABLE_RE = re.compile(rb"[\x20-\x7E]{4,}")

@dataclass
class StringHit:
    offset: int
    encoding: str
    text: str

@dataclass
class TargetHit:
    target: str
    kind: str
    offset: int
    offset_hex: str
    detail: str


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def safe_write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys or ["empty"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


RSC_MAGICS = {
    b"RSC\x05": "RSC05",
    b"RSC\x06": "RSC06",
    b"RSC\x85": "RSC85",
    b"RSC\x86": "RSC86",
}


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


def detect_rsc(data: bytes) -> dict | None:
    """Detect RDR1 RSC resource wrappers used by WSC/WFT/WGD etc."""
    if len(data) < 16:
        return None
    magic = RSC_MAGICS.get(data[:4])
    if not magic:
        return None
    resource_type = struct.unpack_from("<I", data, 4)[0]
    flag1 = struct.unpack_from("<i", data, 8)[0]
    flag2: int | None = None
    header_size = 12
    if magic in {"RSC85", "RSC86"}:
        flag2 = struct.unpack_from("<i", data, 12)[0]
        header_size = 16
    if magic in {"RSC85", "RSC86"}:
        virtual_size, physical_size = _rsc85_sizes(flag2)
    else:
        virtual_size, physical_size = _rsc05_sizes(flag1)
    payload = data[header_size:]
    compression = "zstd" if payload.startswith(b"\x28\xb5\x2f\xfd") else "zlib-or-raw"
    expected = (virtual_size or 0) + (physical_size or 0)
    return {
        "magic": magic,
        "resource_type": resource_type,
        "flag1": flag1,
        "flag2": flag2,
        "header_size": header_size,
        "compressed_size": len(payload),
        "virtual_size": virtual_size,
        "physical_size": physical_size,
        "expected_unpacked_size": expected or None,
        "payload_sha256": _sha256_bytes(payload),
        "compression": compression,
    }


def _zstd_cli() -> str | None:
    return shutil.which("zstd") or shutil.which("zstd.exe")


def zstd_decompress(data: bytes, expected_size: int | None = None) -> bytes:
    if zstd is not None:
        dctx = zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data)
        except Exception as exc:
            if expected_size and expected_size > 0:
                return dctx.decompress(data, max_output_size=expected_size)
            raise exc
    exe = _zstd_cli()
    if exe:
        with tempfile.TemporaryDirectory(prefix="codered_wsc_zstd_") as td:
            src = Path(td) / "in.zst"
            dst = Path(td) / "out.bin"
            src.write_bytes(data)
            proc = subprocess.run([exe, "-q", "-d", "-f", str(src), "-o", str(dst)], capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "zstd failed")
            return dst.read_bytes()
    raise RuntimeError("zstandard support unavailable. Install Python package 'zstandard' or put zstd.exe on PATH.")


def try_decompress_payload(payload: bytes, rsc: dict | None = None) -> tuple[bytes | None, str, str | None]:
    if not payload:
        return b"", "empty", None
    expected = None if not rsc else rsc.get("expected_unpacked_size")
    if payload.startswith(b"\x28\xb5\x2f\xfd"):
        try:
            return zstd_decompress(payload, expected), "zstd", None
        except Exception as exc:
            return None, "zstd", str(exc)
    for wbits, label in [(-15, "zlib-raw"), (15, "zlib"), (31, "gzip")]:
        try:
            return zlib.decompress(payload, wbits), label, None
        except Exception:
            pass
    return None, "raw-or-unknown", "payload is not recognized as zstd/zlib, or dependency is missing"


def prepare_analysis_bytes(data: bytes) -> tuple[bytes, dict]:
    """Return decompressed script payload when input is an RSC resource.

    v3 scanned the packed RSC85 wrapper, which made WSC strings look like noise.
    v4 decodes the wrapper first and stores enough metadata for honest reports.
    """
    rsc = detect_rsc(data)
    meta = {
        "input_is_rsc": bool(rsc),
        "payload_source": "raw-file",
        "codec": "none",
        "decompress_error": None,
        "raw_size": len(data),
        "analysis_size": len(data),
        "rsc": rsc,
    }
    if not rsc:
        return data, meta
    payload = data[int(rsc["header_size"]):]
    unpacked, codec, error = try_decompress_payload(payload, rsc)
    meta.update({"codec": codec, "decompress_error": error})
    if unpacked is None:
        meta["payload_source"] = "compressed-or-unknown"
        meta["analysis_size"] = len(payload)
        return payload, meta
    meta["payload_source"] = "rsc-decompressed"
    meta["analysis_size"] = len(unpacked)
    if rsc is not None:
        rsc["payload_unpacked_size"] = len(unpacked)
        rsc["payload_unpacked_sha256"] = _sha256_bytes(unpacked)
    return unpacked, meta


def read_analysis_bytes(path: Path) -> tuple[bytes, bytes, dict]:
    raw = path.read_bytes()
    analysis, meta = prepare_analysis_bytes(raw)
    return raw, analysis, meta


def jenkins_hash(text: str) -> int:
    """RAGE/Jenkins one-at-a-time style hash used for string-name clues.

    This is a research hint, not a guarantee every compiled WSC reference uses
    this exact representation.
    """
    h = 0
    for b in text.lower().encode("utf-8", errors="ignore"):
        h = (h + b) & 0xFFFFFFFF
        h = (h + ((h << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + ((h << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


def extract_ascii_strings(data: bytes, min_len: int = 4, limit: int = 20000) -> list[StringHit]:
    hits: list[StringHit] = []
    for match in PRINTABLE_RE.finditer(data):
        raw = match.group(0)
        if len(raw) < min_len:
            continue
        try:
            text = raw.decode("ascii")
        except Exception:
            continue
        hits.append(StringHit(match.start(), "ascii", text))
        if len(hits) >= limit:
            break
    return hits


def extract_utf16le_strings(data: bytes, min_chars: int = 4, limit: int = 20000) -> list[StringHit]:
    hits: list[StringHit] = []
    start: int | None = None
    chars: list[int] = []
    i = 0
    while i + 1 < len(data):
        code = data[i] | (data[i + 1] << 8)
        if 32 <= code <= 126:
            if start is None:
                start = i
                chars = []
            chars.append(code)
        else:
            if start is not None and len(chars) >= min_chars:
                hits.append(StringHit(start, "utf16le", "".join(chr(c) for c in chars)))
                if len(hits) >= limit:
                    break
            start = None
            chars = []
        i += 2
    if start is not None and len(chars) >= min_chars and len(hits) < limit:
        hits.append(StringHit(start, "utf16le", "".join(chr(c) for c in chars)))
    return hits




def printable_quality(text: str) -> dict:
    """Return coarse quality metrics for a printable run.

    WSC bytecode frequently produces accidental printable runs. Human-useful
    strings tend to have enough letters/digits, sane punctuation, and words or
    path separators. This is only a triage filter; raw strings are still exported.
    """
    if not text:
        return {"score": 0, "alnum_ratio": 0, "alpha_ratio": 0, "symbol_ratio": 1, "looks_human": False}
    total = len(text)
    alnum = sum(1 for c in text if c.isalnum())
    alpha = sum(1 for c in text if c.isalpha())
    spaces = sum(1 for c in text if c.isspace())
    sane_punct = sum(1 for c in text if c in "_-/\\:.@$#[](){}")
    symbols = total - alnum - spaces - sane_punct
    alnum_ratio = alnum / total
    alpha_ratio = alpha / total
    symbol_ratio = max(0, symbols) / total
    lower = text.lower()
    has_wordish = any(tok in lower for tok in [
        "vehicle", "wagon", "coach", "cart", "car", "truck", "horse", "actor", "script",
        "template", "vehsim", "vehmodel", "enter", "exit", "driver", "seat", "player",
        "t:/", "content/", "content\\", ".wsc", ".xml", ".vehsim", ".vehmodel"
    ])
    has_pathish = ("/" in text or "\\" in text or ":/" in lower or "." in text) and alpha >= 3
    repeated_noise = any(ch * 4 in text for ch in "!@#$%^&*~|`")
    score = 0
    if total >= 6: score += 1
    if alnum_ratio >= 0.55: score += 2
    if alpha_ratio >= 0.35: score += 1
    if symbol_ratio <= 0.25: score += 1
    if has_wordish: score += 5
    if has_pathish: score += 3
    if repeated_noise: score -= 2
    looks_human = score >= 4 and symbol_ratio <= 0.45
    return {
        "score": score,
        "alnum_ratio": round(alnum_ratio, 3),
        "alpha_ratio": round(alpha_ratio, 3),
        "symbol_ratio": round(symbol_ratio, 3),
        "looks_human": looks_human,
    }


def filter_humanish_strings(strings: Sequence[StringHit]) -> list[dict]:
    rows: list[dict] = []
    for h in strings:
        q = printable_quality(h.text)
        if q["looks_human"]:
            rows.append({
                "offset": h.offset,
                "offset_hex": f"0x{h.offset:X}",
                "encoding": h.encoding,
                "text": h.text,
                **q,
            })
    rows.sort(key=lambda r: (-int(r.get("score", 0)), int(r.get("offset", 0))))
    return rows


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    ent = 0.0
    n = len(data)
    for c in counts:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return round(ent, 4)


def profile_binary(data: bytes, chunk_size: int = 512) -> dict:
    chunks = []
    for off in range(0, len(data), chunk_size):
        chunk = data[off:off+chunk_size]
        chunks.append({
            "offset": off,
            "offset_hex": f"0x{off:X}",
            "size": len(chunk),
            "entropy": shannon_entropy(chunk),
            "zero_bytes": chunk.count(0),
            "printable_bytes": sum(1 for b in chunk if 32 <= b <= 126),
        })
    # aligned u32 frequency can expose VM opcode/immediate pools or repeated constants.
    freq: dict[int, int] = {}
    for off in range(0, len(data) - 3, 4):
        val = struct.unpack_from("<I", data, off)[0]
        freq[val] = freq.get(val, 0) + 1
    common = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:200]
    common_rows = [{"u32_hex": f"0x{v:08X}", "u32": v, "count": c} for v, c in common if c > 1]
    # Header/prefix bytes are useful while researching WSC containers.
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "prefix_hex": data[:128].hex(" ").upper(),
        "entropy_total": shannon_entropy(data),
        "chunk_size": chunk_size,
        "chunks": chunks,
        "common_aligned_u32": common_rows[:100],
        "notes": [
            "High entropy plus junk printable runs usually means the WSC needs bytecode/container parsing, not plain string scraping.",
            "Aligned u32 constants and chunk entropy are research clues, not proof of control flow.",
        ],
    }


def write_profile_outputs(input_path: Path, out_dir: Path) -> dict:
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw, data, script_meta = read_analysis_bytes(input_path)
    prof = profile_binary(data)
    prof["raw_size"] = len(raw)
    prof["analysis_payload_source"] = script_meta.get("payload_source")
    prof["rsc"] = script_meta.get("rsc")
    safe_write_json(out_dir / f"{input_path.name}.byte_profile.json", prof)
    write_csv(out_dir / f"{input_path.name}.entropy_chunks.csv", prof["chunks"])
    write_csv(out_dir / f"{input_path.name}.common_u32.csv", prof["common_aligned_u32"])
    if script_meta.get("input_is_rsc"):
        (out_dir / f"{input_path.name}.payload.bin").write_bytes(data)
    report = [
        f"# WSC Byte Profile: `{input_path.name}`",
        "",
        f"- Raw size: `{len(raw)}` bytes",
        f"- Analysis payload size: `{prof['size']}` bytes",
        f"- SHA256: `{prof['sha256']}`",
        f"- Payload source: `{script_meta.get('payload_source')}`",
        f"- Codec: `{script_meta.get('codec')}`",
        f"- Total entropy: `{prof['entropy_total']}`",
        "",
        "## Interpretation",
        "",
        "v4 profiles the decompressed RSC payload when possible. If payload entropy remains high and string hits are still weak, the remaining layer is compiled/encrypted VM bytecode rather than plain labels.",
        "",
        "## Outputs",
        "",
        f"- `{rel(out_dir / f'{input_path.name}.byte_profile.json')}`",
        f"- `{rel(out_dir / f'{input_path.name}.entropy_chunks.csv')}`",
        f"- `{rel(out_dir / f'{input_path.name}.common_u32.csv')}`",
    ]
    if script_meta.get("input_is_rsc"):
        report.append(f"- `{rel(out_dir / f'{input_path.name}.payload.bin')}`")
    (out_dir / f"{input_path.name}.byte_profile.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {
        "input": str(input_path),
        "name": input_path.name,
        "profile_json": rel(out_dir / f"{input_path.name}.byte_profile.json"),
        "entropy_csv": rel(out_dir / f"{input_path.name}.entropy_chunks.csv"),
        "common_u32_csv": rel(out_dir / f"{input_path.name}.common_u32.csv"),
        "payload_bin": rel(out_dir / f"{input_path.name}.payload.bin") if script_meta.get("input_is_rsc") else "",
        "report_md": rel(out_dir / f"{input_path.name}.byte_profile.md"),
        "summary": {
            "raw_size": len(raw),
            "analysis_size": prof["size"],
            "sha256": prof["sha256"],
            "entropy_total": prof["entropy_total"],
            "payload_source": script_meta.get("payload_source"),
            "codec": script_meta.get("codec"),
            "decompress_error": script_meta.get("decompress_error"),
            "prefix_hex": prof["prefix_hex"],
            "rsc": script_meta.get("rsc"),
        },
    }


def find_all(data: bytes, needle: bytes, case_sensitive: bool = False) -> list[int]:
    if not needle:
        return []
    hay = data if case_sensitive else data.lower()
    ned = needle if case_sensitive else needle.lower()
    offsets = []
    start = 0
    while True:
        idx = hay.find(ned, start)
        if idx < 0:
            break
        offsets.append(idx)
        start = idx + 1
    return offsets


def scan_targets(data: bytes, targets: Sequence[str], case_sensitive: bool = False) -> tuple[list[TargetHit], list[dict]]:
    hits: list[TargetHit] = []
    hash_rows: list[dict] = []
    for target in targets:
        if not target:
            continue
        # raw ASCII / UTF16 references.
        for off in find_all(data, target.encode("ascii", errors="ignore"), case_sensitive=case_sensitive):
            hits.append(TargetHit(target, "ascii", off, f"0x{off:X}", target))
        utf = target.encode("utf-16le", errors="ignore")
        for off in find_all(data, utf, case_sensitive=case_sensitive):
            hits.append(TargetHit(target, "utf16le", off, f"0x{off:X}", target))
        # Jenkins hash hits, both byte orders, because script/resource blobs can vary.
        h = jenkins_hash(target)
        le = struct.pack("<I", h)
        be = struct.pack(">I", h)
        le_hits = find_all(data, le, case_sensitive=True)
        be_hits = find_all(data, be, case_sensitive=True)
        hash_rows.append({
            "target": target,
            "jenkins_hex": f"0x{h:08X}",
            "little_endian_hits": len(le_hits),
            "big_endian_hits": len(be_hits),
            "first_little_endian_offsets": ";".join(f"0x{o:X}" for o in le_hits[:20]),
            "first_big_endian_offsets": ";".join(f"0x{o:X}" for o in be_hits[:20]),
        })
        for off in le_hits:
            hits.append(TargetHit(target, "jenkins32_le", off, f"0x{off:X}", f"0x{h:08X}"))
        for off in be_hits:
            hits.append(TargetHit(target, "jenkins32_be", off, f"0x{off:X}", f"0x{h:08X}"))
    hits.sort(key=lambda x: (x.offset, x.target, x.kind))
    return hits, hash_rows


def classify_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in DEFAULT_SCRIPT_EXTENSIONS:
        return "compiled-script"
    if ext in TEXTISH_EXTENSIONS:
        return "text-or-config"
    if ext in {".rpf"}:
        return "rpf-archive"
    return "binary-resource"


def read_targets_file(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_TARGETS
    text = path.read_text(encoding="utf-8", errors="ignore")
    targets = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        targets.append(line)
    return targets or DEFAULT_TARGETS


def scan_file(input_path: Path, out_dir: Path, targets: Sequence[str], min_string: int = 4) -> dict:
    ensure_dirs()
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_data, data, script_meta = read_analysis_bytes(input_path)
    ascii_hits = extract_ascii_strings(data, min_len=min_string)
    utf_hits = extract_utf16le_strings(data, min_chars=min_string)
    target_hits, hash_rows = scan_targets(data, targets)

    all_strings = ascii_hits + utf_hits
    strings_rows = [asdict(h) | {"offset_hex": f"0x{h.offset:X}", **printable_quality(h.text)} for h in all_strings]
    humanish_rows = filter_humanish_strings(all_strings)
    target_rows = [asdict(h) for h in target_hits]
    string_texts = {h.text for h in all_strings}
    likely_vehicle_strings = sorted([
        s for s in string_texts
        if any(k in s.lower() for k in ["vehicle", "wagon", "coach", "cart", "car", "truck", "vehsim", "vehmodel", "seat", "driver", "pilot", "mount"])
    ])[:500]

    base = input_path.name
    write_csv(out_dir / f"{base}.strings.csv", strings_rows, ["offset", "offset_hex", "encoding", "text", "score", "alnum_ratio", "alpha_ratio", "symbol_ratio", "looks_human"])
    write_csv(out_dir / f"{base}.humanish_strings.csv", humanish_rows, ["offset", "offset_hex", "encoding", "text", "score", "alnum_ratio", "alpha_ratio", "symbol_ratio", "looks_human"])
    write_csv(out_dir / f"{base}.target_hits.csv", target_rows, ["target", "kind", "offset", "offset_hex", "detail"])
    write_csv(out_dir / f"{base}.hash_probe.csv", hash_rows)
    profile_summary = None
    if input_path.suffix.lower() in DEFAULT_SCRIPT_EXTENSIONS:
        profile_summary = write_profile_outputs(input_path, out_dir).get("summary")
    if script_meta.get("input_is_rsc"):
        (out_dir / f"{base}.payload.bin").write_bytes(data)
    summary = {
        "input": str(input_path),
        "name": input_path.name,
        "kind": classify_file(input_path),
        "raw_size": len(raw_data),
        "analysis_size": len(data),
        "size": len(data),
        "sha256": _sha256_bytes(data),
        "raw_sha256": _sha256_bytes(raw_data),
        "payload_source": script_meta.get("payload_source"),
        "codec": script_meta.get("codec"),
        "decompress_error": script_meta.get("decompress_error"),
        "rsc": script_meta.get("rsc"),
        "ascii_strings": len(ascii_hits),
        "utf16le_strings": len(utf_hits),
        "humanish_strings": len(humanish_rows),
        "string_signal_quality": "good" if humanish_rows or target_hits else "mostly-bytecode-noise",
        "target_hits": len(target_hits),
        "hash_targets_checked": len(hash_rows),
        "targets_with_hits": sorted({h.target for h in target_hits}),
        "likely_vehicle_strings_sample": likely_vehicle_strings[:100],
        "outputs": {
            "strings_csv": rel(out_dir / f"{base}.strings.csv"),
            "humanish_strings_csv": rel(out_dir / f"{base}.humanish_strings.csv"),
            "byte_profile_json": rel(out_dir / f"{base}.byte_profile.json") if profile_summary else "",
            "entropy_chunks_csv": rel(out_dir / f"{base}.entropy_chunks.csv") if profile_summary else "",
            "target_hits_csv": rel(out_dir / f"{base}.target_hits.csv"),
            "hash_probe_csv": rel(out_dir / f"{base}.hash_probe.csv"),
            "payload_bin": rel(out_dir / f"{base}.payload.bin") if script_meta.get("input_is_rsc") else "",
            "summary_json": rel(out_dir / f"{base}.summary.json"),
            "report_md": rel(out_dir / f"{base}.report.md"),
        },
        "byte_profile": profile_summary,
        "guardrails": [
            "read-only scan",
            "humanish string filtering separates useful strings from accidental bytecode printable runs",
            "no compiled script decompile/recompile claimed",
            "hash hits and byte profiles are research clues, not proof of control flow",
        ],
    }
    safe_write_json(out_dir / f"{base}.summary.json", summary)
    report = [
        f"# Code RED Vehicle Script Scan: `{input_path.name}`",
        "",
        f"- Kind: `{summary['kind']}`",
        f"- Raw size: `{summary['raw_size']}` bytes",
        f"- Analysis payload size: `{summary['analysis_size']}` bytes",
        f"- Payload source: `{summary['payload_source']}`",
        f"- Codec: `{summary['codec']}`",
        f"- ASCII strings: `{summary['ascii_strings']}`",
        f"- UTF-16LE strings: `{summary['utf16le_strings']}`",
        f"- Humanish strings: `{summary['humanish_strings']}`",
        f"- String signal quality: `{summary['string_signal_quality']}`",
        f"- Target/hash hits: `{summary['target_hits']}`",
        "",
        "## Targets with hits",
        "",
    ]
    if summary["targets_with_hits"]:
        report.extend(f"- `{t}`" for t in summary["targets_with_hits"][:200])
    else:
        report.append("No default vehicle targets were found directly. Check hash_probe.csv for hash candidates.")
    report.extend(["", "## Likely vehicle strings sample", ""])
    if likely_vehicle_strings:
        report.extend(f"- `{s}`" for s in likely_vehicle_strings[:100])
    else:
        report.append("No obvious vehicle strings surfaced from printable string scan.")
    (out_dir / f"{base}.report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


def scan_folder(input_dir: Path, out_dir: Path, targets: Sequence[str], include_exts: Sequence[str] | None = None) -> dict:
    input_dir = input_dir.resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    exts = {e.lower() if e.startswith(".") else "." + e.lower() for e in include_exts} if include_exts else None
    files = [p for p in input_dir.rglob("*") if p.is_file() and (exts is None or p.suffix.lower() in exts)]
    summaries = []
    for p in files:
        relp = p.relative_to(input_dir).as_posix().replace("/", "__")
        try:
            summaries.append(scan_file(p, out_dir / "files" / relp, targets))
        except Exception as exc:
            summaries.append({"input": str(p), "error": str(exc)})
    aggregate = {
        "input_dir": str(input_dir),
        "out_dir": str(out_dir),
        "files_scanned": len(files),
        "files_with_hits": sum(1 for s in summaries if s.get("target_hits", 0) > 0),
        "summaries": summaries,
    }
    safe_write_json(out_dir / "folder_scan_summary.json", aggregate)
    rows = []
    for s in summaries:
        rows.append({
            "name": s.get("name", Path(str(s.get("input", ""))).name),
            "input": s.get("input"),
            "kind": s.get("kind", ""),
            "size": s.get("size", ""),
            "target_hits": s.get("target_hits", ""),
            "targets_with_hits": ";".join(s.get("targets_with_hits", [])) if isinstance(s.get("targets_with_hits"), list) else "",
            "error": s.get("error", ""),
        })
    write_csv(out_dir / "folder_scan_summary.csv", rows)
    return aggregate


def load_workbench_backend():
    workbench = ROOT / "python_workbench.py"
    if not workbench.exists():
        raise FileNotFoundError(f"Missing Code RED python_workbench.py at {workbench}")
    spec = importlib.util.spec_from_file_location("codered_vehicle_lab_workbench", workbench)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {workbench}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def scan_rpf(archive: Path, out_dir: Path, targets: Sequence[str], include_exts: Sequence[str] | None = None, max_files: int = 5000) -> dict:
    archive = archive.resolve()
    if not archive.exists():
        raise FileNotFoundError(archive)
    out_dir.mkdir(parents=True, exist_ok=True)
    wb = load_workbench_backend()
    if not hasattr(wb, "parse_rpf6"):
        raise RuntimeError("python_workbench.py does not expose parse_rpf6")
    info = wb.parse_rpf6(archive)
    if info is None:
        raise ValueError(f"Not a readable RPF6 archive: {archive}")
    exts = {e.lower() if e.startswith(".") else "." + e.lower() for e in include_exts} if include_exts else DEFAULT_SCRIPT_EXTENSIONS
    entries = []
    for ent in info.get("entries", []):
        if ent.get("type") != "file":
            continue
        ext = str(ent.get("extension") or Path(str(ent.get("name") or "")).suffix).lower()
        name = str(ent.get("name") or "")
        path = str(ent.get("path") or name)
        if ext in exts or any(name.lower().endswith(e) for e in exts):
            entries.append(ent)
    entries = entries[:max_files]
    extract_dir = out_dir / "extracted_scripts"
    extract_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for ent in entries:
        name = str(ent.get("name") or f"entry_{ent.get('index')}")
        path = str(ent.get("path") or name).replace("\\", "/")
        safe_name = f"{ent.get('index')}_{path}".replace("/", "__").replace(":", "_")
        target_path = extract_dir / safe_name
        try:
            if hasattr(wb, "extract_rpf_entry"):
                data = wb.extract_rpf_entry(archive, ent)
            else:
                raise RuntimeError("python_workbench.py does not expose extract_rpf_entry")
            target_path.write_bytes(data)
            summaries.append(scan_file(target_path, out_dir / "scans" / safe_name, targets))
        except Exception as exc:
            summaries.append({"entry": ent, "output": str(target_path), "error": str(exc)})
    aggregate = {
        "archive": str(archive),
        "entry_count": info.get("entry_count"),
        "matched_script_entries": len(entries),
        "files_scanned": len(summaries),
        "files_with_hits": sum(1 for s in summaries if s.get("target_hits", 0) > 0),
        "out_dir": str(out_dir),
        "extract_dir": str(extract_dir),
        "summaries": summaries,
    }
    safe_write_json(out_dir / "rpf_script_scan_summary.json", aggregate)
    write_csv(out_dir / "rpf_script_entries.csv", [{
        "index": e.get("index"),
        "name": e.get("name"),
        "path": e.get("path"),
        "extension": e.get("extension"),
        "offset": e.get("offset"),
        "size_in_archive": e.get("size_in_archive"),
        "total_size": e.get("total_size"),
        "is_resource": e.get("is_resource"),
        "is_compressed": e.get("is_compressed"),
    } for e in entries])
    return aggregate


def compare_files(left: Path, right: Path, out_dir: Path, targets: Sequence[str]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    left = left.resolve()
    right = right.resolve()
    left_summary = scan_file(left, out_dir / "left", targets)
    right_summary = scan_file(right, out_dir / "right", targets)
    left_sha = sha256_file(left)
    right_sha = sha256_file(right)
    duplicate_inputs = left_sha == right_sha

    def load_strings(path: Path) -> tuple[set[str], set[str]]:
        _raw, data, _meta = read_analysis_bytes(path)
        all_hits = extract_ascii_strings(data) + extract_utf16le_strings(data)
        raw = {h.text for h in all_hits}
        human = {r["text"] for r in filter_humanish_strings(all_hits)}
        return raw, human

    lset, lhuman = load_strings(left)
    rset, rhuman = load_strings(right)
    shared = sorted(lset & rset)
    left_only = sorted(lset - rset)
    right_only = sorted(rset - lset)
    human_shared = sorted(lhuman & rhuman)
    human_left_only = sorted(lhuman - rhuman)
    human_right_only = sorted(rhuman - lhuman)
    result = {
        "left": str(left),
        "right": str(right),
        "left_sha256": left_sha,
        "right_sha256": right_sha,
        "duplicate_inputs": duplicate_inputs,
        "duplicate_warning": (
            "The two compared files are byte-identical; this is not a useful behavior comparison. "
            "Find/extract the real distinct script before drawing conclusions."
            if duplicate_inputs else ""
        ),
        "left_summary": left_summary,
        "right_summary": right_summary,
        "shared_strings_count": len(shared),
        "left_only_strings_count": len(left_only),
        "right_only_strings_count": len(right_only),
        "human_shared_strings_count": len(human_shared),
        "human_left_only_strings_count": len(human_left_only),
        "human_right_only_strings_count": len(human_right_only),
        "compare_quality": "low-direct-string-signal" if not human_shared and not human_left_only and not human_right_only else "humanish-string-signal-present",
        "shared_vehicle_strings": [s for s in human_shared if any(k in s.lower() for k in ["vehicle", "wagon", "coach", "car", "truck", "vehsim", "seat", "driver"])][:500],
        "left_only_humanish_sample": human_left_only[:500],
        "right_only_humanish_sample": human_right_only[:500],
        "left_only_raw_sample": left_only[:200],
        "right_only_raw_sample": right_only[:200],
        "guardrails": [
            "read-only compare",
            "SHA256 duplicate detection is included",
            "no compiled script decompile/recompile claimed",
        ],
    }
    safe_write_json(out_dir / "compare_summary.json", result)
    write_csv(out_dir / "shared_strings.csv", [{"text": x} for x in shared[:5000]])
    write_csv(out_dir / "left_only_strings.csv", [{"text": x} for x in left_only[:5000]])
    write_csv(out_dir / "right_only_strings.csv", [{"text": x} for x in right_only[:5000]])
    write_csv(out_dir / "human_shared_strings.csv", [{"text": x} for x in human_shared[:5000]])
    write_csv(out_dir / "human_left_only_strings.csv", [{"text": x} for x in human_left_only[:5000]])
    write_csv(out_dir / "human_right_only_strings.csv", [{"text": x} for x in human_right_only[:5000]])
    write_profile_outputs(left, out_dir / "left_profile")
    write_profile_outputs(right, out_dir / "right_profile")
    (out_dir / "compare_report.md").write_text(
        "# Code RED Vehicle Script Compare\n\n"
        f"Left: `{left}`\n\n"
        f"Right: `{right}`\n\n"
        f"Left SHA256: `{left_sha}`\n\n"
        f"Right SHA256: `{right_sha}`\n\n"
        f"Duplicate inputs: `{duplicate_inputs}`\n\n"
        + (f"⚠️ {result['duplicate_warning']}\n\n" if duplicate_inputs else "")
        + f"Shared raw strings: `{len(shared)}`\n\n"
        + f"Shared humanish strings: `{len(human_shared)}`\n\n"
        + f"Left-only humanish strings: `{len(human_left_only)}`\n\n"
        + f"Right-only humanish strings: `{len(human_right_only)}`\n\n"
        + f"Compare quality: `{result['compare_quality']}`\n",
        encoding="utf-8",
    )
    return result


def find_script_candidates(archive: Path, out_dir: Path, queries: Sequence[str], include_exts: Sequence[str] | None = None, extract: bool = False) -> dict:
    """Find likely scripts/resources by internal RPF path/name and optional string scan.

    This is for locating the real playercar/wagonthief script instead of relying
    on manually copied imports. It is read-only unless --extract is provided, and
    even then it only extracts to the report folder.
    """
    archive = archive.resolve()
    if not archive.exists():
        raise FileNotFoundError(archive)
    out_dir.mkdir(parents=True, exist_ok=True)
    wb = load_workbench_backend()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise ValueError(f"Not a readable RPF6 archive: {archive}")
    exts = {e.lower() if e.startswith(".") else "." + e.lower() for e in include_exts} if include_exts else (DEFAULT_SCRIPT_EXTENSIONS | TEXTISH_EXTENSIONS)
    qnorm = [q.lower() for q in queries if q]
    rows: list[dict] = []
    extract_dir = out_dir / "candidates"
    if extract:
        extract_dir.mkdir(parents=True, exist_ok=True)
    for ent in info.get("entries", []):
        if ent.get("type") != "file":
            continue
        name = str(ent.get("name") or "")
        path = str(ent.get("path") or name).replace("\\", "/")
        ext = str(ent.get("extension") or Path(name).suffix).lower()
        full = f"{path} {name} {ext}".lower()
        name_hits = [q for q in qnorm if q in full]
        if not name_hits and ext not in exts:
            continue
        string_hits: list[str] = []
        extracted_to = ""
        sha = ""
        scanned = False
        if name_hits or ext in exts:
            try:
                data = wb.extract_rpf_entry(archive, ent)
                scanned = True
                sha = hashlib.sha256(data).hexdigest().upper()
                hay = data.lower()
                string_hits = [q for q in qnorm if q.encode("ascii", errors="ignore") in hay]
                if extract and (name_hits or string_hits):
                    safe_name = f"{ent.get('index')}_{path}".replace("/", "__").replace(":", "_")
                    target = extract_dir / safe_name
                    target.write_bytes(data)
                    extracted_to = rel(target)
            except Exception as exc:
                string_hits = [f"extract_error:{exc}"]
        score = len(name_hits) * 10 + len([h for h in string_hits if not h.startswith("extract_error:")]) * 3
        if name_hits or string_hits:
            rows.append({
                "score": score,
                "index": ent.get("index"),
                "name": name,
                "path": path,
                "extension": ext,
                "size_in_archive": ent.get("size_in_archive"),
                "total_size": ent.get("total_size"),
                "is_resource": ent.get("is_resource"),
                "is_compressed": ent.get("is_compressed"),
                "name_hits": ";".join(name_hits),
                "string_hits": ";".join(string_hits[:50]),
                "scanned_payload": scanned,
                "sha256": sha,
                "extracted_to": extracted_to,
            })
    rows.sort(key=lambda r: (-int(r.get("score") or 0), str(r.get("path") or "")))
    write_csv(out_dir / "script_candidates.csv", rows)
    result = {
        "archive": str(archive),
        "queries": list(queries),
        "candidate_count": len(rows),
        "top_candidates": rows[:50],
        "csv": rel(out_dir / "script_candidates.csv"),
        "extract_dir": rel(extract_dir) if extract else "",
        "guardrails": [
            "source RPF was not modified",
            "candidate ranking is based on names/strings only",
            "extracted candidates are copies for research",
        ],
    }
    safe_write_json(out_dir / "script_candidates_summary.json", result)
    return result

def write_target_map(out_path: Path) -> dict:
    target_map = {
        "goal": "Find the missing layer between placed car/truck props and active driveable vehicles.",
        "priority_scripts": [
            "playercar.wsc",
            "beat_crime_wagonthief.wsc",
            "gen_vehicle_brain.wsc",
            "vehicle_generator.wsc",
        ],
        "priority_resources": [
            "template_vehicle*.xml",
            "car01x.vehsim", "truck01x.vehsim",
            "car01x.vehmodel", "truck01x.vehmodel",
            "car01x.vehinput", "truck01x.vehinput",
            "car01x.vehgyro", "truck01x.vehgyro",
            "car01x.vehstuck", "truck01x.vehstuck",
            "car01x.wft", "truck01x.wft",
            "territory/refgroup files that place vehicles",
        ],
        "working_theory": [
            "Refgroups can place the asset visually but do not automatically register it as a driveable vehicle.",
            "Driveability probably comes from script/template/tune activation: vehicle actor creation, vehicle brain, seats, controls, and vehsim binding.",
            "WSC files should be treated as maps for behavior until full decompile/recompile is proven.",
            "ASI/ScriptHook bridge is the practical behavior lane if WSC recompile remains blocked.",
        ],
        "safe_next_steps": [
            "Extract and scan the priority WSC files.",
            "Compare playercar.wsc against beat_crime_wagonthief.wsc.",
            "Search extracted scripts and tune files for car01x/truck01x/wagon/template/vehsim refs.",
            "Only same-size binary patches should be staged until a script compiler/decompiler is validated.",
            "Use ASI plugin experiments for new logic instead of replacing random WSC bytes.",
        ],
        "targets": DEFAULT_TARGETS,
    }
    safe_write_json(out_path, target_map)
    return target_map


def make_asi_scaffold(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "README.md").write_text("""# Code RED Vehicle Bridge ASI Scaffold

This is a conservative scaffold for the ScriptHook/ASI lane. It is not a finished
vehicle spawner. The goal is to keep custom behavior out of fragile compiled WSC
patches while Code RED uses WSC files as research maps.

## Intended workflow

1. Use `codered_vehicle_script_lab.py` to scan `playercar.wsc`,
   `beat_crime_wagonthief.wsc`, `vehicle_generator.wsc`, and tune resources.
2. Identify the native calls / templates / strings involved in making a vehicle
   active and driveable.
3. Implement the smallest ASI experiment possible: logging first, then controlled
   spawn/activation tests.
4. Keep original RPFs untouched. Put replacement resource files in copied RPFs only.

## Build notes

- Use Visual Studio x64 Release.
- Add your local ScriptHookRDR headers/libs when available.
- Keep logging on by default.
- Avoid hardcoded memory patching until native-call routes are proven.

""", encoding="utf-8")
    (out_dir / "vehicle_targets.json").write_text(json.dumps({
        "vehicles": ["car01x", "truck01x", "stagecoachgatling01x"],
        "scripts": ["playercar.wsc", "beat_crime_wagonthief.wsc", "gen_vehicle_brain.wsc", "vehicle_generator.wsc"],
        "tune_files": ["*.vehsim", "*.vehmodel", "*.vehinput", "*.vehgyro", "*.vehstuck"],
    }, indent=2), encoding="utf-8")
    (out_dir / "CodeREDVehicleBridge.cpp").write_text(r'''// Code RED Vehicle Bridge ASI scaffold
// Research-only starter: add ScriptHookRDR includes/libs locally.

#include <windows.h>
#include <fstream>
#include <string>

static HMODULE g_module = nullptr;

static void Log(const std::string& line)
{
    std::ofstream f("CodeREDVehicleBridge.log", std::ios::app);
    f << line << "\n";
}

static DWORD WINAPI MainThread(LPVOID)
{
    Log("Code RED Vehicle Bridge loaded.");
    Log("TODO: attach ScriptHookRDR native-call layer here after WSC research maps vehicle activation.");

    // Suggested first experiment once native wrappers are available:
    // - resolve player position
    // - create/spawn car01x/truck01x through the same native family seen in playercar/vehicle_generator
    // - register/activate vehicle brain/seat/controls
    // - log failures rather than crashing the game

    while (true)
    {
        if (GetAsyncKeyState(VK_F7) & 1)
        {
            Log("F7 pressed: placeholder vehicle activation test hook.");
        }
        if (GetAsyncKeyState(VK_END) & 1)
        {
            Log("END pressed: unloading worker loop.");
            break;
        }
        Sleep(50);
    }
    FreeLibraryAndExitThread(g_module, 0);
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        g_module = hModule;
        DisableThreadLibraryCalls(hModule);
        CreateThread(nullptr, 0, MainThread, nullptr, 0, nullptr);
    }
    return TRUE;
}
''', encoding="utf-8")
    (out_dir / "CodeREDVehicleBridge.vcxproj.note.txt").write_text("""Create a Visual Studio x64 DLL/ASI project and add CodeREDVehicleBridge.cpp.
Rename the built DLL to CodeREDVehicleBridge.asi.
Link against your local ScriptHookRDR SDK once native includes/libs are available.
""", encoding="utf-8")
    return {"out_dir": str(out_dir), "files": [p.name for p in out_dir.iterdir() if p.is_file()]}


def status() -> dict:
    return {
        "tool": "Code RED Vehicle Script Lab",
        "version": "v4",
        "root": str(ROOT),
        "python": sys.version.split()[0],
        "python_workbench_present": (ROOT / "python_workbench.py").exists(),
        "rpf_utils_present": (ROOT / "tools" / "codered_rpf_utils.py").exists(),
        "default_targets": len(DEFAULT_TARGETS),
        "v4_notes": [
            "Decodes RSC85/RSC05 script resource wrappers before string/hash/profile scans.",
            "Exports decompressed payload.bin beside scan/profile reports when input is an RSC resource.",
            "Keeps full WSC decompile/recompile out of scope while giving cleaner payload-level evidence."
        ],
        "zstandard_python": zstd is not None,
        "zstd_cli": _zstd_cli(),
        "policy": {
            "wsc_full_decompile_recompile": "not claimed",
            "safe_script_patching": "same-size/string/hash research only",
            "behavior_modding_lane": "ASI/ScriptHook scaffold and native-call research",
            "source_rpf_mutation": "blocked by this tool",
        },
        "common_commands": [
            r"Run_CodeRED_Vehicle_Script_Lab.bat scan-rpf --archive game\content.rpf --out logs\vehicle_script_lab\content_scripts",
            r"Run_CodeRED_Vehicle_Script_Lab.bat scan-folder --input imports\scripts --out logs\vehicle_script_lab\scripts",
            r"Run_CodeRED_Vehicle_Script_Lab.bat find-rpf --archive game\content.rpf --query playercar beat_crime_wagonthief wagonthief vehicle_generator gen_vehicle_brain --extract --out logs\vehicle_script_lab\script_finder",
            r"Run_CodeRED_Vehicle_Script_Lab.bat compare --left imports\playercar.wsc --right imports\beat_crime_wagonthief.wsc --out logs\vehicle_script_lab\playercar_vs_wagonthief",
            r"Run_CodeRED_Vehicle_Script_Lab.bat make-asi-scaffold --out asi\CodeREDVehicleBridge",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Code RED Vehicle Script Lab")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    tm = sub.add_parser("target-map")
    tm.add_argument("--out", default="logs/vehicle_script_lab/vehicle_activation_map.json")

    sf = sub.add_parser("scan-file")
    sf.add_argument("--input", required=True)
    sf.add_argument("--out", required=True)
    sf.add_argument("--targets")
    sf.add_argument("--min-string", type=int, default=4)

    sd = sub.add_parser("scan-folder")
    sd.add_argument("--input", required=True)
    sd.add_argument("--out", required=True)
    sd.add_argument("--targets")
    sd.add_argument("--ext", nargs="*", help="Optional extensions, e.g. .wsc .vehsim .xml")

    sr = sub.add_parser("scan-rpf")
    sr.add_argument("--archive", required=True)
    sr.add_argument("--out", required=True)
    sr.add_argument("--targets")
    sr.add_argument("--ext", nargs="*", default=[".wsc", ".sco", ".xsc", ".csc"], help="Extensions to extract/scan from RPF")
    sr.add_argument("--max-files", type=int, default=5000)

    fr = sub.add_parser("find-rpf")
    fr.add_argument("--archive", required=True)
    fr.add_argument("--out", required=True)
    fr.add_argument("--query", nargs="+", required=True, help="Names/terms to find, e.g. playercar beat_crime_wagonthief")
    fr.add_argument("--ext", nargs="*", help="Optional extensions to scan/extract")
    fr.add_argument("--extract", action="store_true", help="Extract matching candidates to the output folder")

    prof = sub.add_parser("profile-wsc")
    prof.add_argument("--input", required=True)
    prof.add_argument("--out", required=True)

    cmp = sub.add_parser("compare")
    cmp.add_argument("--left", required=True)
    cmp.add_argument("--right", required=True)
    cmp.add_argument("--out", required=True)
    cmp.add_argument("--targets")

    asi = sub.add_parser("make-asi-scaffold")
    asi.add_argument("--out", default="asi/CodeREDVehicleBridge")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(json.dumps(status(), indent=2))
            return 0
        if args.command == "target-map":
            print(json.dumps(write_target_map(Path(args.out)), indent=2))
            return 0
        if args.command == "scan-file":
            targets = read_targets_file(Path(args.targets) if args.targets else None)
            print(json.dumps(scan_file(Path(args.input), Path(args.out), targets, args.min_string), indent=2))
            return 0
        if args.command == "scan-folder":
            targets = read_targets_file(Path(args.targets) if args.targets else None)
            print(json.dumps(scan_folder(Path(args.input), Path(args.out), targets, args.ext), indent=2))
            return 0
        if args.command == "scan-rpf":
            targets = read_targets_file(Path(args.targets) if args.targets else None)
            print(json.dumps(scan_rpf(Path(args.archive), Path(args.out), targets, args.ext, args.max_files), indent=2))
            return 0
        if args.command == "find-rpf":
            print(json.dumps(find_script_candidates(Path(args.archive), Path(args.out), args.query, args.ext, args.extract), indent=2))
            return 0
        if args.command == "profile-wsc":
            print(json.dumps(write_profile_outputs(Path(args.input), Path(args.out)), indent=2))
            return 0
        if args.command == "compare":
            targets = read_targets_file(Path(args.targets) if args.targets else None)
            print(json.dumps(compare_files(Path(args.left), Path(args.right), Path(args.out), targets), indent=2))
            return 0
        if args.command == "make-asi-scaffold":
            print(json.dumps(make_asi_scaffold(Path(args.out)), indent=2))
            return 0
        return 1
    except Exception:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        crash = LOG_DIR / "vehicle_script_lab_crash.log"
        crash.write_text("Code RED Vehicle Script Lab crash\n\n" + traceback.format_exc(), encoding="utf-8")
        print(f"ERROR: {traceback.format_exc().splitlines()[-1]}", file=sys.stderr)
        print(f"Crash note: {crash}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
