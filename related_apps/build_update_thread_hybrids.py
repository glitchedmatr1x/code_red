#!/usr/bin/env python3
"""
Code RED content.rpf update-thread hybrid builder.

This does not contain game data. It reads your own content.rpf and creates patched
copies beside it so you can test variants without overwriting the original.

Usage:
  python build_update_thread_hybrids.py C:\\path\\to\\content.rpf
  python build_update_thread_hybrids.py content.rpf --variant sp_owner

Variants:
  sp_owner   = DLC zombie long update slot is replaced with the normal SP long update stream.
               Goal: reduce conflict by making normal SP own global state.
  z_owner    = Normal SP long update slot is replaced with the zombie DLC long update stream.
               Goal: zombie systems own global state while SP content remains present.
  dual_swap  = Swaps the two long update streams both ways.
               Goal: recreate your older mixed-mode experiment as a clean archive-copy patch.
  all_long_medium_short_dual = swaps short/medium/long pairs both ways. Highest risk.
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except Exception as exc:
    print("Missing dependency: cryptography")
    print("Install with: py -m pip install cryptography")
    raise

RPF6_AES_KEY = bytes([
    0xB7,0x62,0xDF,0xB6,0xE2,0xB2,0xC6,0xDE,0xAF,0x72,0x2A,0x32,0xD2,0xFB,0x6F,0x0C,
    0x98,0xA3,0x21,0x74,0x62,0xC9,0xC4,0xED,0xAD,0xAA,0x2E,0xD0,0xDD,0xF9,0x2F,0x10,
])

def crypt_block(data: bytes, encrypt: bool) -> bytes:
    block_len = len(data) & ~0xF
    if block_len <= 0:
        return data
    cipher = Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
    block = data[:block_len]
    for _ in range(16):
        ctx = cipher.encryptor() if encrypt else cipher.decryptor()
        block = ctx.update(block) + ctx.finalize()
    return block + data[block_len:]

def rpf_hash(name: str) -> int:
    n = 0
    for ch in name.lower():
        a = (n + ord(ch)) & 0xFFFFFFFF
        b = (a + ((a << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        n = (b ^ (b >> 6)) & 0xFFFFFFFF
    a = (n + ((n << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    b = (a ^ (a >> 11)) & 0xFFFFFFFF
    return (b + ((b << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF

def is_resource(flag1: int) -> bool:
    return (flag1 & 0x80000000) != 0

def is_compressed(flag1: int, flag2: int) -> bool:
    return (flag1 & 0x40000000) != 0 or (flag2 & 0x40000000) != 0

def entry_offset(offset_raw: int, resource: bool) -> int:
    if resource:
        return (offset_raw & 0x7FFFFF00) * 8
    return (offset_raw & 0x7FFFFFFF) * 8

def parse_rpf6(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 16 or data[:4] != b"RPF6":
        raise ValueError("Not an RPF6 archive")
    magic, count, debug_offset, enc_flag = struct.unpack(">4s3I", data[:16])
    toc_size = ((count * 20) + 15) & ~15
    toc_encrypted = data[16:16 + toc_size]
    toc = crypt_block(toc_encrypted, encrypt=False) if enc_flag else toc_encrypted
    entries = []
    for i in range(count):
        a, b, c, d, e = struct.unpack(">5I", toc[i*20:(i+1)*20])
        is_dir = ((c >> 24) & 0xFF) == 0x80
        if is_dir:
            ent = dict(index=i, name_off=a, type="dir", flags=b, start=c & 0x7FFFFFFF, count=d & 0x0FFFFFFF, unk=e)
        else:
            res = is_resource(d)
            ent = dict(index=i, name_off=a, type="file", size_in_archive=b & 0x0FFFFFFF,
                       offset_raw=c, flag1=d, flag2=e, is_resource=res,
                       is_compressed=is_compressed(d,e), offset=entry_offset(c,res))
        entries.append(ent)

    # Debug names are stored as hash->name records after count*8 bytes.
    names = {}
    if debug_offset:
        dbg_start = debug_offset * 8
        if dbg_start < len(data):
            dbg = crypt_block(data[dbg_start:], encrypt=False)
            blob = dbg[count * 8:]
            for raw in blob.decode("latin-1", "ignore").split("\0"):
                raw = raw.strip()
                if raw:
                    names.setdefault(rpf_hash(raw), raw)
    for e in entries:
        e["name"] = names.get(e["name_off"], "root" if e["type"] == "dir" and e["name_off"] == 0 else f"0x{e['name_off']:08X}")

    parents = [None] * len(entries)
    for e in entries:
        if e["type"] == "dir":
            for ci in range(e["start"], min(len(entries), e["start"] + e["count"])):
                if ci != e["index"]:
                    parents[ci] = e["index"]
    for e in entries:
        parts = [e["name"]]
        seen = {e["index"]}
        p = parents[e["index"]]
        while p is not None and p not in seen and 0 <= p < len(entries):
            seen.add(p)
            parts.append(entries[p]["name"])
            p = parents[p]
        e["path"] = "/".join(reversed(parts))
    return dict(path=str(path), entry_count=count, debug_offset=debug_offset, enc_flag=enc_flag, toc_size=toc_size, entries=entries)

def find_entry(info: dict, suffix: str) -> dict:
    suffix = suffix.lower().replace("\\", "/")
    matches = [e for e in info["entries"] if e.get("type") == "file" and e.get("path", "").lower().endswith(suffix)]
    if len(matches) != 1:
        # Fallback by filename for partially unresolved parent folders.
        name = suffix.rsplit("/", 1)[-1]
        matches = [e for e in info["entries"] if e.get("type") == "file" and e.get("name", "").lower() == name]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one match for {suffix!r}, got {len(matches)}")
    return matches[0]

def read_entry_bytes(path: Path, entry: dict) -> bytes:
    with path.open("rb") as f:
        f.seek(entry["offset"])
        return f.read(entry["size_in_archive"])

def append_payload(path: Path, payload: bytes) -> int:
    size = path.stat().st_size
    aligned = (size + 7) & ~7
    with path.open("ab") as f:
        if aligned > size:
            f.write(b"\x00" * (aligned - size))
        f.write(payload)
    return aligned

def update_entry_metadata(path: Path, info: dict, entry: dict, new_size: int, new_offset: int) -> None:
    # Only touch the encrypted TOC span, not the entire archive.
    toc_start = 16
    toc_size = info["toc_size"]
    with path.open("r+b") as f:
        f.seek(toc_start)
        toc = f.read(toc_size)
        if info["enc_flag"]:
            toc = crypt_block(toc, encrypt=False)
        toc_buf = bytearray(toc)
        off = entry["index"] * 20
        a, b, c, d, e = struct.unpack(">5I", bytes(toc_buf[off:off + 20]))
        b = (b & 0xF0000000) | (new_size & 0x0FFFFFFF)
        if new_offset % 8:
            raise ValueError("new offset is not 8-byte aligned")
        if is_resource(d):
            c = ((new_offset // 8) & 0x7FFFFF00) | (c & 0xFF)
        else:
            c = (new_offset // 8) & 0x7FFFFFFF
        toc_buf[off:off + 20] = struct.pack(">5I", a, b, c, d, e)
        out_toc = crypt_block(bytes(toc_buf), encrypt=True) if info["enc_flag"] else bytes(toc_buf)
        f.seek(toc_start)
        f.write(out_toc)

def patch_swap(source_rpf: Path, out_rpf: Path, operations: list[tuple[str, str]], info: dict | None = None) -> dict:
    shutil.copy2(source_rpf, out_rpf)
    info = info or parse_rpf6(source_rpf)
    report = {"source": str(source_rpf), "output": str(out_rpf), "operations": []}
    for target_suffix, donor_suffix in operations:
        target = find_entry(info, target_suffix)
        donor = find_entry(info, donor_suffix)
        donor_bytes = read_entry_bytes(source_rpf, donor)
        new_offset = append_payload(out_rpf, donor_bytes)
        update_entry_metadata(out_rpf, info, target, len(donor_bytes), new_offset)
        with out_rpf.open("rb") as f:
            f.seek(new_offset)
            verify_bytes = f.read(len(donor_bytes))
        ok = verify_bytes == donor_bytes
        report["operations"].append({
            "target": target.get("path"), "target_suffix": target_suffix,
            "donor": donor.get("path"), "donor_suffix": donor_suffix,
            "bytes": len(donor_bytes), "new_offset": new_offset,
            "verified_raw_readback": ok,
        })
        if not ok:
            raise RuntimeError(f"verification failed for {target_suffix}")
    return report

SP_LONG = "scripting/designerdefined/long_update_thread.wsc"
SP_MED = "scripting/designerdefined/medium_update_thread.wsc"
SP_SHORT = "scripting/designerdefined/short_update_thread.wsc"
Z_LONG = "dlc/zombiepack/system/long_update_thread_z.wsc"
Z_MED = "dlc/zombiepack/system/medium_update_thread_z.wsc"
Z_SHORT = "dlc/zombiepack/system/short_update_thread_z.wsc"

VARIANTS = {
    "sp_owner": [(Z_LONG, SP_LONG)],
    "z_owner": [(SP_LONG, Z_LONG)],
    "dual_swap": [(SP_LONG, Z_LONG), (Z_LONG, SP_LONG)],
    "all_long_medium_short_dual": [(SP_LONG, Z_LONG), (Z_LONG, SP_LONG), (SP_MED, Z_MED), (Z_MED, SP_MED), (SP_SHORT, Z_SHORT), (Z_SHORT, SP_SHORT)],
}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("content_rpf", nargs="?", default="content.rpf")
    ap.add_argument("--variant", choices=["all"] + sorted(VARIANTS), default="sp_owner")
    args = ap.parse_args()
    source = Path(args.content_rpf).expanduser().resolve()
    if not source.exists():
        print(f"Missing content.rpf: {source}")
        return 2
    variants = sorted(VARIANTS) if args.variant == "all" else [args.variant]
    print("Parsing source archive once...")
    parsed_info = parse_rpf6(source)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = source.with_name(f"codered_update_thread_hybrids_{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for name in variants:
        out = out_dir / f"content_{name}.rpf"
        print(f"Building {name}: {out}")
        rep = patch_swap(source, out, VARIANTS[name], parsed_info)
        rep["variant"] = name
        reports.append(rep)
    (out_dir / "hybrid_build_report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    readme = out_dir / "READ_ME_FIRST.txt"
    readme.write_text(
        "Code RED update-thread hybrid builds generated from your own content.rpf.\n\n"
        "Test order I recommend:\n"
        "1) content_sp_owner.rpf - least conflict; normal SP owns the long update state.\n"
        "2) content_z_owner.rpf - zombie DLC owns the long update state.\n"
        "3) content_dual_swap.rpf - recreates the stronger mixed-mode swap.\n"
        "4) content_all_long_medium_short_dual.rpf - highest risk, all update pairs swapped.\n\n"
        "Do not overwrite the original. Rename the chosen candidate to content.rpf only after backing up.\n",
        encoding="utf-8"
    )
    print(f"Done. Output folder: {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
