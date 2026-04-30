#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RPF6_AES_KEY = bytes([
    0xB7, 0x62, 0xDF, 0xB6, 0xE2, 0xB2, 0xC6, 0xDE,
    0xAF, 0x72, 0x2A, 0x32, 0xD2, 0xFB, 0x6F, 0x0C,
    0x98, 0xA3, 0x21, 0x74, 0x62, 0xC9, 0xC4, 0xED,
    0xAD, 0xAA, 0x2E, 0xD0, 0xDD, 0xF9, 0x2F, 0x10,
])
VBASE = 0x50000000
DEFAULT_RECORD_OFFSET = 0x0011C7E0
DEFAULT_RECORD_SIZE = 0xE0
DEFAULT_NAME_PTR_REL = 0xB8
DEFAULT_POSITION_REL = 0x70
DEFAULT_EXPECTED_HOST = "i_gen_wagonBroken02x"
EXPECTED_DRAWABLE_VFT = 0x01913300


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()

def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rdr_hash(name: str) -> int:
    h = 0
    for ch in name.lower():
        a = (h + ord(ch)) & 0xFFFFFFFF
        b = (a + ((a << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h = (b ^ (b >> 6)) & 0xFFFFFFFF
    a = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    b = (a ^ (a >> 11)) & 0xFFFFFFFF
    return (b + ((b << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


def aes_blocks(data: bytes, decrypt: bool = True) -> bytes:
    n = len(data) & ~0xF
    if n <= 0:
        return data
    # Use the OpenSSL CLI here instead of optional crypto imports. This keeps the tool
    # predictable in portable/embedded Python environments and avoids slow site-package startup.
    if not shutil.which("openssl"):
        raise RuntimeError("Encrypted RPF needs openssl on PATH")
    block = data[:n]
    mode = "-d" if decrypt else "-e"
    key = RPF6_AES_KEY.hex()
    for _ in range(16):
        proc = subprocess.run(
            ["openssl", "enc", "-aes-256-ecb", mode, "-K", key, "-nopad", "-nosalt"],
            input=block,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=True,
        )
        block = proc.stdout
    return block + data[n:]

def is_resource(flag1: int) -> bool:
    return (flag1 & 0x80000000) != 0


def is_ext(flag2: int) -> bool:
    return (flag2 & 0x80000000) != 0


def is_comp(flag1: int, flag2: int) -> bool:
    return (not is_ext(flag2)) and ((flag1 >> 30) & 1) == 1


def resource_type(c: int) -> int:
    return c & 0xFF


def entry_offset(c: int, resource: bool) -> int:
    return ((c & 0x7FFFFF00) if resource else (c & 0x7FFFFFFF)) * 8


def total_size(flag1: int, flag2: int) -> int:
    if not is_resource(flag1):
        return flag1 & 0xBFFFFFFF
    if is_ext(flag2):
        return ((flag2 & 0x3FFF) << 12) + (((flag2 >> 14) & 0x3FFF) << 12)
    vp = ((flag1 >> 4) & 0x7F) + ((flag1 >> 3) & 1) + ((flag1 >> 2) & 1) + ((flag1 >> 1) & 1) + (flag1 & 1)
    vs = (flag1 >> 11) & 0xF
    pp = ((flag1 >> 19) & 0x7F) + ((flag1 >> 18) & 1) + ((flag1 >> 17) & 1) + ((flag1 >> 16) & 1) + ((flag1 >> 15) & 1)
    ps = (flag1 >> 26) & 0xF
    return (vp << (vs + 8)) + (pp << (ps + 8))


@dataclass
class Entry:
    index: int
    name_hash: int
    name: str
    path: str
    parent_index: int | None
    type: str
    start: int = 0
    count: int = 0
    size: int = 0
    offset_raw: int = 0
    offset: int = 0
    flag1: int = 0
    flag2: int = 0
    resource: bool = False
    compressed: bool = False
    resource_type: int | None = None
    total: int = 0
    ext: str = ""


class RPF6:
    def __init__(self, path: str | Path, debug: bool = True):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:4] != b"RPF6":
            raise ValueError(f"not an RPF6 archive: {self.path}")
        _, self.count, self.debug_word, self.encrypted_toc = struct.unpack(">4I", self.data[:16])
        self.toc_size = ((self.count * 20) + 15) & ~15
        toc = self.data[16 : 16 + self.toc_size]
        self.toc = aes_blocks(toc, True) if self.encrypted_toc else toc
        self.entries = self._entries(debug)
        self.exts = Counter(e.ext for e in self.entries if e.ext)

    def _debug_names(self) -> dict[int, list[str]]:
        off = self.debug_word * 8
        if off <= 0 or off >= len(self.data):
            return {}
        try:
            blob = aes_blocks(self.data[off:], True)[self.count * 8 :]
        except Exception:
            return {}
        out: dict[int, list[str]] = defaultdict(list)
        for text in blob.decode("latin-1", "ignore").split("\0"):
            s = text.strip()
            if s:
                out[rdr_hash(s)].append(s)
        return out

    def _entries(self, debug: bool) -> list[Entry]:
        raw: list[dict[str, Any]] = []
        names = self._debug_names() if debug else {}
        for i in range(self.count):
            a, b, c, d, e = struct.unpack(">5I", self.toc[i * 20 : (i + 1) * 20])
            is_dir = ((c >> 24) & 0xFF) == 0x80
            if is_dir:
                raw.append({"i": i, "h": a, "t": "dir", "start": c & 0x7FFFFFFF, "count": d & 0x0FFFFFFF})
            else:
                res = is_resource(d)
                raw.append(
                    {
                        "i": i,
                        "h": a,
                        "t": "file",
                        "size": b & 0x0FFFFFFF,
                        "oraw": c,
                        "off": entry_offset(c, res),
                        "f1": d,
                        "f2": e,
                        "res": res,
                        "comp": is_comp(d, e),
                        "rt": resource_type(c) if res else None,
                        "total": total_size(d, e),
                    }
                )
        parents: list[int | None] = [None] * len(raw)
        for item in raw:
            if item["t"] == "dir":
                for child_index in range(item["start"], item["start"] + item["count"]):
                    if 0 <= child_index < len(raw):
                        parents[child_index] = item["i"]

        def name_for(item: dict[str, Any]) -> str:
            if item["t"] == "dir" and item["h"] == 0:
                return "root"
            vals = names.get(item["h"])
            return vals.pop(0) if vals else f"0x{item['h']:08X}"

        for item in raw:
            item["name"] = name_for(item)
            item["par"] = parents[item["i"]]

        out: list[Entry] = []
        for item in raw:
            parts = [item["name"]]
            parent = item["par"]
            seen: set[int] = set()
            while parent is not None and parent not in seen and 0 <= parent < len(raw):
                seen.add(parent)
                parts.append(raw[parent]["name"])
                parent = raw[parent]["par"]
            path = "/".join(reversed(parts))
            ext = "." + item["name"].lower().rsplit(".", 1)[-1] if item["t"] == "file" and "." in item["name"] else ""
            out.append(
                Entry(
                    item["i"],
                    item["h"],
                    item["name"],
                    path,
                    item["par"],
                    item["t"],
                    item.get("start", 0),
                    item.get("count", 0),
                    item.get("size", 0),
                    item.get("oraw", 0),
                    item.get("off", 0),
                    item.get("f1", 0),
                    item.get("f2", 0),
                    item.get("res", False),
                    item.get("comp", False),
                    item.get("rt"),
                    item.get("total", 0),
                    ext,
                )
            )
        return out

    def files(self, ext: str | None = None) -> list[Entry]:
        if ext is None:
            return [e for e in self.entries if e.type == "file"]
        return [e for e in self.entries if e.type == "file" and e.ext == ext.lower()]

    def find(self, path: str) -> Entry | None:
        want = path.replace("\\", "/").lower()
        return next((e for e in self.entries if e.type == "file" and e.path.lower() == want), None)

    def slot(self, entry: Entry) -> bytes:
        return self.data[entry.offset : entry.offset + entry.size]

    def summary(self) -> dict[str, Any]:
        return {
            "archive": str(self.path),
            "entry_count": self.count,
            "file_count": sum(e.type == "file" for e in self.entries),
            "dir_count": sum(e.type == "dir" for e in self.entries),
            "encrypted_toc": bool(self.encrypted_toc),
            "debug_offset_word": self.debug_word,
            "extensions": dict(sorted(self.exts.items())),
        }


def zstd_dec(data: bytes) -> bytes:
    try:
        import zstandard as zstd  # type: ignore

        return zstd.ZstdDecompressor().decompress(data)
    except Exception:
        pass
    if not shutil.which("zstd"):
        raise RuntimeError("Need zstandard Python package or zstd CLI")
    return subprocess.run(
        ["zstd", "-d", "-q", "--single-thread", "--stdout"],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def zstd_enc(data: bytes, level: int = 9) -> bytes:
    try:
        import zstandard as zstd  # type: ignore

        return zstd.ZstdCompressor(level=level, write_checksum=False).compress(data)
    except Exception:
        pass
    if not shutil.which("zstd"):
        raise RuntimeError("Need zstandard Python package or zstd CLI")
    return subprocess.run(
        ["zstd", "-q", "-z", f"-{level}", "--no-check", "--single-thread", "--stdout"],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def rsc_decode(raw: bytes) -> tuple[bytes, bytes]:
    if not raw.startswith(b"RSC") or len(raw) < 12:
        raise ValueError("not an RSC resource slot")
    return raw[:12], zstd_dec(raw[12:])


def rsc_encode(header: bytes, payload: bytes, level: int = 9) -> bytes:
    return header + zstd_enc(payload, level)


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0] if off + 4 <= len(data) else 0


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0] if off + 4 <= len(data) else 0.0


def vec4(data: bytes, off: int) -> list[float | str]:
    if off + 16 > len(data):
        return []
    out: list[float | str] = []
    for value in struct.unpack_from("<4f", data, off):
        out.append(round(value, 6) if math.isfinite(value) else "nan")
    return out


def ptr_target(ptr: int, size: int) -> int | None:
    return ptr - VBASE if VBASE <= ptr < VBASE + size else None


def cstr(data: bytes, off: int | None, max_len: int = 512) -> str:
    if off is None or off < 0 or off >= len(data):
        return ""
    end = off
    while end < len(data) and end - off < max_len and data[end] != 0:
        end += 1
    return data[off:end].decode("latin-1", "replace")


def parse_drawable_record(data: bytes, record_offset: int, record_size: int, name_ptr_rel: int, position_rel: int) -> dict[str, Any]:
    name_ptr = u32(data, record_offset + name_ptr_rel)
    name_off = ptr_target(name_ptr, len(data))
    row3 = vec4(data, record_offset + position_rel)
    return {
        "record_offset": record_offset,
        "record_offset_hex": f"0x{record_offset:08X}",
        "record_size": record_size,
        "record_vft_hex": f"0x{u32(data, record_offset):08X}",
        "matrix_row0_guess": vec4(data, record_offset + 0x40),
        "matrix_row1_guess": vec4(data, record_offset + 0x50),
        "matrix_row2_guess": vec4(data, record_offset + 0x60),
        "matrix_row3_position_guess": row3,
        "position_guess": row3[:3] if len(row3) >= 3 else [],
        "bbox_min_guess": vec4(data, record_offset + 0x80),
        "bbox_max_guess": vec4(data, record_offset + 0x90),
        "instance_hash_guess_hex": f"0x{u32(data, record_offset + 0xA0):08X}",
        "drawable_flags_guess_hex": f"0x{u32(data, record_offset + 0xB0):08X}",
        "name_ptr_rel_guess": name_ptr_rel,
        "record_name_ptr_hex": f"0x{name_ptr:08X}" if name_ptr else "",
        "record_name_offset_hex": f"0x{name_off:08X}" if name_off is not None else "",
        "record_name": cstr(data, name_off),
        "record_sha1": sha1(data[record_offset : record_offset + record_size]),
    }


def choose_wsi_entry(rpf: RPF6, wsi_path: str | None) -> Entry:
    if wsi_path:
        entry = rpf.find(wsi_path)
        if not entry:
            raise SystemExit(f"WSI path not found: {wsi_path}")
        return entry
    candidates = [e for e in rpf.entries if e.type == "file" and e.resource and e.resource_type == 134]
    if len(candidates) != 1:
        summary = [{"index": e.index, "path": e.path, "size": e.size, "resource_type": e.resource_type} for e in candidates]
        raise SystemExit("Expected exactly one resource_type 134 WSI candidate; pass --wsi-path. Candidates: " + json.dumps(summary, indent=2))
    return candidates[0]


def patch_toc(data: bytearray, rpf: RPF6, entry: Entry, new_size: int, new_offset: int) -> None:
    if new_offset % 2048:
        raise ValueError("RSC replacement must be 2048-byte aligned")
    toc = bytearray(rpf.toc)
    off = entry.index * 20
    a, b, c, d, f = struct.unpack(">5I", toc[off : off + 20])
    b = (b & 0xF0000000) | (new_size & 0x0FFFFFFF)
    c = ((new_offset // 8) & 0x7FFFFF00) | (entry.resource_type or resource_type(c))
    toc[off : off + 20] = struct.pack(">5I", a, b, c, d, f)
    data[16 : 16 + rpf.toc_size] = aes_blocks(bytes(toc), False) if rpf.encrypted_toc else bytes(toc)


def apply_mutation(payload: bytearray, args: argparse.Namespace) -> dict[str, Any]:
    rec_off = args.record_offset
    pos_off = rec_off + args.position_rel
    before_position = list(struct.unpack_from("<4f", payload, pos_off))
    changed_ranges: list[dict[str, Any]] = []

    if args.mode == "noop":
        # Intentionally no data changes; useful for archive rewrite/reopen proof.
        after_position = before_position[:]
    elif args.mode == "nudge-position":
        after_position = before_position[:]
        after_position[0] += args.dx
        after_position[1] += args.dy
        after_position[2] += args.dz
        old = bytes(payload[pos_off : pos_off + 16])
        struct.pack_into("<4f", payload, pos_off, *after_position)
        new = bytes(payload[pos_off : pos_off + 16])
        changed_ranges.append(
            {
                "field": "matrix_row3_position_guess",
                "decoded_offset": pos_off,
                "decoded_offset_hex": f"0x{pos_off:08X}",
                "old_hex": old.hex(),
                "new_hex": new.hex(),
                "before_position": [round(v, 6) for v in before_position],
                "after_position": [round(v, 6) for v in after_position],
            }
        )
    else:
        raise SystemExit(f"Unsupported mode: {args.mode}")

    return {
        "mode": args.mode,
        "position_field_offset": pos_off,
        "position_field_offset_hex": f"0x{pos_off:08X}",
        "before_position": [round(v, 6) for v in before_position],
        "after_position": [round(v, 6) for v in after_position],
        "changed_ranges": changed_ranges,
        "changed_byte_count": sum(len(bytes.fromhex(r["new_hex"])) for r in changed_ranges),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Code RED copied-RPF single WSI placement mutation harness")
    parser.add_argument("archive", help="Source RPF containing Blackwater WSI")
    parser.add_argument("--wsi-path", help="Exact WSI entry path. Optional when archive has one resource_type 134 file.")
    parser.add_argument("--out", required=True, help="Copied/patched output RPF. Refuses in-place edits.")
    parser.add_argument("--proof", help="Proof JSON path. Default: <out>.single_placement_proof.json")
    parser.add_argument("--record-offset", type=lambda s: int(s, 0), default=DEFAULT_RECORD_OFFSET)
    parser.add_argument("--record-size", type=lambda s: int(s, 0), default=DEFAULT_RECORD_SIZE)
    parser.add_argument("--name-ptr-rel", type=lambda s: int(s, 0), default=DEFAULT_NAME_PTR_REL)
    parser.add_argument("--position-rel", type=lambda s: int(s, 0), default=DEFAULT_POSITION_REL)
    parser.add_argument("--expected-host", default=DEFAULT_EXPECTED_HOST)
    parser.add_argument("--mode", choices=["noop", "nudge-position"], default="noop")
    parser.add_argument("--dx", type=float, default=0.0)
    parser.add_argument("--dy", type=float, default=0.0)
    parser.add_argument("--dz", type=float, default=0.25)
    parser.add_argument("--zstd-level", type=int, default=9)
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()

    src = Path(args.archive)
    dst = Path(args.out)
    if not src.exists():
        raise SystemExit(f"source archive does not exist: {src}")
    if src.resolve() == dst.resolve():
        raise SystemExit("Refusing in-place patch. Use --out for a copied archive.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    rpf = RPF6(dst, debug=not args.no_debug)
    entry = choose_wsi_entry(rpf, args.wsi_path)
    header, payload = rsc_decode(rpf.slot(entry))
    if args.record_offset < 0 or args.record_offset + args.record_size > len(payload):
        raise SystemExit("record offset/size is outside decoded WSI payload")

    before_record = parse_drawable_record(payload, args.record_offset, args.record_size, args.name_ptr_rel, args.position_rel)
    validation_errors: list[str] = []
    if before_record["record_vft_hex"] != f"0x{EXPECTED_DRAWABLE_VFT:08X}":
        validation_errors.append(f"unexpected record VFT: {before_record['record_vft_hex']}")
    if args.expected_host and before_record["record_name"] != args.expected_host:
        validation_errors.append(f"expected host {args.expected_host!r}, got {before_record['record_name']!r}")
    if validation_errors:
        raise SystemExit("Preflight failed: " + "; ".join(validation_errors))

    mutated = bytearray(payload)
    mutation = apply_mutation(mutated, args)
    new_payload = bytes(mutated)
    after_record = parse_drawable_record(new_payload, args.record_offset, args.record_size, args.name_ptr_rel, args.position_rel)
    new_resource = rsc_encode(header, new_payload, args.zstd_level)
    roundtrip_header, roundtrip_payload = rsc_decode(new_resource)
    if roundtrip_header != header or roundtrip_payload != new_payload:
        raise SystemExit("RSC encode/decode roundtrip verification failed")

    archive_data = bytearray(rpf.data)
    new_offset = (len(archive_data) + 2047) & ~2047
    archive_data.extend(b"\0" * (new_offset - len(archive_data)))
    archive_data.extend(new_resource)
    patch_toc(archive_data, rpf, entry, len(new_resource), new_offset)
    dst.write_bytes(archive_data)

    reopened = RPF6(dst, debug=not args.no_debug)
    reopened_entry = choose_wsi_entry(reopened, entry.path)
    reopened_header, reopened_payload = rsc_decode(reopened.slot(reopened_entry))
    reopened_record = parse_drawable_record(reopened_payload, args.record_offset, args.record_size, args.name_ptr_rel, args.position_rel)

    verification = {
        "archive_reopened": True,
        "wsi_entry_path_preserved": reopened_entry.path == entry.path,
        "decoded_payload_matches_written_payload": reopened_payload == new_payload,
        "record_sha1_matches_after": reopened_record["record_sha1"] == after_record["record_sha1"],
        "host_name_preserved": reopened_record["record_name"] == args.expected_host,
        "mode": args.mode,
    }
    validation_passed = all(bool(v) for v in verification.values() if not isinstance(v, str))

    proof = {
        "tool": "codered_wsi_single_placement_mutation_harness.py",
        "purpose": "copied-RPF one-placement mutation/reopen proof",
        "source_archive": str(src),
        "output_archive": str(dst),
        "source_archive_sha1": sha1_file(src),
        "output_archive_sha1": sha1_file(dst),
        "source_archive_size": src.stat().st_size,
        "output_archive_size": dst.stat().st_size,
        "wsi_entry_before": asdict(entry),
        "wsi_entry_after_reopen": asdict(reopened_entry),
        "decoded_sha1_before": sha1(payload),
        "decoded_sha1_after": sha1(new_payload),
        "decoded_sha1_after_reopen": sha1(reopened_payload),
        "rsc_header_hex": header.hex(),
        "old_resource_size": len(rpf.slot(entry)),
        "new_resource_size": len(new_resource),
        "new_resource_archive_offset": new_offset,
        "new_resource_archive_offset_hex": f"0x{new_offset:08X}",
        "record_offset": args.record_offset,
        "record_offset_hex": f"0x{args.record_offset:08X}",
        "expected_host": args.expected_host,
        "record_before": before_record,
        "record_after": after_record,
        "record_after_reopen": reopened_record,
        "record_bytes_before_hex": payload[args.record_offset : args.record_offset + args.record_size].hex(),
        "record_bytes_after_hex": new_payload[args.record_offset : args.record_offset + args.record_size].hex(),
        "mutation": mutation,
        "verification": verification,
        "validation_passed": validation_passed,
        "rollback": {
            "delete_output_archive": str(dst),
            "original_archive_was_not_modified": True,
        },
        "next_safe_action": "Use mode nudge-position as the first visual-only copied-RPF test. Do not attempt Vehicle_Generator binding until this exact placement change is confirmed in-game.",
    }

    proof_path = Path(args.proof) if args.proof else dst.with_suffix(dst.suffix + ".single_placement_proof.json")
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(json.dumps({"output_archive": str(dst), "proof": str(proof_path), "validation_passed": validation_passed, "mode": args.mode, "record_after": reopened_record}, indent=2), flush=True)
    # Some embedded Python environments can hang during interpreter teardown after repeated
    # subprocess zstd/openssl calls. At this point all files are flushed and proof JSON is
    # written, so exit hard and cleanly.
    os._exit(0)


if __name__ == "__main__":
    main()
