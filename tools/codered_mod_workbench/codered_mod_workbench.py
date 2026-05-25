#!/usr/bin/env python3
"""
Code RED Mod Workbench

A conservative scanner/patcher for Red Dead Redemption PC modding workflows.

Supported lanes:
- Text/XML/SCXML/TUNE/etc.: scan readable strings and replace text, including length-changing replacements.
- Raw binary: scan ASCII/UTF-16 strings and replace only same-size or shorter padded byte strings.
- RSC85/WSC resources: decode encrypted/compressed RSC85 payloads when possible, patch decoded strings only with
  same-size or shorter replacements, then repack/reopen/decode validate.
- ZIP packages: extract to a work folder, scan contents, optionally patch files and rebuild a new ZIP.

This is not a WSC compiler. It does not insert bytecode, add functions, or rewrite native calls.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as _dt
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import zipfile
import zlib
from pathlib import Path
from typing import Iterable, Optional, Sequence

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except Exception:  # pragma: no cover - handled at runtime
    Cipher = None
    algorithms = None
    modes = None
    default_backend = None

try:
    import zstandard as _zstd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _zstd = None

TOOL_VERSION = "0.1.0-conservative"

# Magic-RDR public RDR key, used by RSC85 type-2 resources.
# Keep it in this source so the tool is portable/offline for user-owned game files.
RDR_RSC85_AES_KEY = bytes([
    0xB7, 0x62, 0xDF, 0xB6, 0xE2, 0xB2, 0xC6, 0xDE,
    0xAF, 0x72, 0x2A, 0x32, 0xD2, 0xFB, 0x6F, 0x0C,
    0x98, 0xA3, 0x21, 0x74, 0x62, 0xC9, 0xC4, 0xED,
    0xAD, 0xAA, 0x2E, 0xD0, 0xDD, 0xF9, 0x2F, 0x10,
])

TEXT_EXTENSIONS = {
    ".xml", ".sc.xml", ".txt", ".csv", ".json", ".cfg", ".ini", ".dat",
    ".tr", ".tune", ".weap", ".traffic", ".hud", ".raw", ".refgroup",
    ".fxlist", ".modellist", ".emitlist", ".fullfxlist", ".shaderlist",
    ".texlist", ".ptxlist", ".arm", ".mtl", ".fx", ".ppp",
}

ASCII_RE = re.compile(rb"[\x20-\x7E]{3,}")
UTF16LE_RE = re.compile((rb"(?:[\x20-\x7E]\x00){3,}"))


@dataclasses.dataclass
class StringHit:
    file: str
    container: str
    kind: str
    offset: int
    length: int
    text: str
    replaceable: str
    note: str = ""


@dataclasses.dataclass
class RSC85Meta:
    endian: str
    ident: int
    resource_type: int
    flag1: int
    flag2: int
    total_v: int
    total_p: int
    decoded_size: int
    compression: str
    encrypted: bool
    header_size: int = 16


class WorkbenchError(Exception):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def is_probably_text_path(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".sc.xml"):
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def read_bytes(path: Path) -> bytes:
    with path.open("rb") as f:
        return f.read()


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(data)


def safe_decode_text(data: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "utf-16-le", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1", errors="replace"), "latin-1-replace"


def encode_text(text: str, encoding: str) -> bytes:
    if encoding == "latin-1-replace":
        return text.encode("latin-1", errors="replace")
    return text.encode(encoding)


def aes_ecb_16_rounds(data: bytes, *, decrypt: bool) -> bytes:
    if Cipher is None:
        raise WorkbenchError("cryptography package is required for RSC85 AES decode/repack. Install requirements.txt.")
    out = bytearray(data)
    count = len(out) & ~0xF
    if count <= 0:
        return bytes(out)
    cipher = Cipher(algorithms.AES(RDR_RSC85_AES_KEY), modes.ECB(), backend=default_backend())
    for _ in range(16):
        ctx = cipher.decryptor() if decrypt else cipher.encryptor()
        block = ctx.update(bytes(out[:count])) + ctx.finalize()
        out[:count] = block
    return bytes(out)


def rsc85_totals(flag1: int, flag2: int) -> tuple[int, int]:
    total_v = (flag2 & 0x3FFF) << 12
    total_p = ((flag2 >> 14) & 0x3FFF) << 12
    return total_v, total_p


def parse_rsc85_header(data: bytes) -> Optional[RSC85Meta]:
    if len(data) < 16:
        return None
    candidates: list[RSC85Meta] = []
    for endian, fmt in (("little", "<IIII"), ("big", ">IIII")):
        ident, resource_type, flag1, flag2 = struct.unpack_from(fmt, data, 0)
        # Little-endian RSC85 appears as 0x85435352. Big-endian reversed form appears as 0x52534385.
        if ident not in (0x85435352, 0x52534385, 0x86435352, 0x52534386):
            continue
        total_v, total_p = rsc85_totals(flag1, flag2)
        decoded_size = total_v + total_p
        encrypted = resource_type == 2
        candidates.append(RSC85Meta(
            endian=endian,
            ident=ident,
            resource_type=resource_type,
            flag1=flag1,
            flag2=flag2,
            total_v=total_v,
            total_p=total_p,
            decoded_size=decoded_size,
            compression="unknown",
            encrypted=encrypted,
        ))
    if not candidates:
        return None
    # Prefer little-endian PC/Switch-style RSC85 with sane decoded size.
    sane = [c for c in candidates if 0 < c.decoded_size < 512 * 1024 * 1024]
    little = [c for c in sane if c.endian == "little"]
    if little:
        return little[0]
    return sane[0] if sane else candidates[0]


def zstd_decompress(data: bytes) -> bytes:
    if _zstd is not None:
        return _zstd.ZstdDecompressor().decompress(data)
    # External fallback if user has zstd.exe/zstd CLI in PATH.
    try:
        p = subprocess.run(["zstd", "-d", "-q", "-c"], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return p.stdout
    except Exception as e:
        raise WorkbenchError("zstandard Python package or zstd CLI is required for Zstandard RSC85 resources.") from e


def zstd_compress(data: bytes, level: int = 9) -> bytes:
    if _zstd is not None:
        return _zstd.ZstdCompressor(level=level).compress(data)
    try:
        p = subprocess.run(["zstd", "-q", f"-{level}", "-c"], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return p.stdout
    except Exception as e:
        raise WorkbenchError("zstandard Python package or zstd CLI is required to repack Zstandard RSC85 resources.") from e


def decompress_payload(payload: bytes, expected_size: int) -> tuple[bytes, str]:
    errors: list[str] = []
    if payload.startswith(b"\x28\xB5\x2F\xFD") or _zstd is not None:
        try:
            out = zstd_decompress(payload)
            if expected_size <= 0 or len(out) == expected_size or len(out) > 0:
                return out, "zstd"
        except Exception as e:
            errors.append(f"zstd:{e}")
    for wbits, label in ((-15, "zlib_raw"), (15, "zlib")):
        try:
            out = zlib.decompress(payload, wbits)
            if expected_size <= 0 or len(out) == expected_size or len(out) > 0:
                return out, label
        except Exception as e:
            errors.append(f"{label}:{e}")
    raise WorkbenchError("Unable to decompress RSC85 payload. Tried zstd/zlib. " + "; ".join(errors[:3]))


def compress_payload(decoded: bytes, compression: str) -> bytes:
    if compression == "zstd":
        return zstd_compress(decoded)
    if compression == "zlib_raw":
        co = zlib.compressobj(level=9, wbits=-15)
        return co.compress(decoded) + co.flush()
    if compression == "zlib":
        return zlib.compress(decoded, level=9)
    raise WorkbenchError(f"Unsupported compression for repack: {compression}")


def decode_rsc85(data: bytes) -> tuple[bytes, RSC85Meta, bytes]:
    meta = parse_rsc85_header(data)
    if meta is None:
        raise WorkbenchError("Not an RSC85/RSC86 resource with a recognized header.")
    payload = data[meta.header_size:]
    if meta.encrypted:
        payload = aes_ecb_16_rounds(payload, decrypt=True)
    decoded, compression = decompress_payload(payload, meta.decoded_size)
    meta.compression = compression
    meta.decoded_size = len(decoded)
    return decoded, meta, data[:meta.header_size]


def repack_rsc85(decoded: bytes, meta: RSC85Meta, header: bytes) -> bytes:
    if len(header) != 16:
        raise WorkbenchError("Invalid RSC85 header length.")
    # For conservative first release, preserve original header/flags. This is safest for same-size decoded patches.
    if len(decoded) != meta.decoded_size:
        raise WorkbenchError("RSC85 repack currently requires decoded size to stay unchanged.")
    payload = compress_payload(decoded, meta.compression)
    if meta.encrypted:
        payload = aes_ecb_16_rounds(payload, decrypt=False)
    return header + payload


def scan_bytes_for_strings(data: bytes, file_label: str, container: str = "") -> list[StringHit]:
    hits: list[StringHit] = []
    for m in ASCII_RE.finditer(data):
        raw = m.group(0)
        text = raw.decode("ascii", errors="replace")
        hits.append(StringHit(file_label, container, "ascii", m.start(), len(raw), text, "same_size_or_shorter"))
    for m in UTF16LE_RE.finditer(data):
        raw = m.group(0)
        try:
            text = raw.decode("utf-16-le", errors="replace")
        except Exception:
            continue
        hits.append(StringHit(file_label, container, "utf16le", m.start(), len(raw), text, "same_size_or_shorter"))
    hits.sort(key=lambda h: (h.offset, h.kind))
    return hits


def scan_file(path: Path, *, container: str = "") -> tuple[list[StringHit], dict]:
    data = read_bytes(path)
    info = {
        "path": str(path),
        "size": len(data),
        "sha256": sha256_bytes(data),
        "mode": "unknown",
        "notes": [],
    }
    meta = parse_rsc85_header(data)
    if meta is not None:
        info["mode"] = "rsc85"
        try:
            decoded, decoded_meta, _header = decode_rsc85(data)
            info["decoded_size"] = len(decoded)
            info["compression"] = decoded_meta.compression
            hits = scan_bytes_for_strings(decoded, str(path), container)
            for h in hits:
                h.note = "decoded_rsc85_payload"
            return hits, info
        except Exception as e:
            info["notes"].append(f"RSC85 decode failed: {e}")
            # Fall through to raw scan too; sometimes raw names still exist.
    if is_probably_text_path(path):
        text, enc = safe_decode_text(data)
        info["mode"] = "text"
        info["encoding"] = enc
        hits: list[StringHit] = []
        # Report line-ish tokens as readable candidates.
        for m in re.finditer(r"[^\x00\r\n\t]{3,}", text):
            snippet = m.group(0).strip()
            if not snippet:
                continue
            hits.append(StringHit(str(path), container, "text", m.start(), len(snippet), snippet[:500], "length_change_ok"))
        return hits, info
    info["mode"] = "binary"
    return scan_bytes_for_strings(data, str(path), container), info


def patch_text_file(path: Path, find: str, replace: str, *, all_matches: bool = True, case_sensitive: bool = True) -> tuple[bytes, dict]:
    data = read_bytes(path)
    text, enc = safe_decode_text(data)
    flags = 0 if case_sensitive else re.IGNORECASE
    count = 0
    if all_matches:
        pattern = re.compile(re.escape(find), flags)
        text2, count = pattern.subn(replace, text)
    else:
        pattern = re.compile(re.escape(find), flags)
        text2, count = pattern.subn(replace, text, count=1)
    return encode_text(text2, enc), {"mode": "text", "encoding": enc, "replacements": count, "length_change": len(text2) - len(text)}


def patch_raw_bytes(data: bytes, find: bytes, replace: bytes, *, all_matches: bool, pad: bytes = b"\x00") -> tuple[bytes, int]:
    if len(replace) > len(find):
        raise WorkbenchError("Binary/RSC85 replacement is longer than target. Use a shorter/equal string or text-mode XML file.")
    repl = replace + pad * (len(find) - len(replace))
    count = data.count(find)
    if count == 0:
        return data, 0
    if all_matches:
        return data.replace(find, repl), count
    return data.replace(find, repl, 1), 1


def encode_find_replace_for_kind(kind: str, find: str, replace: str) -> tuple[bytes, bytes]:
    if kind == "utf16le":
        return find.encode("utf-16-le"), replace.encode("utf-16-le")
    return find.encode("ascii"), replace.encode("ascii")


def patch_binary_file(path: Path, find: str, replace: str, *, all_matches: bool = True, pad_kind: str = "null", string_kind: str = "ascii") -> tuple[bytes, dict]:
    data = read_bytes(path)
    find_b, replace_b = encode_find_replace_for_kind(string_kind, find, replace)
    pad = b"\x00" if pad_kind == "null" else b" "
    if string_kind == "utf16le":
        pad = b"\x00\x00" if pad_kind == "null" else b" \x00"
    patched, count = patch_raw_bytes(data, find_b, replace_b, all_matches=all_matches, pad=pad)
    return patched, {"mode": "binary", "string_kind": string_kind, "replacements": count}


def patch_rsc85_file(path: Path, find: str, replace: str, *, all_matches: bool = True, pad_kind: str = "null", string_kind: str = "ascii") -> tuple[bytes, dict]:
    original = read_bytes(path)
    decoded, meta, header = decode_rsc85(original)
    find_b, replace_b = encode_find_replace_for_kind(string_kind, find, replace)
    pad = b"\x00" if pad_kind == "null" else b" "
    if string_kind == "utf16le":
        pad = b"\x00\x00" if pad_kind == "null" else b" \x00"
    patched_decoded, count = patch_raw_bytes(decoded, find_b, replace_b, all_matches=all_matches, pad=pad)
    if count == 0:
        return original, {"mode": "rsc85", "replacements": 0, "compression": meta.compression, "decoded_size": len(decoded)}
    rebuilt = repack_rsc85(patched_decoded, meta, header)
    # Reopen/decode validation.
    decoded2, meta2, _ = decode_rsc85(rebuilt)
    if decoded2 != patched_decoded:
        raise WorkbenchError("RSC85 validation failed: reopened decoded payload differs from patched payload.")
    return rebuilt, {"mode": "rsc85", "replacements": count, "compression": meta.compression, "decoded_size": len(decoded), "validated": True}


def decide_patch_mode(path: Path, mode: str) -> str:
    if mode != "auto":
        return mode
    data = read_bytes(path)
    if parse_rsc85_header(data) is not None:
        return "rsc85"
    if is_probably_text_path(path):
        return "text"
    return "binary"


def patch_one_file(path: Path, out_path: Path, find: str, replace: str, *, mode: str = "auto", all_matches: bool = True, pad_kind: str = "null", string_kind: str = "ascii", dry_run: bool = False) -> dict:
    chosen = decide_patch_mode(path, mode)
    if chosen == "text":
        patched, manifest = patch_text_file(path, find, replace, all_matches=all_matches)
    elif chosen == "rsc85":
        patched, manifest = patch_rsc85_file(path, find, replace, all_matches=all_matches, pad_kind=pad_kind, string_kind=string_kind)
    elif chosen == "binary":
        patched, manifest = patch_binary_file(path, find, replace, all_matches=all_matches, pad_kind=pad_kind, string_kind=string_kind)
    else:
        raise WorkbenchError(f"Unsupported patch mode: {chosen}")
    manifest.update({
        "input": str(path),
        "output": str(out_path),
        "find": find,
        "replace": replace,
        "input_sha256": sha256_bytes(read_bytes(path)),
        "output_sha256": sha256_bytes(patched),
        "dry_run": dry_run,
    })
    if not dry_run:
        write_bytes(out_path, patched)
    return manifest


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
    else:
        for p in root.rglob("*"):
            if p.is_file():
                yield p


def write_scan_reports(out_dir: Path, hits: list[StringHit], infos: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "strings.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "container", "kind", "offset", "length", "replaceable", "text", "note"])
        writer.writeheader()
        for h in hits:
            writer.writerow(dataclasses.asdict(h))
    with (out_dir / "file_info.json").open("w", encoding="utf-8") as f:
        json.dump(infos, f, indent=2)
    # Simple markdown summary.
    by_file: dict[str, int] = {}
    for h in hits:
        by_file[h.file] = by_file.get(h.file, 0) + 1
    lines = ["# Code RED Mod Workbench Scan", "", f"Tool version: `{TOOL_VERSION}`", "", f"Files scanned: {len(infos)}", f"String candidates: {len(hits)}", "", "## Top files", ""]
    for file, count in sorted(by_file.items(), key=lambda kv: kv[1], reverse=True)[:50]:
        lines.append(f"- `{file}`: {count} candidates")
    lines += ["", "See `strings.csv` for the full candidate table.", ""]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def extract_zip(zip_path: Path, work_dir: Path) -> Path:
    dest = work_dir / zip_path.stem
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest)
    return dest


def rebuild_zip(src_dir: Path, out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in src_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(src_dir).as_posix())


def command_scan(args: argparse.Namespace) -> int:
    in_path = Path(args.input).resolve()
    out_dir = Path(args.out or f"scan_{in_path.stem}_{now_stamp()}").resolve()
    tmp: Optional[tempfile.TemporaryDirectory] = None
    scan_root = in_path
    container = ""
    if in_path.suffix.lower() == ".zip":
        tmp = tempfile.TemporaryDirectory(prefix="codered_scan_zip_")
        scan_root = extract_zip(in_path, Path(tmp.name))
        container = str(in_path)
    hits: list[StringHit] = []
    infos: list[dict] = []
    files = list(iter_files(scan_root))
    for idx, file in enumerate(files, 1):
        try:
            fhits, info = scan_file(file, container=container)
            hits.extend(fhits)
            infos.append(info)
        except Exception as e:
            infos.append({"path": str(file), "error": str(e)})
    write_scan_reports(out_dir, hits, infos)
    print(f"Scan complete: {out_dir}")
    print(f"Files scanned: {len(infos)}")
    print(f"String candidates: {len(hits)}")
    if tmp:
        tmp.cleanup()
    return 0


def command_replace(args: argparse.Namespace) -> int:
    in_path = Path(args.input).resolve()
    if not in_path.exists():
        raise WorkbenchError(f"Input not found: {in_path}")
    out = Path(args.out).resolve() if args.out else None
    all_matches = not args.first_only
    manifest: dict
    if in_path.suffix.lower() == ".zip":
        out_zip = out or in_path.with_name(f"{in_path.stem}_patched_{now_stamp()}.zip")
        with tempfile.TemporaryDirectory(prefix="codered_patch_zip_") as td:
            root = extract_zip(in_path, Path(td))
            manifests = []
            for p in iter_files(root):
                rel = p.relative_to(root)
                try:
                    chosen = decide_patch_mode(p, args.mode)
                    # Only patch files that actually contain the find string in some form.
                    before = read_bytes(p)
                    if chosen == "text":
                        text, _ = safe_decode_text(before)
                        if args.find not in text:
                            continue
                    elif chosen == "rsc85":
                        try:
                            decoded, _, _ = decode_rsc85(before)
                            fb, _ = encode_find_replace_for_kind(args.string_kind, args.find, args.replace)
                            if fb not in decoded:
                                continue
                        except Exception:
                            continue
                    else:
                        fb, _ = encode_find_replace_for_kind(args.string_kind, args.find, args.replace)
                        if fb not in before:
                            continue
                    m = patch_one_file(p, p, args.find, args.replace, mode=chosen, all_matches=all_matches, pad_kind=args.pad, string_kind=args.string_kind, dry_run=False)
                    m["zip_relative_path"] = rel.as_posix()
                    manifests.append(m)
                except Exception as e:
                    manifests.append({"zip_relative_path": rel.as_posix(), "error": str(e)})
            rebuild_zip(root, out_zip)
            manifest = {"input_zip": str(in_path), "output_zip": str(out_zip), "patched_entries": manifests}
            man_path = out_zip.with_suffix(out_zip.suffix + ".manifest.json")
            man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(f"Patched zip: {out_zip}")
            print(f"Manifest: {man_path}")
            return 0
    out_path = out or in_path.with_name(f"{in_path.stem}_patched{in_path.suffix}")
    manifest = patch_one_file(in_path, out_path, args.find, args.replace, mode=args.mode, all_matches=all_matches, pad_kind=args.pad, string_kind=args.string_kind, dry_run=args.dry_run)
    man_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if not args.dry_run:
        print(f"Patched file: {out_path}")
        print(f"Manifest: {man_path}")
    return 0


def command_interactive(args: argparse.Namespace) -> int:
    in_path = Path(args.input).resolve()
    if not in_path.exists():
        raise WorkbenchError(f"Input not found: {in_path}")
    out_dir = Path(args.outdir or f"interactive_{in_path.stem}_{now_stamp()}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Code RED Mod Workbench interactive replacement")
    print(f"Input: {in_path}")
    print("Scanning candidates...")
    hits, info = scan_file(in_path)
    print(f"Mode: {info.get('mode')}  candidates: {len(hits)}")
    if not hits:
        print("No readable candidates found.")
        return 1
    query = input("Filter text contains (blank to list first 80): ").strip()
    filtered = [h for h in hits if (query.lower() in h.text.lower())] if query else hits[:80]
    for i, h in enumerate(filtered[:200], 1):
        short = h.text.replace("\n", "\\n")
        if len(short) > 120:
            short = short[:117] + "..."
        print(f"[{i:03}] {h.kind} off=0x{h.offset:X} len={h.length} {h.replaceable} :: {short}")
    choice = input("Pick candidate number, or enter exact find text: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(filtered[:200]):
        find = filtered[int(choice) - 1].text
        string_kind = filtered[int(choice) - 1].kind if filtered[int(choice) - 1].kind in ("ascii", "utf16le") else "ascii"
    else:
        find = choice
        string_kind = input("String kind [ascii/utf16le] (default ascii): ").strip() or "ascii"
    replace = input(f"Replace `{find}` with: ").strip()
    mode = decide_patch_mode(in_path, "auto")
    out_path = out_dir / in_path.name
    print(f"Patch mode: {mode}")
    print(f"Output: {out_path}")
    confirm = input("Apply? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return 1
    manifest = patch_one_file(in_path, out_path, find, replace, mode=mode, all_matches=True, pad_kind=args.pad, string_kind=string_kind)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Done: {out_path}")
    return 0


def command_info(args: argparse.Namespace) -> int:
    path = Path(args.input).resolve()
    data = read_bytes(path)
    meta = parse_rsc85_header(data)
    info = {"path": str(path), "size": len(data), "sha256": sha256_bytes(data)}
    if meta is not None:
        info["rsc85_header"] = dataclasses.asdict(meta)
        try:
            decoded, meta2, _ = decode_rsc85(data)
            info["decoded"] = {"size": len(decoded), "sha256": sha256_bytes(decoded), "compression": meta2.compression}
            info["decoded_string_candidates"] = len(scan_bytes_for_strings(decoded, str(path)))
        except Exception as e:
            info["decode_error"] = str(e)
    else:
        info["mode_guess"] = "text" if is_probably_text_path(path) else "binary"
    print(json.dumps(info, indent=2))
    return 0



def int_to_bytes(value: int, width: int, endian: str, signed: bool = False) -> bytes:
    if width not in (1, 2, 4, 8):
        raise WorkbenchError("width must be 1, 2, 4, or 8")
    if width == 1:
        return int(value).to_bytes(1, "little", signed=signed)
    return int(value).to_bytes(width, endian, signed=signed)


def bytes_to_int(data: bytes, endian: str, signed: bool = False) -> int:
    return int.from_bytes(data, endian, signed=signed)


def find_all_bytes(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx < 0:
            break
        offsets.append(idx)
        start = idx + 1
    return offsets


def command_find_int(args: argparse.Namespace) -> int:
    path = Path(args.input).resolve()
    data = read_bytes(path)
    mode = decide_patch_mode(path, args.mode)
    container_note = "raw_file"
    if mode == "rsc85":
        decoded, meta, _ = decode_rsc85(data)
        data_to_scan = decoded
        container_note = f"decoded_rsc85:{meta.compression}"
    elif mode == "binary":
        data_to_scan = data
    else:
        text, enc = safe_decode_text(data)
        data_to_scan = encode_text(text, enc)
        container_note = f"text_bytes:{enc}"
    needle = int_to_bytes(args.value, args.width, args.endian, args.signed)
    offsets = find_all_bytes(data_to_scan, needle)
    rows = []
    for off in offsets:
        lo = max(0, off - args.context)
        hi = min(len(data_to_scan), off + args.width + args.context)
        rows.append({
            "offset_hex": f"0x{off:X}",
            "offset": off,
            "value": args.value,
            "width": args.width,
            "endian": args.endian,
            "context_hex": data_to_scan[lo:hi].hex(),
            "container": container_note,
        })
    if args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["offset_hex", "offset", "value", "width", "endian", "context_hex", "container"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"Integer scan wrote: {out}")
    print(json.dumps({"input": str(path), "mode": mode, "value": args.value, "width": args.width, "endian": args.endian, "matches": len(rows), "sample": rows[:25]}, indent=2))
    return 0


def patch_int_data(data: bytes, old: int, new: int, width: int, endian: str, *, offsets: Optional[list[int]], replace_all: bool, signed: bool) -> tuple[bytes, int, list[int]]:
    old_b = int_to_bytes(old, width, endian, signed)
    new_b = int_to_bytes(new, width, endian, signed)
    buf = bytearray(data)
    changed: list[int] = []
    if offsets:
        for off in offsets:
            if off < 0 or off + width > len(buf):
                raise WorkbenchError(f"Offset out of range: 0x{off:X}")
            actual = bytes(buf[off:off+width])
            if actual != old_b and not replace_all:
                raise WorkbenchError(f"Offset 0x{off:X} contains {actual.hex()}, expected {old_b.hex()}. Use --force-offset to patch anyway.")
            buf[off:off+width] = new_b
            changed.append(off)
        return bytes(buf), len(changed), changed
    matches = find_all_bytes(data, old_b)
    if not replace_all:
        raise WorkbenchError(f"Found {len(matches)} matches. Use --offset 0x... for one target or --all to patch all matches.")
    for off in matches:
        buf[off:off+width] = new_b
        changed.append(off)
    return bytes(buf), len(changed), changed


def command_replace_int(args: argparse.Namespace) -> int:
    path = Path(args.input).resolve()
    out_path = Path(args.out).resolve() if args.out else path.with_name(f"{path.stem}_intpatched{path.suffix}")
    mode = decide_patch_mode(path, args.mode)
    offsets = None
    if args.offset:
        offsets = [int(x, 0) for x in args.offset]
    original = read_bytes(path)
    if mode == "rsc85":
        decoded, meta, header = decode_rsc85(original)
        patched_decoded, count, changed_offsets = patch_int_data(decoded, args.old, args.new, args.width, args.endian, offsets=offsets, replace_all=args.all or args.force_offset, signed=args.signed)
        rebuilt = repack_rsc85(patched_decoded, meta, header)
        decoded2, _, _ = decode_rsc85(rebuilt)
        if decoded2 != patched_decoded:
            raise WorkbenchError("RSC85 validation failed after integer patch.")
        patched = rebuilt
        manifest_extra = {"compression": meta.compression, "decoded_size": len(decoded), "validated": True}
    elif mode == "binary":
        patched, count, changed_offsets = patch_int_data(original, args.old, args.new, args.width, args.endian, offsets=offsets, replace_all=args.all or args.force_offset, signed=args.signed)
        manifest_extra = {}
    else:
        raise WorkbenchError("replace-int supports binary and rsc85 modes only. Use text replace for XML/text.")
    manifest = {
        "mode": mode,
        "input": str(path),
        "output": str(out_path),
        "old": args.old,
        "new": args.new,
        "width": args.width,
        "endian": args.endian,
        "signed": args.signed,
        "replacements": count,
        "changed_offsets_hex": [f"0x{x:X}" for x in changed_offsets],
        "input_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(patched),
        "dry_run": args.dry_run,
        **manifest_extra,
    }
    if not args.dry_run:
        write_bytes(out_path, patched)
        out_path.with_suffix(out_path.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if not args.dry_run:
        print(f"Patched file: {out_path}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codered_mod_workbench",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(r"""
        Code RED Mod Workbench - conservative scanner/patcher.

        Examples:
          py -3 codered_mod_workbench.py scan medium_update_thread.wsc --out reports\medium_scan
          py -3 codered_mod_workbench.py replace medium_update_thread.wsc --find beh_grave01x --replace dlc02x --out patched\medium_update_thread.wsc
          py -3 codered_mod_workbench.py interactive savegame.sc.xml
          py -3 codered_mod_workbench.py replace netstats.zip --find "NetMachine.Authenticate" --replace "//NetMachine.Authenticate" --out netstats_patched.zip
        """),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan readable/replaceable candidates")
    s.add_argument("input")
    s.add_argument("--out")
    s.set_defaults(func=command_scan)

    i = sub.add_parser("info", help="print file/RSC85 info")
    i.add_argument("input")
    i.set_defaults(func=command_info)

    r = sub.add_parser("replace", help="replace text/string bytes and save a patched copy")
    r.add_argument("input")
    r.add_argument("--find", required=True)
    r.add_argument("--replace", required=True)
    r.add_argument("--out")
    r.add_argument("--mode", choices=["auto", "text", "binary", "rsc85"], default="auto")
    r.add_argument("--pad", choices=["null", "space"], default="null", help="padding for shorter binary/RSC85 replacements")
    r.add_argument("--string-kind", choices=["ascii", "utf16le"], default="ascii")
    r.add_argument("--first-only", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    r.set_defaults(func=command_replace)

    it = sub.add_parser("interactive", help="interactive candidate picker for one file")
    it.add_argument("input")
    it.add_argument("--outdir")
    it.add_argument("--pad", choices=["null", "space"], default="null")
    it.set_defaults(func=command_interactive)


    fi = sub.add_parser("find-int", help="find integer/enum byte patterns in binary or decoded RSC85 payloads")
    fi.add_argument("input")
    fi.add_argument("--value", type=lambda x: int(x, 0), required=True)
    fi.add_argument("--width", type=int, choices=[1, 2, 4, 8], default=2)
    fi.add_argument("--endian", choices=["little", "big"], default="little")
    fi.add_argument("--signed", action="store_true")
    fi.add_argument("--mode", choices=["auto", "binary", "rsc85", "text"], default="auto")
    fi.add_argument("--context", type=int, default=16)
    fi.add_argument("--out")
    fi.set_defaults(func=command_find_int)

    ri = sub.add_parser("replace-int", help="replace integer/enum byte patterns in binary or decoded RSC85 payloads")
    ri.add_argument("input")
    ri.add_argument("--old", type=lambda x: int(x, 0), required=True)
    ri.add_argument("--new", type=lambda x: int(x, 0), required=True)
    ri.add_argument("--width", type=int, choices=[1, 2, 4, 8], default=2)
    ri.add_argument("--endian", choices=["little", "big"], default="little")
    ri.add_argument("--signed", action="store_true")
    ri.add_argument("--mode", choices=["auto", "binary", "rsc85"], default="auto")
    ri.add_argument("--offset", action="append", help="decoded/raw offset to patch, e.g. --offset 0x35D1A. Can be repeated.")
    ri.add_argument("--all", action="store_true", help="patch every matching old value. Risky; prefer offsets.")
    ri.add_argument("--force-offset", action="store_true", help="with --offset, patch even if old value check does not match")
    ri.add_argument("--out")
    ri.add_argument("--dry-run", action="store_true")
    ri.set_defaults(func=command_replace_int)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except WorkbenchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
