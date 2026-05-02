#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import subprocess
import shutil
from pathlib import Path

VBASE = 0x50000000
VFT_GRINGO = 0x01979634
VFT_USE_CONTEXT = 0xE03269C1
VFT_ITEM_ATTRIBUTES = 0xB16C14A8


def u8(data: bytes, off: int) -> int:
    return data[off] if 0 <= off < len(data) else 0


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0] if off + 2 <= len(data) else 0


def i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0] if off + 2 <= len(data) else 0


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0] if off + 4 <= len(data) else 0


def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0] if off + 4 <= len(data) else 0


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0] if off + 4 <= len(data) else 0.0


def vec4(data: bytes, off: int) -> list[float]:
    if off + 16 > len(data):
        return []
    return [round(x, 6) for x in struct.unpack_from("<4f", data, off)]


def target(ptr: int, size: int) -> int | None:
    if VBASE <= ptr < VBASE + size:
        return ptr - VBASE
    return None


def read_cstr(data: bytes, off: int | None, max_len: int = 500) -> str:
    if off is None or off < 0 or off >= len(data):
        return ""
    end = off
    while end < len(data) and end - off < max_len and data[end] != 0:
        end += 1
    return data[off:end].decode("latin-1", "replace")


def ptr(data: bytes, off: int) -> int | None:
    return target(u32(data, off), len(data))


def arr_desc(data: bytes, off: int) -> dict:
    p = u32(data, off)
    return {"ptr": p, "offset": target(p, len(data)), "count": u16(data, off + 4), "capacity": u16(data, off + 6)}


def ptr_array_items(data: bytes, arr_off: int, limit: int = 100000) -> list[int | None]:
    desc = arr_desc(data, arr_off)
    out: list[int | None] = []
    if desc["offset"] is None:
        return out
    for i in range(min(desc["count"], limit)):
        out.append(target(u32(data, desc["offset"] + i * 4), len(data)))
    return out


