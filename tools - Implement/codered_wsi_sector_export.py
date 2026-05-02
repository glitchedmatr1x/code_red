#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import struct
from dataclasses import asdict
from pathlib import Path

from codered_wsi_explorer import (
    RPF6,
    SAG_SECTORINFO_VFT,
    VBASE,
    hash_map,
    load_names,
    rsc_decode,
    sha1,
)


def u8(data: bytes, off: int) -> int:
    return data[off] if 0 <= off < len(data) else 0


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0] if off + 2 <= len(data) else 0


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0] if off + 4 <= len(data) else 0


def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0] if off + 4 <= len(data) else 0


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0] if off + 4 <= len(data) else 0.0


def vec4(data: bytes, off: int) -> list[float]:
    if off + 16 > len(data):
        return [0.0, 0.0, 0.0, 0.0]
    return [round(x, 6) for x in struct.unpack_from("<4f", data, off)]


def ptr_target(ptr: int, size: int) -> int | None:
    if VBASE <= ptr < VBASE + size:
        return ptr - VBASE
    return None


def read_cstr(data: bytes, off: int | None, max_len: int = 256) -> str:
    if off is None or off < 0 or off >= len(data):
        return ""
    end = off
    while end < len(data) and end - off < max_len and data[end] != 0:
        end += 1
    return data[off:end].decode("latin-1", "replace")


def parse_sector(payload: bytes, off: int, names: dict[int, str]) -> dict:
    """Read the stable top-level sagSectorInfo/Rsc6SectorInfo fields.

    Field offsets follow the CodeX.Games.RDR1 Rsc6SectorInfo layout. This pass
    intentionally exports conservative fixed fields and pointer lanes first; it
    does not yet walk every child array or drawable/prop structure.
    """

    name_ptr = u32(payload, off + 0x08)
    scope_ptr = u32(payload, off + 0x1B0)
    prop_names_ptr = u32(payload, off + 0x19C)
    scoped_hash = u32(payload, off + 0x1C)
    name_hash = u32(payload, off + 0x178)
    flags = u32(payload, off + 0x1C8)
    named_node_map = 0
    if off + 0x1E0 <= len(payload):
        named_node_map = struct.unpack_from("<Q", payload, off + 0x1D8)[0]

    return {
        "offset": off,
        "vft": f"0x{u32(payload, off):08X}",
        "name_ptr": f"0x{name_ptr:08X}" if name_ptr else "",
        "name": read_cstr(payload, ptr_target(name_ptr, len(payload))),
        "scope_ptr": f"0x{scope_ptr:08X}" if scope_ptr else "",
        "scope": read_cstr(payload, ptr_target(scope_ptr, len(payload))),
        "scoped_name_hash": f"0x{scoped_hash:08X}" if scoped_hash else "",
        "scoped_name_resolved": names.get(scoped_hash, ""),
        "sector_name_hash": f"0x{name_hash:08X}" if name_hash else "",
        "sector_name_resolved": names.get(name_hash, ""),
        "lod_fade": round(f32(payload, off + 0x0C), 6),
        "added": u8(payload, off + 0x18),
        "props_group": u8(payload, off + 0x19),
        "missing_med_lod": u8(payload, off + 0x1A),
        "parent_level_index": i32(payload, off + 0x80),
        "curve_extra_data": f"0x{u32(payload, off + 0x8C):08X}",
        "min_and_bounding_radius": vec4(payload, off + 0x90),
        "max_and_inscribed_radius": vec4(payload, off + 0xA0),
        "bound_min": vec4(payload, off + 0xB0),
        "bound_max": vec4(payload, off + 0xC0),
        "placed_lights_group_ptr": f"0x{u32(payload, off + 0xD0):08X}" if u32(payload, off + 0xD0) else "",
        "props_arr_ptr": f"0x{u32(payload, off + 0xD4):08X}" if u32(payload, off + 0xD4) else "",
        "children_arr_ptr": f"0x{u32(payload, off + 0xE8):08X}" if u32(payload, off + 0xE8) else "",
        "child_group_ptr": f"0x{u32(payload, off + 0xF0):08X}" if u32(payload, off + 0xF0) else "",
        "child_ptrs_ptr": f"0x{u32(payload, off + 0xF4):08X}" if u32(payload, off + 0xF4) else "",
        "drawable_instances_ptr": f"0x{u32(payload, off + 0xFC):08X}" if u32(payload, off + 0xFC) else "",
        "drawable_instances2_ptr": f"0x{u32(payload, off + 0x104):08X}" if u32(payload, off + 0x104) else "",
        "low_lod_fade": round(f32(payload, off + 0x174), 6),
        "resident_status": u32(payload, off + 0x188),
        "prop_names_ptr": f"0x{prop_names_ptr:08X}" if prop_names_ptr else "",
        "prop_names_preview": read_cstr(payload, ptr_target(prop_names_ptr, len(payload))),
        "any_high_instance_loaded": u8(payload, off + 0x1A8),
        "resident_vlow_count": u8(payload, off + 0x1A9),
        "has_vlow_lod_resource": u8(payload, off + 0x1AA),
        "vlow_superseded": u8(payload, off + 0x1AB),
        "district": u8(payload, off + 0x1BD),
        "is_terrain": u8(payload, off + 0x1BE),
        "ref_count": u8(payload, off + 0x1C5),
        "flags": f"0x{flags:08X}",
        "disabled_flag_guess": bool(flags & 0x01000000),
        "bound_instances_ptr": f"0x{u32(payload, off + 0x1D0):08X}" if u32(payload, off + 0x1D0) else "",
        "unknown_1d4h": f"0x{u32(payload, off + 0x1D4):08X}",
        "named_node_map": f"0x{named_node_map:016X}",
    }


