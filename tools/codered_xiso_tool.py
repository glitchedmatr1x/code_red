from __future__ import annotations

"""Code RED Xbox ISO / XDVDFS helper.

Public-safe, copy-first tooling for Xbox/Xenia research.

This module indexes XDVDFS-style Xbox disc images, extracts selected files, and
builds replacement plans. It intentionally does not modify original ISOs in
place. Write-back support is limited to copied-output original-size sector
replacement. Smaller files are padded to the original directory size; larger
files are refused because changed directory sizes require a real filesystem
rebuild or extracted-folder/Xenia layout.

The parser is conservative and heuristic-friendly:
- It scans for the XDVDFS volume magic (MICROSOFT*XBOX*MEDIA).
- It treats the root sector/root size fields as little-endian values at +20/+24.
- It parses the common variable-length XDVDFS directory entry layout.
- If directory parsing fails, it emits a readable diagnostic instead of guessing.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

SECTOR_SIZE = 2048
XDVDFS_MAGIC = b"MICROSOFT*XBOX*MEDIA"
PRINTABLE_RE = re.compile(rb"[\x20-\x7E]{4,}")
FOCUS_KEYWORDS = [
    "content.rpf", "layer_0.rpf", "layer_1.rpf", "flash.rpf",
    "rdr2init", "initpopulation", "pausemenu", "networking", "lobby",
    "avatar", "profile", "freeroam", "gamespy", "auth", "titleupdate",
    "zombiepack", "dlc_inventory", "mp_avatar", "xex", "default.xex",
]
RPF_REPLACEMENT_EXTS = {".rpf"}
PAD_BYTE_DEFAULT = 0


@dataclass
class VolumeDescriptor:
    descriptor_offset: int
    partition_offset: int
    magic_offset_in_sector: int
    root_sector: int
    root_size: int
    sector_size: int = SECTOR_SIZE
    confidence: str = "candidate"
    notes: list[str] = field(default_factory=list)


@dataclass
class IsoFileEntry:
    path: str
    name: str
    is_dir: bool
    sector: int
    size: int
    absolute_offset: int
    allocated_bytes: int
    attributes: int
    level: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class IsoReport:
    iso_path: str
    iso_size: int
    scanned_at: str
    descriptors: list[dict]
    selected_descriptor: dict | None
    files: list[dict]
    focus_files: list[dict]
    warnings: list[str]


def now_stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def sha256_file(path: Path, limit: int | None = None) -> str:
    h = hashlib.sha256()
    remaining = limit
    with path.open("rb") as fh:
        while True:
            if remaining is not None and remaining <= 0:
                break
            chunk_size = 1024 * 1024
            if remaining is not None:
                chunk_size = min(chunk_size, remaining)
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return h.hexdigest().upper()

def parse_bytes_argument(value: str | None, *, file_path: str | None = None, encoding: str = "utf-8") -> bytes:
    """Parse a CLI byte argument from file/hex/text forms.

    Exactly one source should be supplied by callers. Text mode is intentionally
    plain and same-length safe; it is not a script compiler.
    """
    if file_path:
        return Path(file_path).read_bytes()
    if value is None:
        return b""
    text = value
    is_hex = text.startswith("hex:")
    if is_hex:
        text = text[4:]
        cleaned = re.sub(r"[^0-9A-Fa-f]", "", text)
        if len(cleaned) % 2:
            raise ValueError("Hex byte strings must contain an even number of hex digits")
        return bytes.fromhex(cleaned)
    return text.encode(encoding)


def read_iso_range(iso_path: Path, absolute_offset: int, size: int) -> bytes:
    if size < 0:
        raise ValueError("Cannot read a negative byte range")
    with iso_path.open("rb") as fh:
        fh.seek(absolute_offset)
        data = fh.read(size)
    if len(data) != size:
        raise IOError(f"Unexpected EOF reading {size:,} bytes at ISO offset {absolute_offset:,}")
    return data


def find_pattern_in_iso_entry(iso_path: Path, entry: IsoFileEntry, needle: bytes, *, max_matches: int = 50, chunk_size: int = 4 * 1024 * 1024) -> list[dict]:
    """Find a byte pattern inside one ISO file entry without extracting it.

    Offsets are reported both relative to the selected ISO entry, which is
    useful for repeatable RPF-relative recipes, and absolute to the ISO, which
    is what the direct patch writer uses.
    """
    if not needle:
        raise ValueError("Needle cannot be empty")
    if entry.is_dir:
        raise ValueError("Cannot search inside a directory entry")
    matches: list[dict] = []
    overlap = max(0, len(needle) - 1)
    processed = 0
    tail = b""
    with iso_path.open("rb") as fh:
        fh.seek(entry.absolute_offset)
        remaining = entry.size
        while remaining > 0:
            chunk = fh.read(min(chunk_size, remaining))
            if not chunk:
                break
            data = tail + chunk
            base_rel = processed - len(tail)
            pos = 0
            while True:
                idx = data.find(needle, pos)
                if idx < 0:
                    break
                rel = base_rel + idx
                if 0 <= rel < entry.size:
                    matches.append({
                        "entry_path": entry.path,
                        "relative_offset": rel,
                        "absolute_iso_offset": entry.absolute_offset + rel,
                        "length": len(needle),
                    })
                    if len(matches) >= max_matches:
                        return matches
                pos = idx + 1
            processed += len(chunk)
            remaining -= len(chunk)
            tail = data[-overlap:] if overlap else b""
    return matches


def direct_nested_patch_plan(iso_path: Path, entry: IsoFileEntry, old_bytes: bytes, new_bytes: bytes, *, inner_offset: int | None = None, match_index: int = 0, max_matches: int = 50) -> dict:
    if len(old_bytes) != len(new_bytes):
        raise ValueError(f"Direct nested patch requires same-length bytes ({len(old_bytes)} != {len(new_bytes)})")
    if not old_bytes:
        raise ValueError("Old bytes cannot be empty")
    if entry.is_dir:
        raise ValueError("Cannot patch inside a directory entry")
    if inner_offset is not None:
        if inner_offset < 0 or inner_offset + len(old_bytes) > entry.size:
            raise ValueError("Inner offset range is outside the selected ISO entry")
        absolute = entry.absolute_offset + inner_offset
        current = read_iso_range(iso_path, absolute, len(old_bytes))
        matches = [{
            "entry_path": entry.path,
            "relative_offset": inner_offset,
            "absolute_iso_offset": absolute,
            "length": len(old_bytes),
            "current_matches_old": current == old_bytes,
        }]
        selected = matches[0]
    else:
        matches = find_pattern_in_iso_entry(iso_path, entry, old_bytes, max_matches=max_matches)
        if not matches:
            raise ValueError("Old byte pattern was not found inside the selected ISO entry")
        if match_index < 0 or match_index >= len(matches):
            raise ValueError(f"Match index {match_index} is outside match count {len(matches)}")
        selected = matches[match_index]
        current = read_iso_range(iso_path, selected["absolute_iso_offset"], len(old_bytes))
        selected["current_matches_old"] = current == old_bytes
    if not selected.get("current_matches_old", False):
        raise ValueError("Current ISO bytes do not match the expected old bytes; refusing direct patch")
    return {
        "iso": str(iso_path),
        "container_path": entry.path,
        "container_entry_size": entry.size,
        "container_absolute_offset": entry.absolute_offset,
        "patch_mode": "direct_nested_same_size",
        "old_size": len(old_bytes),
        "new_size": len(new_bytes),
        "match_count": len(matches),
        "selected_match_index": match_index if inner_offset is None else None,
        "selected_relative_offset": selected["relative_offset"],
        "selected_absolute_iso_offset": selected["absolute_iso_offset"],
        "old_sha256": hashlib.sha256(old_bytes).hexdigest().upper(),
        "new_sha256": hashlib.sha256(new_bytes).hexdigest().upper(),
        "safe_for_copy_write": True,
        "requires_rpf_rebuild": False,
        "requires_xdvdfs_rebuild": False,
        "decision": "copy-write allowed: same-size nested byte patch inside existing ISO/RPF allocation",
        "notes": [
            "The original ISO is never modified in-place.",
            "This patches bytes inside the selected ISO file entry, such as layer_0.rpf, without rewriting the RPF container.",
            "It is safe only for same-length byte/string changes where the old bytes match exactly.",
            "It cannot import larger inner files or update RPF directory tables.",
            "Use this for surgical XML/string/constant probes, not full RPF rebuilds.",
        ],
    }


def patch_copy_nested_same_size(iso_path: Path, entry: IsoFileEntry, old_bytes: bytes, new_bytes: bytes, out_iso: Path, *, inner_offset: int | None = None, match_index: int = 0, max_matches: int = 50) -> dict:
    plan = direct_nested_patch_plan(iso_path, entry, old_bytes, new_bytes, inner_offset=inner_offset, match_index=match_index, max_matches=max_matches)
    out_iso.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(iso_path, out_iso)
    absolute = int(plan["selected_absolute_iso_offset"])
    with out_iso.open("r+b") as fh:
        fh.seek(absolute)
        before = fh.read(len(old_bytes))
        if before != old_bytes:
            raise IOError("Copied ISO verification failed before write: old bytes do not match")
        fh.seek(absolute)
        fh.write(new_bytes)
        fh.flush()
    after = read_iso_range(out_iso, absolute, len(new_bytes))
    if after != new_bytes:
        raise IOError("Nested patch verification failed after write")
    plan["output_iso"] = str(out_iso)
    plan["verification"] = {
        "ok": True,
        "patched_absolute_iso_offset": absolute,
        "patched_relative_offset": plan["selected_relative_offset"],
        "verified_bytes": len(new_bytes),
        "new_bytes_sha256": hashlib.sha256(after).hexdigest().upper(),
    }
    plan["output_iso_sha256_head_64mb"] = sha256_file(out_iso, limit=64 * 1024 * 1024)
    plan["decision"] = "nested same-size patch completed on copied ISO and verified"
    return plan


def read_u16le(blob: bytes, offset: int) -> int:
    if offset + 2 > len(blob):
        return 0
    return int.from_bytes(blob[offset:offset + 2], "little")


def read_u32le(blob: bytes, offset: int) -> int:
    if offset + 4 > len(blob):
        return 0
    return int.from_bytes(blob[offset:offset + 4], "little")


def safe_name(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = text.replace("\\", "/").strip("\x00/ ")
    text = re.sub(r"[\r\n\t]+", "_", text)
    text = re.sub(r"/++", "/", text)
    return text or "<unnamed>"


def tags_for_path(path: str) -> list[str]:
    lower = path.lower()
    tags: list[str] = []
    if any(key in lower for key in ["avatar", "profile", "lobby", "network", "signin", "auth", "gamespy", "freeroam"]):
        tags.append("profile/network/freeroam")
    if any(key in lower for key in ["rdr2init", "initpopulation", "population", "zombiepack", "dlc_inventory"]):
        tags.append("init/pop/zombie")
    if lower.endswith(".rpf"):
        tags.append("rpf-container")
    if lower.endswith(".xex"):
        tags.append("executable")
    if lower.endswith((".xsc", ".sco", ".csc", ".wsc")):
        tags.append("script")
    return tags


def find_volume_descriptors(iso_path: Path, scan_limit_bytes: int = 256 * 1024 * 1024) -> list[VolumeDescriptor]:
    size = iso_path.stat().st_size
    limit = min(size, scan_limit_bytes)
    descriptors: list[VolumeDescriptor] = []
    with iso_path.open("rb") as fh:
        data = fh.read(limit)
    start = 0
    while True:
        idx = data.find(XDVDFS_MAGIC, start)
        if idx < 0:
            break
        sector_base = (idx // SECTOR_SIZE) * SECTOR_SIZE
        magic_offset = idx - sector_base
        # The common XDVDFS descriptor puts root sector/root size right after the 20-byte magic.
        root_sector = read_u32le(data, idx + len(XDVDFS_MAGIC))
        root_size = read_u32le(data, idx + len(XDVDFS_MAGIC) + 4)
        notes: list[str] = []
        confidence = "candidate"
        if 0 < root_size < 256 * 1024 * 1024 and root_sector > 0:
            root_abs = sector_base + root_sector * SECTOR_SIZE
            if 0 <= root_abs < size:
                confidence = "strong"
            else:
                notes.append("Root sector points outside image when using sector base as partition offset.")
        else:
            notes.append("Root fields are outside normal heuristic range.")
        # Some images store root sectors relative to the game partition; others behave like absolute sectors.
        # Add both candidates so index_xdvdfs can select the one that actually parses.
        for base_name, base_offset in (("absolute-sector", 0), ("descriptor-sector-base", sector_base)):
            cand_notes = list(notes) + [f"partition-base-candidate={base_name}"]
            cand_conf = confidence
            root_abs = base_offset + root_sector * SECTOR_SIZE
            if not (0 <= root_abs < size):
                cand_conf = "candidate"
                cand_notes.append("Root sector points outside image for this base candidate.")
            descriptors.append(VolumeDescriptor(
                descriptor_offset=idx,
                partition_offset=base_offset,
                magic_offset_in_sector=magic_offset,
                root_sector=root_sector,
                root_size=root_size,
                confidence=cand_conf,
                notes=cand_notes,
            ))
        start = idx + 1
    # Prefer unique root locations, highest confidence first.
    unique: dict[tuple[int, int, int], VolumeDescriptor] = {}
    for desc in descriptors:
        key = (desc.partition_offset, desc.root_sector, desc.root_size)
        if key not in unique or unique[key].confidence != "strong":
            unique[key] = desc
    return sorted(unique.values(), key=lambda d: (d.confidence != "strong", d.descriptor_offset))


def parse_directory_entries(dir_blob: bytes, base_path: str, level: int = 0) -> list[tuple[str, bool, int, int, int, int]]:
    """Parse a linear XDVDFS directory extent.

    Returns tuples of (path, is_dir, sector, size, attrs, entry_offset).
    The left/right tree pointers are intentionally ignored; scanning the extent linearly
    is more robust for read-only inventory generation.
    """
    rows: list[tuple[str, bool, int, int, int, int]] = []
    pos = 0
    while pos + 14 <= len(dir_blob):
        entry_off = pos
        left = read_u16le(dir_blob, pos)
        right = read_u16le(dir_blob, pos + 2)
        sector = read_u32le(dir_blob, pos + 4)
        size = read_u32le(dir_blob, pos + 8)
        attrs = dir_blob[pos + 12]
        name_len = dir_blob[pos + 13]
        if name_len == 0:
            # Align forward once; long runs of zeroes mark unused tail.
            if all(b == 0 for b in dir_blob[pos: min(len(dir_blob), pos + 32)]):
                break
            pos += 4
            continue
        raw_end = pos + 14 + name_len
        if raw_end > len(dir_blob):
            break
        name = safe_name(dir_blob[pos + 14:raw_end])
        # Reject obvious garbage entries.
        if "/" in name or name in {".", ".."}:
            pos = ((raw_end + 3) // 4) * 4
            continue
        full = f"{base_path}/{name}" if base_path else name
        is_dir = bool(attrs & 0x10) or ("." not in name and size % SECTOR_SIZE == 0 and size < 128 * 1024 * 1024)
        rows.append((full, is_dir, sector, size, attrs, entry_off))
        pos = ((raw_end + 3) // 4) * 4
    return rows


def read_extent(iso_path: Path, offset: int, size: int, max_size: int = 64 * 1024 * 1024) -> bytes:
    if size < 0 or size > max_size:
        raise ValueError(f"Refusing to read suspicious extent size: {size:,}")
    with iso_path.open("rb") as fh:
        fh.seek(offset)
        return fh.read(size)


def index_xdvdfs(iso_path: Path, descriptor: VolumeDescriptor | None = None, max_entries: int = 50000, max_depth: int = 16) -> tuple[list[IsoFileEntry], list[str], VolumeDescriptor | None, list[VolumeDescriptor]]:
    warnings: list[str] = []
    descriptors = find_volume_descriptors(iso_path)
    if descriptor is None:
        descriptor = descriptors[0] if descriptors else None
    if descriptor is None:
        warnings.append("No XDVDFS volume descriptor found. This may be an unsupported image, encrypted image, or extracted-folder-only workflow.")
        return [], warnings, None, descriptors
    iso_size = iso_path.stat().st_size

    def parse_with_descriptor(candidate: VolumeDescriptor) -> tuple[list[IsoFileEntry], list[str]]:
        local_warnings: list[str] = []
        files: list[IsoFileEntry] = []
        visited_dirs: set[tuple[int, int]] = set()

        def visit_dir(path: str, sector: int, size: int, level: int) -> None:
            if len(files) >= max_entries:
                return
            if level > max_depth:
                local_warnings.append(f"Max directory depth reached at {path or '<root>'}")
                return
            key = (sector, size)
            if key in visited_dirs:
                return
            visited_dirs.add(key)
            abs_off = candidate.partition_offset + sector * SECTOR_SIZE
            if abs_off < 0 or abs_off >= iso_size:
                local_warnings.append(f"Directory {path or '<root>'} points outside ISO at sector {sector}")
                return
            try:
                blob = read_extent(iso_path, abs_off, size)
            except Exception as exc:
                local_warnings.append(f"Failed to read directory {path or '<root>'}: {exc}")
                return
            rows = parse_directory_entries(blob, path, level)
            for full, is_dir, child_sector, child_size, attrs, _entry_off in rows:
                child_abs = candidate.partition_offset + child_sector * SECTOR_SIZE
                alloc = int(math.ceil(child_size / SECTOR_SIZE) * SECTOR_SIZE) if child_size else 0
                entry = IsoFileEntry(
                    path=full,
                    name=full.rsplit("/", 1)[-1],
                    is_dir=is_dir,
                    sector=child_sector,
                    size=child_size,
                    absolute_offset=child_abs,
                    allocated_bytes=alloc,
                    attributes=attrs,
                    level=level,
                    tags=tags_for_path(full),
                )
                files.append(entry)
                if is_dir and child_size > 0 and len(files) < max_entries:
                    visit_dir(full, child_sector, child_size, level + 1)

        visit_dir("", candidate.root_sector, candidate.root_size, 0)
        return files, local_warnings

    best_desc = descriptor
    best_files: list[IsoFileEntry] = []
    best_warn: list[str] = []
    candidates = descriptors or [descriptor]
    for cand in candidates:
        cand_files, cand_warn = parse_with_descriptor(cand)
        if len(cand_files) > len(best_files):
            best_desc, best_files, best_warn = cand, cand_files, cand_warn
    descriptor = best_desc
    files = best_files
    warnings.extend(best_warn)
    return files, warnings, descriptor, descriptors

def build_report(iso_path: Path, max_entries: int = 50000) -> IsoReport:
    files, warnings, selected, descriptors = index_xdvdfs(iso_path, max_entries=max_entries)
    focus = [asdict(row) for row in files if row.tags or any(k in row.path.lower() for k in FOCUS_KEYWORDS)]
    return IsoReport(
        iso_path=str(iso_path),
        iso_size=iso_path.stat().st_size,
        scanned_at=now_stamp(),
        descriptors=[asdict(d) for d in descriptors],
        selected_descriptor=asdict(selected) if selected else None,
        files=[asdict(row) for row in files],
        focus_files=focus,
        warnings=warnings,
    )


def write_reports(report: IsoReport, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dict = asdict(report)
    json_path = out_dir / "xiso_report.json"
    csv_path = out_dir / "xiso_file_tree.csv"
    focus_path = out_dir / "xiso_focus_files.csv"
    packet_path = out_dir / "xiso_gpt_packet.json"
    json_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "is_dir", "sector", "size", "absolute_offset", "allocated_bytes", "attributes", "tags"])
        writer.writeheader()
        for row in report_dict["files"]:
            writer.writerow({
                "path": row["path"],
                "is_dir": row["is_dir"],
                "sector": row["sector"],
                "size": row["size"],
                "absolute_offset": row["absolute_offset"],
                "allocated_bytes": row["allocated_bytes"],
                "attributes": row["attributes"],
                "tags": ";".join(row.get("tags", [])),
            })
    with focus_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "is_dir", "sector", "size", "absolute_offset", "allocated_bytes", "tags"])
        writer.writeheader()
        for row in report_dict["focus_files"]:
            writer.writerow({
                "path": row["path"],
                "is_dir": row["is_dir"],
                "sector": row["sector"],
                "size": row["size"],
                "absolute_offset": row["absolute_offset"],
                "allocated_bytes": row["allocated_bytes"],
                "tags": ";".join(row.get("tags", [])),
            })
    packet = {
        "tool": "Code RED XISO/XDVDFS Tool",
        "iso_name": Path(report.iso_path).name,
        "iso_size": report.iso_size,
        "descriptor_count": len(report.descriptors),
        "selected_descriptor": report.selected_descriptor,
        "file_count": len(report.files),
        "focus_file_count": len(report.focus_files),
        "focus_preview": report.focus_files[:120],
        "warnings": report.warnings,
        "safe_notes": [
            "The tool indexes user-supplied ISOs locally and does not bundle game files.",
            "Replacement write-back is copy-first and exact-size by default.",
            "Larger replacements require an extracted Xenia folder layout or a real ISO rebuild.",
        ],
    }
    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "focus_csv": str(focus_path),
        "gpt_packet": str(packet_path),
    }


def find_entry(report: IsoReport, wanted_path: str) -> IsoFileEntry:
    wanted = wanted_path.replace("\\", "/").strip("/").lower()
    for row in report.files:
        path = row["path"] if isinstance(row, dict) else row.path
        if path.replace("\\", "/").strip("/").lower() == wanted:
            return IsoFileEntry(**row) if isinstance(row, dict) else row
    # suffix fallback helps when user searches for layer_0.rpf from a long path.
    matches = []
    for row in report.files:
        path = row["path"] if isinstance(row, dict) else row.path
        if path.lower().endswith(wanted):
            matches.append(IsoFileEntry(**row) if isinstance(row, dict) else row)
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise KeyError(f"Ambiguous path {wanted_path!r}: {len(matches)} matches")
    raise KeyError(f"Path not found in ISO index: {wanted_path}")


def extract_file(iso_path: Path, entry: IsoFileEntry, out_path: Path) -> Path:
    if entry.is_dir:
        raise ValueError("Cannot extract a directory entry as a file")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with iso_path.open("rb") as src, out_path.open("wb") as dst:
        src.seek(entry.absolute_offset)
        remaining = entry.size
        while remaining > 0:
            chunk = src.read(min(1024 * 1024, remaining))
            if not chunk:
                raise IOError("Unexpected EOF while extracting ISO file")
            dst.write(chunk)
            remaining -= len(chunk)
    return out_path


def replacement_plan(iso_path: Path, entry: IsoFileEntry, replacement: Path) -> dict:
    repl_size = replacement.stat().st_size
    exact_size = repl_size == entry.size
    smaller = repl_size < entry.size
    larger = repl_size > entry.size
    fits_allocation = repl_size <= entry.allocated_bytes
    ext = Path(entry.path).suffix.lower()
    can_copy_write_exact = exact_size
    can_copy_write_padded = repl_size <= entry.size
    if exact_size:
        decision = "copy-write allowed: exact original size"
    elif smaller:
        decision = "copy-write allowed with zero-padding to original size"
    else:
        decision = "refuse ISO write-back: replacement is larger than original directory size"
    return {
        "iso": str(iso_path),
        "target_path": entry.path,
        "target_offset": entry.absolute_offset,
        "target_sector": entry.sector,
        "original_size": entry.size,
        "allocated_bytes": entry.allocated_bytes,
        "replacement": str(replacement),
        "replacement_size": repl_size,
        "replacement_sha256": sha256_file(replacement),
        "entry_extension": ext,
        "is_rpf_target": ext in RPF_REPLACEMENT_EXTS,
        "exact_size_safe_for_copy_write": can_copy_write_exact,
        "smaller_safe_with_padding": smaller,
        "safe_copy_write_with_padding": can_copy_write_padded,
        "fits_original_allocation": fits_allocation,
        "requires_directory_rebuild": larger,
        "bytes_to_pad": max(0, entry.size - repl_size),
        "decision": decision,
        "notes": [
            "Code RED never modifies the original ISO in-place.",
            "Xbox XDVDFS directory metadata stores the file size. Writing a larger file without rebuilding metadata corrupts or truncates the effective file.",
            "Exact-size replacements are safest.",
            "Smaller replacements are made ISO-safe by padding the written sector range back to the original file size.",
            "Larger replacements must use an extracted Xenia folder layout or a future full XDVDFS rebuild/relayout path.",
        ],
    }


def write_padded_replacement(replacement: Path, original_size: int, out_path: Path, pad_byte: int = PAD_BYTE_DEFAULT) -> dict:
    repl_size = replacement.stat().st_size
    if repl_size > original_size:
        raise ValueError(f"Replacement is larger than original size ({repl_size:,} > {original_size:,}); refusing padded staging.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    remaining_pad = original_size - repl_size
    with replacement.open("rb") as src, out_path.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
        if remaining_pad:
            pad = bytes([pad_byte]) * min(1024 * 1024, remaining_pad)
            while remaining_pad > 0:
                chunk = pad if remaining_pad >= len(pad) else bytes([pad_byte]) * remaining_pad
                dst.write(chunk)
                remaining_pad -= len(chunk)
    return {
        "replacement": str(replacement),
        "staged_exact_file": str(out_path),
        "original_replacement_size": repl_size,
        "staged_size": out_path.stat().st_size,
        "pad_byte": pad_byte,
        "sha256": sha256_file(out_path),
    }


def verify_iso_region(iso_path: Path, entry: IsoFileEntry, expected_file: Path) -> dict:
    expected_size = expected_file.stat().st_size
    if expected_size != entry.size:
        raise ValueError("Verification file must match the original XDVDFS entry size")
    h_iso = hashlib.sha256()
    h_expected = hashlib.sha256()
    with iso_path.open("rb") as iso_fh, expected_file.open("rb") as exp_fh:
        iso_fh.seek(entry.absolute_offset)
        remaining = entry.size
        while remaining > 0:
            amount = min(1024 * 1024, remaining)
            iso_chunk = iso_fh.read(amount)
            exp_chunk = exp_fh.read(amount)
            if len(iso_chunk) != len(exp_chunk):
                return {"ok": False, "reason": "unexpected EOF during verification"}
            h_iso.update(iso_chunk)
            h_expected.update(exp_chunk)
            remaining -= amount
    return {
        "ok": h_iso.digest() == h_expected.digest(),
        "iso_region_sha256": h_iso.hexdigest().upper(),
        "expected_sha256": h_expected.hexdigest().upper(),
        "verified_bytes": entry.size,
    }


def replace_file_copy_exact(iso_path: Path, entry: IsoFileEntry, replacement: Path, out_iso: Path) -> dict:
    plan = replacement_plan(iso_path, entry, replacement)
    if not plan["exact_size_safe_for_copy_write"]:
        raise ValueError("Refusing exact copy-write because replacement is not exact size. Use replace-copy-safe to allow smaller padded replacements, or export-overlay for larger files.")
    out_iso.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(iso_path, out_iso)
    with out_iso.open("r+b") as fh, replacement.open("rb") as repl:
        fh.seek(entry.absolute_offset)
        shutil.copyfileobj(repl, fh, length=1024 * 1024)
    verify = verify_iso_region(out_iso, entry, replacement)
    if not verify.get("ok"):
        raise IOError("Copy-write verification failed")
    plan["output_iso"] = str(out_iso)
    plan["output_iso_sha256_head_64mb"] = sha256_file(out_iso, limit=64 * 1024 * 1024)
    plan["verification"] = verify
    plan["decision"] = "exact copy-write completed and verified"
    return plan


def replace_file_copy_safe(iso_path: Path, entry: IsoFileEntry, replacement: Path, out_iso: Path, staging_dir: Path | None = None) -> dict:
    plan = replacement_plan(iso_path, entry, replacement)
    if not plan["safe_copy_write_with_padding"]:
        raise ValueError("Refusing ISO write-back because replacement is larger than the original XDVDFS file size. Use export-overlay or rebuild the disc layout.")
    out_iso.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = staging_dir or (out_iso.parent / "codered_staged_replacements")
    staged = staging_dir / (Path(entry.path).name + ".exactsize")
    staged_info = write_padded_replacement(replacement, entry.size, staged)
    shutil.copy2(iso_path, out_iso)
    with out_iso.open("r+b") as fh, staged.open("rb") as repl:
        fh.seek(entry.absolute_offset)
        shutil.copyfileobj(repl, fh, length=1024 * 1024)
    verify = verify_iso_region(out_iso, entry, staged)
    if not verify.get("ok"):
        raise IOError("Safe copy-write verification failed")
    plan["staging"] = staged_info
    plan["output_iso"] = str(out_iso)
    plan["output_iso_sha256_head_64mb"] = sha256_file(out_iso, limit=64 * 1024 * 1024)
    plan["verification"] = verify
    plan["decision"] = "safe copy-write completed and verified"
    return plan


def export_xenia_overlay(entry: IsoFileEntry, replacement: Path, out_dir: Path, iso_path: Path | None = None) -> dict:
    target = out_dir / "xenia_extracted_overlay" / entry.path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(replacement, target)
    manifest = {
        "tool": "Code RED XISO overlay exporter",
        "iso": str(iso_path) if iso_path else None,
        "target_path": entry.path,
        "replacement": str(replacement),
        "overlay_file": str(target),
        "replacement_size": replacement.stat().st_size,
        "original_size": entry.size,
        "reason": "Use this overlay/extracted-folder route when the replacement is larger than the original ISO file entry or when you want to avoid ISO mutation.",
        "notes": [
            "This does not include game files except the user-provided replacement file.",
            "Merge this into a user-owned extracted Xenia game folder at the same path.",
            "For full ISO rebuild support, Code RED needs a future XDVDFS relayout/rebuild pass.",
        ],
    }
    manifest_path = out_dir / "CODE_RED_XENIA_OVERLAY_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _bytes_from_nested_args(args: argparse.Namespace) -> tuple[bytes, bytes]:
    old_sources = [bool(getattr(args, "old", None)), bool(getattr(args, "old_hex", None)), bool(getattr(args, "old_file", None))]
    new_sources = [bool(getattr(args, "new", None)), bool(getattr(args, "new_hex", None)), bool(getattr(args, "new_file", None))]
    if sum(old_sources) != 1 or sum(new_sources) != 1:
        raise ValueError("Provide exactly one old source and one new source: --old/--old-hex/--old-file and --new/--new-hex/--new-file")
    old_value = getattr(args, "old_hex", None) or getattr(args, "old", None)
    new_value = getattr(args, "new_hex", None) or getattr(args, "new", None)
    if getattr(args, "old_hex", None):
        old_value = "hex:" + old_value
    if getattr(args, "new_hex", None):
        new_value = "hex:" + new_value
    old_bytes = parse_bytes_argument(old_value, file_path=getattr(args, "old_file", None), encoding=getattr(args, "encoding", "utf-8"))
    new_bytes = parse_bytes_argument(new_value, file_path=getattr(args, "new_file", None), encoding=getattr(args, "encoding", "utf-8"))
    return old_bytes, new_bytes


def cmd_find_nested(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    needle = parse_bytes_argument(args.needle_hex and ("hex:" + args.needle_hex) or args.needle, file_path=args.needle_file, encoding=args.encoding)
    matches = find_pattern_in_iso_entry(iso, entry, needle, max_matches=args.max_matches)
    result = {
        "status": "ok",
        "container_path": entry.path,
        "needle_size": len(needle),
        "match_count": len(matches),
        "matches": matches,
    }
    if args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def cmd_plan_nested_patch(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    old_bytes, new_bytes = _bytes_from_nested_args(args)
    inner_offset = int(args.inner_offset, 0) if args.inner_offset is not None else None
    plan = direct_nested_patch_plan(iso, entry, old_bytes, new_bytes, inner_offset=inner_offset, match_index=args.match_index, max_matches=args.max_matches)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "plan": str(out), "decision": plan["decision"], "match_count": plan["match_count"]}, indent=2))
    return 0


def cmd_patch_copy_nested(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    old_bytes, new_bytes = _bytes_from_nested_args(args)
    inner_offset = int(args.inner_offset, 0) if args.inner_offset is not None else None
    plan = patch_copy_nested_same_size(iso, entry, old_bytes, new_bytes, Path(args.output_iso).resolve(), inner_offset=inner_offset, match_index=args.match_index, max_matches=args.max_matches)
    out = Path(args.report).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output_iso": plan["output_iso"], "report": str(out), "decision": plan["decision"]}, indent=2))
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    paths = write_reports(report, Path(args.out).resolve())
    print(json.dumps({"status": "ok", "files": len(report.files), "focus": len(report.focus_files), "reports": paths, "warnings": report.warnings}, indent=2))
    return 0 if report.selected_descriptor else 2


def cmd_extract(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    out = Path(args.out).resolve()
    if out.is_dir() or str(args.out).endswith(("/", "\\")):
        out = out / entry.path
    extract_file(iso, entry, out)
    print(json.dumps({"status": "ok", "extracted": str(out), "entry": asdict(entry)}, indent=2))
    return 0


def cmd_plan_replace(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    plan = replacement_plan(iso, entry, Path(args.replacement).resolve())
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "plan": str(out), "decision": plan["decision"]}, indent=2))
    return 0


def cmd_replace_copy(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    plan = replace_file_copy_exact(iso, entry, Path(args.replacement).resolve(), Path(args.output_iso).resolve())
    out = Path(args.report).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output_iso": plan["output_iso"], "report": str(out)}, indent=2))
    return 0


def cmd_prepare_exact(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    info = write_padded_replacement(Path(args.replacement).resolve(), entry.size, Path(args.out).resolve(), pad_byte=args.pad_byte)
    plan = replacement_plan(iso, entry, Path(args.replacement).resolve())
    info["plan"] = plan
    print(json.dumps({"status": "ok", "staged_exact_file": info["staged_exact_file"], "bytes_to_pad": plan["bytes_to_pad"]}, indent=2))
    sidecar = Path(args.out).resolve().with_suffix(Path(args.out).resolve().suffix + ".json")
    sidecar.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return 0


def cmd_replace_copy_safe(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    plan = replace_file_copy_safe(iso, entry, Path(args.replacement).resolve(), Path(args.output_iso).resolve(), staging_dir=Path(args.staging_dir).resolve() if args.staging_dir else None)
    out = Path(args.report).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output_iso": plan["output_iso"], "report": str(out), "decision": plan["decision"]}, indent=2))
    return 0


def cmd_export_overlay(args: argparse.Namespace) -> int:
    iso = Path(args.iso).resolve()
    report = build_report(iso, max_entries=args.max_entries)
    entry = find_entry(report, args.path)
    manifest = export_xenia_overlay(entry, Path(args.replacement).resolve(), Path(args.out).resolve(), iso_path=iso)
    print(json.dumps({"status": "ok", "overlay_file": manifest["overlay_file"], "manifest": str(Path(args.out).resolve() / "CODE_RED_XENIA_OVERLAY_MANIFEST.json")}, indent=2))
    return 0


def build_fake_xdvdfs_iso(path: Path) -> None:
    """Create a tiny synthetic image for parser validation only."""
    sectors = 96
    blob = bytearray(sectors * SECTOR_SIZE)
    descriptor_sector = 32
    root_sector = 40
    root_size = SECTOR_SIZE
    desc_off = descriptor_sector * SECTOR_SIZE
    blob[desc_off:desc_off + len(XDVDFS_MAGIC)] = XDVDFS_MAGIC
    blob[desc_off + len(XDVDFS_MAGIC):desc_off + len(XDVDFS_MAGIC) + 4] = root_sector.to_bytes(4, "little")
    blob[desc_off + len(XDVDFS_MAGIC) + 4:desc_off + len(XDVDFS_MAGIC) + 8] = root_size.to_bytes(4, "little")

    def entry(name: str, sector: int, size: int, attrs: int) -> bytes:
        n = name.encode("ascii")
        e = bytearray()
        e += (0).to_bytes(2, "little")
        e += (0).to_bytes(2, "little")
        e += sector.to_bytes(4, "little")
        e += size.to_bytes(4, "little")
        e += bytes([attrs, len(n)])
        e += n
        while len(e) % 4:
            e += b"\x00"
        return bytes(e)

    root = bytearray(SECTOR_SIZE)
    pos = 0
    for e in [entry("content.rpf", 50, 17, 0), entry("layer_0.rpf", 51, 11, 0), entry("content", 60, SECTOR_SIZE, 0x10)]:
        root[pos:pos + len(e)] = e
        pos += len(e)
    blob[root_sector * SECTOR_SIZE:(root_sector + 1) * SECTOR_SIZE] = root
    blob[50 * SECTOR_SIZE:50 * SECTOR_SIZE + 17] = b"RPF7 content test"
    blob[51 * SECTOR_SIZE:51 * SECTOR_SIZE + 11] = b"RPF7 layer0"
    sub = bytearray(SECTOR_SIZE)
    e = entry("default.xex", 61, 8, 0)
    sub[0:len(e)] = e
    blob[60 * SECTOR_SIZE:61 * SECTOR_SIZE] = sub
    blob[61 * SECTOR_SIZE:61 * SECTOR_SIZE + 8] = b"XEX2TEST"
    path.write_bytes(blob)


def cmd_selftest(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    iso = out_dir / "synthetic_xdvdfs.iso"
    build_fake_xdvdfs_iso(iso)
    report = build_report(iso)
    assert report.selected_descriptor is not None, "descriptor not found"
    paths = {row["path"] for row in report.files}
    assert "content.rpf" in paths and "layer_0.rpf" in paths and "content/default.xex" in paths, paths
    extracted = out_dir / "extract" / "layer_0.rpf"
    entry = find_entry(report, "layer_0.rpf")
    extract_file(iso, entry, extracted)
    assert extracted.read_bytes() == b"RPF7 layer0"
    # Smaller replacements are padded back to original size before copy-write.
    small = out_dir / "small_layer_0.rpf"
    small.write_bytes(b"RPF7NEW")
    safe_iso = out_dir / "synthetic_safe_replace.iso"
    safe_plan = replace_file_copy_safe(iso, entry, small, safe_iso, staging_dir=out_dir / "staged")
    assert safe_plan["verification"]["ok"], safe_plan
    roundtrip = out_dir / "extract" / "layer_0_after_safe.rpf"
    extract_file(safe_iso, entry, roundtrip)
    assert roundtrip.read_bytes().startswith(b"RPF7NEW") and len(roundtrip.read_bytes()) == entry.size
    too_big = out_dir / "too_big_layer_0.rpf"
    too_big.write_bytes(b"X" * (entry.size + 1))
    try:
        replace_file_copy_safe(iso, entry, too_big, out_dir / "should_not_write.iso")
        raise AssertionError("oversize replacement was not refused")
    except ValueError:
        pass
    nested_iso = out_dir / "synthetic_nested_patch.iso"
    nested_plan = patch_copy_nested_same_size(iso, entry, b"layer0", b"LAYR00", nested_iso)
    assert nested_plan["verification"]["ok"], nested_plan
    patched_extract = out_dir / "extract" / "layer_0_after_nested.rpf"
    extract_file(nested_iso, entry, patched_extract)
    assert patched_extract.read_bytes() == b"RPF7 LAYR00"
    write_reports(report, out_dir / "reports")
    print(json.dumps({"status": "ok", "synthetic_iso": str(iso), "files": len(report.files), "safe_replace_verified": True, "nested_patch_verified": True}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code RED Xbox ISO / XDVDFS browser, extractor, and corruption-safe RPF replacement planner")
    parser.add_argument("--max-entries", type=int, default=50000, help="Maximum directory entries to index")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Index an Xbox/XDVDFS ISO and write reports")
    p_index.add_argument("iso")
    p_index.add_argument("--out", default="reports/xiso")
    p_index.set_defaults(func=cmd_index)

    p_extract = sub.add_parser("extract", help="Extract one indexed file from an ISO")
    p_extract.add_argument("iso")
    p_extract.add_argument("--path", required=True, help="Game-relative path, e.g. layer_0.rpf")
    p_extract.add_argument("--out", required=True, help="Output file or directory")
    p_extract.set_defaults(func=cmd_extract)

    p_plan = sub.add_parser("plan-replace", help="Create a replacement safety plan")
    p_plan.add_argument("iso")
    p_plan.add_argument("--path", required=True)
    p_plan.add_argument("--replacement", required=True)
    p_plan.add_argument("--out", default="reports/xiso_replace_plan.json")
    p_plan.set_defaults(func=cmd_plan_replace)

    p_copy = sub.add_parser("replace-copy-exact", help="Create a copied ISO with an exact-size file replacement")
    p_copy.add_argument("iso")
    p_copy.add_argument("--path", required=True)
    p_copy.add_argument("--replacement", required=True)
    p_copy.add_argument("--output-iso", required=True)
    p_copy.add_argument("--report", default="reports/xiso_replace_copy_report.json")
    p_copy.set_defaults(func=cmd_replace_copy)

    p_stage = sub.add_parser("prepare-exact", help="Create a padded exact-size replacement file for the target ISO entry")
    p_stage.add_argument("iso")
    p_stage.add_argument("--path", required=True)
    p_stage.add_argument("--replacement", required=True)
    p_stage.add_argument("--out", required=True)
    p_stage.add_argument("--pad-byte", type=lambda x: int(x, 0), default=0, help="Padding byte, default 0")
    p_stage.set_defaults(func=cmd_prepare_exact)

    p_safe = sub.add_parser("replace-copy-safe", help="Create a copied ISO with exact or smaller padded replacement, verified after write")
    p_safe.add_argument("iso")
    p_safe.add_argument("--path", required=True)
    p_safe.add_argument("--replacement", required=True)
    p_safe.add_argument("--output-iso", required=True)
    p_safe.add_argument("--report", default="reports/xiso_replace_safe_report.json")
    p_safe.add_argument("--staging-dir", default=None)
    p_safe.set_defaults(func=cmd_replace_copy_safe)

    p_overlay = sub.add_parser("export-overlay", help="Export a replacement file to a Xenia extracted-folder overlay when ISO write-back is unsafe")
    p_overlay.add_argument("iso")
    p_overlay.add_argument("--path", required=True)
    p_overlay.add_argument("--replacement", required=True)
    p_overlay.add_argument("--out", default="reports/xiso_overlay")
    p_overlay.set_defaults(func=cmd_export_overlay)

    def add_nested_byte_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--old", help="Old text bytes to verify/replace")
        p.add_argument("--old-hex", help="Old bytes as hex, spaces allowed")
        p.add_argument("--old-file", help="File containing exact old bytes")
        p.add_argument("--new", help="New text bytes; must be same length as old")
        p.add_argument("--new-hex", help="New bytes as hex, spaces allowed; must be same length as old")
        p.add_argument("--new-file", help="File containing exact new bytes; must be same length as old")
        p.add_argument("--encoding", default="utf-8", help="Encoding for --old/--new text, default utf-8")
        p.add_argument("--inner-offset", default=None, help="Optional offset inside selected ISO entry/RPF, e.g. 0x1234; skips search")
        p.add_argument("--match-index", type=int, default=0, help="Which search match to patch when old bytes appear more than once")
        p.add_argument("--max-matches", type=int, default=50)

    p_find_nested = sub.add_parser("nested-find", help="Find text/bytes directly inside an ISO-contained file such as layer_0.rpf without extracting it")
    p_find_nested.add_argument("iso")
    p_find_nested.add_argument("--path", required=True, help="Container file path inside ISO, e.g. layer_0.rpf")
    p_find_nested.add_argument("--needle", help="Needle text bytes")
    p_find_nested.add_argument("--needle-hex", help="Needle bytes as hex, spaces allowed")
    p_find_nested.add_argument("--needle-file", help="File containing exact needle bytes")
    p_find_nested.add_argument("--encoding", default="utf-8")
    p_find_nested.add_argument("--max-matches", type=int, default=50)
    p_find_nested.add_argument("--out", default=None)
    p_find_nested.set_defaults(func=cmd_find_nested)

    p_nested_plan = sub.add_parser("nested-plan-patch", help="Plan a same-size direct byte patch inside an ISO-contained RPF/file")
    p_nested_plan.add_argument("iso")
    p_nested_plan.add_argument("--path", required=True, help="Container file path inside ISO, e.g. layer_0.rpf")
    add_nested_byte_args(p_nested_plan)
    p_nested_plan.add_argument("--out", default="reports/xiso_nested_patch_plan.json")
    p_nested_plan.set_defaults(func=cmd_plan_nested_patch)

    p_nested_copy = sub.add_parser("nested-patch-copy", help="Create a copied ISO with a same-size byte/string patch written directly inside an ISO-contained RPF/file")
    p_nested_copy.add_argument("iso")
    p_nested_copy.add_argument("--path", required=True, help="Container file path inside ISO, e.g. layer_0.rpf")
    add_nested_byte_args(p_nested_copy)
    p_nested_copy.add_argument("--output-iso", required=True)
    p_nested_copy.add_argument("--report", default="reports/xiso_nested_patch_copy_report.json")
    p_nested_copy.set_defaults(func=cmd_patch_copy_nested)

    p_self = sub.add_parser("selftest", help="Run parser self-test on a synthetic tiny image")
    p_self.add_argument("--out", default="reports/xiso_selftest")
    p_self.set_defaults(func=cmd_selftest)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