def decode_rsc_like_wgd(raw: bytes) -> bytes:
    """Decode the common RDR1 RSC zstd layer when present.

    Some research exports may already be decoded. In that case, return raw.
    """
    magic = raw.find(bytes.fromhex("28b52ffd"))
    if magic < 0:
        return raw
    body = raw[magic:]
    try:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdDecompressor().decompress(body)
    except Exception:
        pass
    if not shutil.which("zstd"):
        return raw
    result = subprocess.run(
        ["zstd", "-d", "-q", "--single-thread", "--stdout"],
        input=body,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout


def parse_component(data: bytes, off: int) -> dict:
    t = u32(data, off)
    row: dict = {
        "offset": off,
        "offset_hex": f"0x{off:08X}",
        "type_hex": f"0x{t:08X}",
        "query_name": read_cstr(data, ptr(data, off + 4)),
        "hash_code": f"0x{u32(data, off + 8):08X}",
        "parent_offset": ptr(data, off + 12),
        "parent_ptr": f"0x{u32(data, off + 12):08X}" if u32(data, off + 12) else "",
    }

    if t == VFT_GRINGO:
        child_desc = arr_desc(data, off + 0x28)
        inst_desc = arr_desc(data, off + 0x30)
        row.update(
            {
                "component_type": "ItemGringo",
                "instance_index": i16(data, off + 0x10),
                "script_name": read_cstr(data, ptr(data, off + 0x20)),
                "gringo_name": read_cstr(data, ptr(data, off + 0x24)),
                "child_count": child_desc["count"],
                "child_array_offset": child_desc["offset"],
                "instanced_item_count": inst_desc["count"],
                "instanced_items_offset": inst_desc["offset"],
                "hashed_name": f"0x{u32(data, off + 0x38):08X}",
                "message_mask": f"0x{u32(data, off + 0x3C):08X}",
                "activation_radius": f32(data, off + 0x40),
                "instance_slot_count": i32(data, off + 0x44),
                "critical": u8(data, off + 0x48),
                "large_script": u8(data, off + 0x49),
                "maintain_state": u8(data, off + 0x4A),
            }
        )
    elif t == VFT_USE_CONTEXT:
        attr_desc = arr_desc(data, off + 0x10)
        child_desc = arr_desc(data, off + 0x54)
        row.update(
            {
                "component_type": "UseContext",
                "attr_count": attr_desc["count"],
                "attr_array_offset": attr_desc["offset"],
                "instance_index": i16(data, off + 0x18),
                "facing": f32(data, off + 0x1C),
                "local_position": vec4(data, off + 0x20),
                "radius": f32(data, off + 0x30),
                "parent_transform_remap": i32(data, off + 0x34),
                "parent_bone": read_cstr(data, ptr(data, off + 0x38)),
                "race_type": read_cstr(data, ptr(data, off + 0x40)),
                "use_priority": i32(data, off + 0x48),
                "unusable_weather": read_cstr(data, ptr(data, off + 0x4C)),
                "child_count": child_desc["count"],
                "child_array_offset": child_desc["offset"],
                "use_button": i32(data, off + 0x60),
                "user_tag": read_cstr(data, ptr(data, off + 0x64)),
                "player_usable": u8(data, off + 0x6E),
                "position_parent_actor_relative": u8(data, off + 0x6F),
                "actor_becomes_obstacle": u8(data, off + 0x70),
                "is_melee_attack": u8(data, off + 0x71),
                "gringo_handles_movement": u8(data, off + 0x72),
                "is_combat_friendly": u8(data, off + 0x73),
                "requires_physics_check": u8(data, off + 0x75),
                "requires_nav_probe_check": u8(data, off + 0x78),
                "start_unavailable": u8(data, off + 0x79),
                "allow_ai_shoot": u8(data, off + 0x7A),
                "auto_play_for_player": u8(data, off + 0x7B),
                "allow_navigate_to": u8(data, off + 0x7E),
            }
        )
    elif t == VFT_ITEM_ATTRIBUTES:
        attr_desc = arr_desc(data, off + 0x10)
        ptrs = []
        if attr_desc["offset"] is not None:
            for i in range(min(attr_desc["count"], 200)):
                val = u32(data, attr_desc["offset"] + i * 4)
                ptrs.append(f"0x{val:08X}")
        row.update(
            {
                "component_type": "ItemAttributes",
                "attr_count": attr_desc["count"],
                "attr_array_offset": attr_desc["offset"],
                "attribute_ptrs": " ".join(ptrs),
            }
        )
    else:
        row["component_type"] = f"Unknown_0x{t:08X}"

    return row


def scan_wgd(path: Path) -> tuple[bytes, list[dict]]:
    data = decode_rsc_like_wgd(path.read_bytes())
    rows: list[dict] = []
    for vft in (VFT_GRINGO, VFT_USE_CONTEXT, VFT_ITEM_ATTRIBUTES):
        sig = struct.pack("<I", vft)
        start = 0
        while True:
            off = data.find(sig, start)
            if off < 0:
                break
            if off % 4 == 0:
                row = parse_component(data, off)
                row["source_file"] = path.name
                rows.append(row)
            start = off + 4
    rows.sort(key=lambda r: r["offset"])
    return data, rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        if fields:
            writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code RED WGD gringo component exporter")
    parser.add_argument("inputs", nargs="+", help="Decoded .wgd files or raw RSC/zstd WGD slots")
    parser.add_argument("--outdir", default="exports/gringo_wgd_export")
    parser.add_argument("--keyword", default="vehicle|car|wagon|coach|cart|train|fbi|gatling|turret")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(args.keyword, re.I) if args.keyword else None

    all_rows: list[dict] = []
    vehicle_rows: list[dict] = []
    master = []
    for item in args.inputs:
        path = Path(item)
        if not path.exists():
            continue
        decoded, rows = scan_wgd(path)
        all_rows.extend(rows)
        local_hits = []
        for row in rows:
            text = " ".join(str(row.get(k, "")) for k in ("script_name", "gringo_name", "query_name", "user_tag", "race_type"))
            if pattern and pattern.search(text):
                local_hits.append(row)
                vehicle_rows.append(row)
        safe = path.name.replace("/", "_").replace("\\", "_")
        write_csv(outdir / f"{safe}.components.csv", rows)
        write_csv(outdir / f"{safe}.keyword_hits.csv", local_hits)
        (outdir / f"{safe}.components.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        master.append({"file": str(path), "decoded_size": len(decoded), "component_count": len(rows), "keyword_hit_count": len(local_hits)})
        print(f"Exported {len(rows)} components from {path.name}; keyword hits {len(local_hits)}")

    write_csv(outdir / "all_components.csv", all_rows)
    write_csv(outdir / "keyword_hits.csv", vehicle_rows)
    (outdir / "gringo_wgd_export_master.json").write_text(json.dumps({"inputs": master}, indent=2), encoding="utf-8")
    print("Wrote", outdir)


if __name__ == "__main__":
    main()