def sector_offsets(payload: bytes) -> list[int]:
    sig = struct.pack("<I", SAG_SECTORINFO_VFT)
    out: list[int] = []
    start = 0
    while True:
        off = payload.find(sig, start)
        if off < 0:
            break
        if off % 4 == 0 and off + 480 <= len(payload):
            out.append(off)
        start = off + 4
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        if fields:
            writer.writeheader()
        writer.writerows(rows)


def select_entries(rpf: RPF6, path: str | None):
    if path:
        entry = rpf.find(path)
        if entry is None:
            raise KeyError(path)
        return [entry]

    # Prefer named .wsi entries, but fall back to resource type 134 when debug
    # names are unavailable.
    entries = rpf.files(".wsi")
    if entries:
        return entries
    return [e for e in rpf.entries if e.type == "file" and e.resource and e.resource_type == 134]


def export(args: argparse.Namespace) -> None:
    rpf = RPF6(args.archive, not args.no_debug)
    names = hash_map(rpf, load_names(args.names))
    entries = select_entries(rpf, args.path)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    master = {"archive": rpf.summary(), "wsi": []}
    for entry in entries:
        header, payload = rsc_decode(rpf.slot(entry))
        rows = [parse_sector(payload, off, names) for off in sector_offsets(payload)]
        for row in rows:
            row["wsi_path"] = entry.path
            row["decoded_sha1"] = sha1(payload)

        safe = entry.path.replace("/", "__").replace("\\", "__")
        csv_path = outdir / f"{safe}.sectors.csv"
        json_path = outdir / f"{safe}.sectors.json"
        write_csv(csv_path, rows)
        json_path.write_text(
            json.dumps({"entry": asdict(entry), "sector_count": len(rows), "sectors": rows}, indent=2),
            encoding="utf-8",
        )
        master["wsi"].append(
            {
                "path": entry.path,
                "resource_type": entry.resource_type,
                "decoded_size": len(payload),
                "decoded_sha1": sha1(payload),
                "sector_count": len(rows),
                "csv": csv_path.name,
                "json": json_path.name,
            }
        )
        print(f"Exported {len(rows)} sectors from {entry.path}")

    (outdir / "wsi_sector_export_master.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
    print("Wrote", outdir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code RED semantic WSI sector exporter")
    parser.add_argument("archive", help="RPF6 archive containing WSI resources")
    parser.add_argument("--path", help="Optional exact .wsi path inside the RPF")
    parser.add_argument("--names", nargs="*", default=[], help="Optional text/csv/hash files or folders of candidate names")
    parser.add_argument("--outdir", default="exports/wsi_sector_export")
    parser.add_argument("--no-debug", action="store_true", help="Skip debug-name recovery")
    args = parser.parse_args()
    export(args)


if __name__ == "__main__":
    main()
