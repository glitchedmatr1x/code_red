#!/usr/bin/env python3
"""Code RED WSI Host Placement Resolver.

Read-only resolver for the post-correlator Blackwater vehicle/gringo lane.

The WSI <-> WGD correlator proved that Blackwater WSI does not expose a clean
Vehicle_Generator reference. It exposes prop/drawable host strings and gringo
annotation strings. This tool resolves those host strings back into likely WSI
placement records before any copied-RPF patch is attempted.

Outputs are proof tables only. This script does not patch WSI/WGD/WVD/WBD.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

VBASE = 0x50000000
SAG_SECTORINFO_VFT = 0x01909C38
ASCII_RE = re.compile(rb"[\x20-\x7E]{4,}")

ARRAY_FIELDS = {
    "props": 0xD4,
    "doors_attributes": 0xDC,
    "children": 0xE8,
    "child_ptrs": 0xF4,
    "drawable_instances": 0xFC,
    "drawable_instances2": 0x104,
    "occluders": 0x17C,
    "locators": 0x1A0,
}

# Field/stride evidence from Blackwater WSI Pass 3:
# - props records are compact 0x30-byte records with name ptr at +0 and position at +0x10.
# - drawable_instances use the known 0xE0/224-byte stride, name ptr at +0xB8,
#   transform matrix at +0x40, position row at +0x70, bbox at +0x80/+0x90.
KNOWN_ARRAY_LAYOUTS = {
    "props": {"stride": 0x30, "name_rel": 0x00, "kind": "prop_record_0x30"},
    "drawable_instances": {"stride": 0xE0, "name_rel": 0xB8, "kind": "drawable_instance_0xE0"},
    "drawable_instances2": {"stride": 0xE0, "name_rel": 0xB8, "kind": "drawable_instance_0xE0"},
}

DEFAULT_PRIORITY_HOSTS = (
    "p_gen_cart03x",
    "p_gen_cart01x",
    "i_gen_wagonParked01x",
    "i_gen_wagonBroken02x",
    "i_gen_wagonParts01x",
    "i_gen_wagonParts02x",
    "i_gen_wagonParts03x",
    "p_gen_lumberCart01x",
    "p_gen_lumberCart03x",
    "i_gen_hitchingPost02x",
    "i_gen_hitchingPost03x",
)


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def rdr_hash(name: str) -> int:
    h = 0
    for ch in name.lower():
        a = (h + ord(ch)) & 0xFFFFFFFF
        b = (a + ((a << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h = (b ^ (b >> 6)) & 0xFFFFFFFF
    a = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    b = (a ^ (a >> 11)) & 0xFFFFFFFF
    return (b + ((b << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


def u8(data: bytes, off: int) -> int:
    return data[off] if 0 <= off < len(data) else 0


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0] if 0 <= off and off + 2 <= len(data) else 0


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0] if 0 <= off and off + 4 <= len(data) else 0


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0] if 0 <= off and off + 4 <= len(data) else 0.0


def vec3(data: bytes, off: int) -> list[float]:
    if off < 0 or off + 12 > len(data):
        return []
    return [round(v, 6) for v in struct.unpack_from("<3f", data, off)]


def vec4(data: bytes, off: int) -> list[float]:
    if off < 0 or off + 16 > len(data):
        return []
    return [round(v, 6) if math.isfinite(v) else "nan" for v in struct.unpack_from("<4f", data, off)]


def ptr_target(value: int, size: int) -> int | None:
    if VBASE <= value < VBASE + size:
        return value - VBASE
    return None


def ptr_hex(value: int) -> str:
    return f"0x{value:08X}" if value else ""


def read_cstr(data: bytes, off: int | None, max_len: int = 600) -> str:
    if off is None or off < 0 or off >= len(data):
        return ""
    end = off
    while end < len(data) and end - off < max_len and data[end] != 0:
        end += 1
    return data[off:end].decode("latin-1", "replace")


def ascii_run_at(data: bytes, off: int) -> tuple[int, int, str]:
    if off < 0 or off >= len(data):
        return off, off, ""
    start = off
    while start > 0 and 0x20 <= data[start - 1] <= 0x7E:
        start -= 1
    end = off
    while end < len(data) and 0x20 <= data[end] <= 0x7E:
        end += 1
    return start, end, data[start:end].decode("latin-1", "replace")


def arr_desc(data: bytes, off: int) -> dict[str, Any]:
    ptr = u32(data, off)
    return {
        "ptr": ptr,
        "ptr_hex": ptr_hex(ptr),
        "offset": ptr_target(ptr, len(data)),
        "count": u16(data, off + 4),
        "capacity": u16(data, off + 6),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def sector_offsets(payload: bytes) -> list[int]:
    sig = struct.pack("<I", SAG_SECTORINFO_VFT)
    out: list[int] = []
    start = 0
    while True:
        off = payload.find(sig, start)
        if off < 0:
            break
        if off % 4 == 0 and off + 0x1D4 <= len(payload):
            out.append(off)
        start = off + 4
    return out


def parse_sector(payload: bytes, off: int) -> dict[str, Any]:
    name_ptr = u32(payload, off + 8)
    scope_ptr = u32(payload, off + 0x1B0)
    row: dict[str, Any] = {
        "sector_offset": off,
        "sector_offset_hex": f"0x{off:08X}",
        "sector_name": read_cstr(payload, ptr_target(name_ptr, len(payload))),
        "sector_scope": read_cstr(payload, ptr_target(scope_ptr, len(payload))),
        "bound_min": vec4(payload, off + 0xB0),
        "bound_max": vec4(payload, off + 0xC0),
        "flags": f"0x{u32(payload, off + 0x1C8):08X}",
        "resident_status": u32(payload, off + 0x188),
        "district": u8(payload, off + 0x1BD),
        "ref_count": u8(payload, off + 0x1C5),
    }
    for name, rel in ARRAY_FIELDS.items():
        desc = arr_desc(payload, off + rel)
        row[f"{name}_offset"] = desc["offset"]
        row[f"{name}_count"] = desc["count"]
        row[f"{name}_ptr_hex"] = desc["ptr_hex"]
    return row


def build_array_spans(payload: bytes, sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for sector in sectors:
        for name in ARRAY_FIELDS:
            off = sector.get(f"{name}_offset")
            count = sector.get(f"{name}_count")
            if off in (None, "") or count in (None, ""):
                continue
            try:
                arr_off = int(off)
                arr_count = int(count)
            except Exception:
                continue
            if arr_off < 0 or arr_count <= 0 or arr_off >= len(payload):
                continue
            layout = KNOWN_ARRAY_LAYOUTS.get(name)
            if layout:
                byte_count = arr_count * int(layout["stride"])
            else:
                byte_count = arr_count * 4
            spans.append({
                "array_name": name,
                "array_offset": arr_off,
                "array_offset_hex": f"0x{arr_off:08X}",
                "array_count": arr_count,
                "array_byte_count_guess": byte_count,
                "array_end_guess": arr_off + byte_count,
                "sector_offset": sector.get("sector_offset"),
                "sector_offset_hex": sector.get("sector_offset_hex", ""),
                "sector_name": sector.get("sector_name", ""),
                "sector_scope": sector.get("sector_scope", ""),
                "sector_bound_min": json.dumps(sector.get("bound_min", [])),
                "sector_bound_max": json.dumps(sector.get("bound_max", [])),
                "sector_district": sector.get("district", ""),
            })
    return spans



def build_ascii_runs(payload: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = len(payload)
    i = 0
    while i < n:
        if 0x20 <= payload[i] <= 0x7E:
            start = i
            i += 1
            while i < n and 0x20 <= payload[i] <= 0x7E:
                i += 1
            if i - start >= 4:
                text = payload[start:i].decode("latin-1", "replace")
                rows.append({"start": start, "end": i, "text": text})
        else:
            i += 1
    return rows


def string_info_for_host(ascii_runs: list[dict[str, Any]], host: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not host:
        return rows
    seen: set[int] = set()
    for run in ascii_runs:
        text = str(run.get("text", ""))
        start = int(run.get("start", 0))
        pos = text.find(host)
        while pos >= 0:
            off = start + pos
            if off not in seen:
                seen.add(off)
                rows.append({
                    "string_offset": off,
                    "string_offset_hex": f"0x{off:08X}",
                    "ascii_run_start_hex": f"0x{start:08X}",
                    "ascii_run_end_hex": f"0x{int(run.get('end', start)):08X}",
                    "full_string_value": text,
                })
            pos = text.find(host, pos + 1)
    return rows


def load_wsi_payloads(args: argparse.Namespace) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in args.wsi_decoded or []:
        path = Path(item)
        if path.exists():
            payloads.append({"source": str(path), "payload": path.read_bytes(), "entry": {}, "source_kind": "decoded_wsi"})
    if args.wsi_archive:
        try:
            from codered_wsi_explorer import RPF6, rsc_decode  # type: ignore
        except Exception as exc:
            raise SystemExit(f"--wsi-archive requires codered_wsi_explorer.py beside this tool: {exc}")
        rpf = RPF6(args.wsi_archive, not args.no_debug)
        entries = [rpf.find(args.wsi_path)] if args.wsi_path else rpf.files(".wsi")
        for entry in entries:
            if entry is None:
                raise KeyError(args.wsi_path)
            _header, payload = rsc_decode(rpf.slot(entry))
            payloads.append({"source": entry.path, "payload": payload, "entry": asdict(entry), "source_kind": "rpf_wsi"})
    if not payloads:
        raise SystemExit("No WSI input. Use --wsi-decoded or --wsi-archive.")
    return payloads


def load_hosts(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_host(host: str, source: str, sample: str = "", score: str = "") -> None:
        host = (host or "").strip()
        if not host or host in seen:
            return
        seen.add(host)
        rows.append({
            "host_name": host,
            "host_hash_guess": f"0x{rdr_hash(host):08X}",
            "sample_wsi_value": sample or host,
            "candidate_score_from_correlator": score,
            "host_source": source,
        })

    for path_text in args.candidate_hosts or []:
        path = Path(path_text)
        if not path.exists():
            continue
        for row in read_csv(path):
            add_host(str(row.get("host_name", "")), str(path), str(row.get("sample_wsi_value", "")), str(row.get("candidate_score_lower_is_safer", "")))
    for host in args.host or []:
        add_host(host, "--host")
    if args.default_priority_hosts:
        for host in DEFAULT_PRIORITY_HOSTS:
            add_host(host, "default_priority_hosts")
    if not rows:
        raise SystemExit("No hosts loaded. Use --candidate-hosts, --host, or --default-priority-hosts.")
    return rows


def find_all(data: bytes, needle: bytes) -> list[int]:
    if not needle:
        return []
    out: list[int] = []
    start = 0
    while True:
        off = data.find(needle, start)
        if off < 0:
            return out
        out.append(off)
        start = off + 1


def build_pointer_index(payload: bytes) -> dict[int, list[int]]:
    """Map decoded string/data offsets to WSI virtual-pointer reference offsets.

    This replaces repeated whole-payload scans and keeps the resolver fast on large WSI files.
    """
    out: dict[int, list[int]] = {}
    size = len(payload)
    for off in range(0, max(0, size - 4), 4):
        value = u32(payload, off)
        target = ptr_target(value, size)
        if target is not None:
            out.setdefault(target, []).append(off)
    return out


def build_hash_index(payload: bytes, wanted_hashes: set[int], max_per_hash: int = 1000) -> dict[int, list[int]]:
    wanted = {h for h in wanted_hashes if h not in (0, 0xFFFFFFFF)}
    out: dict[int, list[int]] = {h: [] for h in wanted}
    if not wanted:
        return out
    for off in range(0, max(0, len(payload) - 4), 4):
        value = u32(payload, off)
        bucket = out.get(value)
        if bucket is not None and len(bucket) < max_per_hash:
            bucket.append(off)
    return out


def find_pointer_refs_from_index(pointer_index: dict[int, list[int]], string_offsets: Iterable[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for str_off in string_offsets:
        ptr = VBASE + int(str_off)
        for ref in pointer_index.get(int(str_off), []):
            key = (int(str_off), int(ref))
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "string_offset": int(str_off),
                "string_offset_hex": f"0x{int(str_off):08X}",
                "string_ptr_hex": f"0x{ptr:08X}",
                "reference_offset": int(ref),
                "reference_offset_hex": f"0x{int(ref):08X}",
            })
    return rows


def find_hash_refs_from_index(hash_index: dict[int, list[int]], hashes: Iterable[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in hashes:
        if value in (0, 0xFFFFFFFF):
            continue
        for ref in hash_index.get(int(value), []):
            rows.append({
                "hash_value": f"0x{int(value):08X}",
                "hash_reference_offset": int(ref),
                "hash_reference_offset_hex": f"0x{int(ref):08X}",
            })
    return rows


def plausible_position(pos: list[float]) -> bool:
    if len(pos) < 3:
        return False
    try:
        vals = [float(v) for v in pos[:3]]
    except Exception:
        return False
    return all(math.isfinite(v) and -100000.0 <= v <= 100000.0 for v in vals) and max(abs(v) for v in vals) >= 1.0


def parse_prop_record(payload: bytes, base: int) -> dict[str, Any]:
    name_ptr = u32(payload, base)
    name_off = ptr_target(name_ptr, len(payload))
    pos = vec3(payload, base + 0x10)
    return {
        "record_kind": "prop_record_0x30",
        "record_offset": base,
        "record_offset_hex": f"0x{base:08X}",
        "record_stride_guess": 0x30,
        "name_ptr_rel_guess": 0x00,
        "record_name": read_cstr(payload, name_off),
        "record_name_ptr_hex": ptr_hex(name_ptr),
        "position_guess": json.dumps(pos),
        "position_x_guess": pos[0] if len(pos) > 0 else "",
        "position_y_guess": pos[1] if len(pos) > 1 else "",
        "position_z_guess": pos[2] if len(pos) > 2 else "",
        "rotation_or_state_guess": f32(payload, base + 0x1C),
        "unk04_hex": f"0x{u32(payload, base + 0x04):08X}",
        "unk08_hex": f"0x{u32(payload, base + 0x08):08X}",
        "unk0c_hex": f"0x{u32(payload, base + 0x0C):08X}",
        "raw_30_hex": payload[base:base + 0x30].hex(),
        "transform_confidence": "medium" if plausible_position(pos) else "low",
    }


def parse_drawable_record(payload: bytes, base: int) -> dict[str, Any]:
    name_ptr = u32(payload, base + 0xB8)
    name_off = ptr_target(name_ptr, len(payload))
    pos = vec3(payload, base + 0x70)
    return {
        "record_kind": "drawable_instance_0xE0",
        "record_offset": base,
        "record_offset_hex": f"0x{base:08X}",
        "record_stride_guess": 0xE0,
        "name_ptr_rel_guess": 0xB8,
        "record_vft_hex": f"0x{u32(payload, base):08X}",
        "record_name": read_cstr(payload, name_off),
        "record_name_ptr_hex": ptr_hex(name_ptr),
        "matrix_row0_guess": json.dumps(vec4(payload, base + 0x40)),
        "matrix_row1_guess": json.dumps(vec4(payload, base + 0x50)),
        "matrix_row2_guess": json.dumps(vec4(payload, base + 0x60)),
        "matrix_row3_position_guess": json.dumps(vec4(payload, base + 0x70)),
        "position_guess": json.dumps(pos),
        "position_x_guess": pos[0] if len(pos) > 0 else "",
        "position_y_guess": pos[1] if len(pos) > 1 else "",
        "position_z_guess": pos[2] if len(pos) > 2 else "",
        "bbox_min_guess": json.dumps(vec4(payload, base + 0x80)),
        "bbox_max_guess": json.dumps(vec4(payload, base + 0x90)),
        "instance_hash_guess_hex": f"0x{u32(payload, base + 0xA0):08X}",
        "drawable_flags_guess_hex": f"0x{u32(payload, base + 0xB0):08X}",
        "raw_name_lane_hex": payload[base + 0xB0:base + 0xC0].hex(),
        "transform_confidence": "high" if plausible_position(pos) else "low",
    }


def resolve_reference_to_array(payload: bytes, ref_off: int, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for span in spans:
        name = str(span.get("array_name", ""))
        layout = KNOWN_ARRAY_LAYOUTS.get(name)
        arr_off = int(span.get("array_offset", -1))
        count = int(span.get("array_count", 0))
        if not layout or arr_off < 0 or count <= 0:
            continue
        stride = int(layout["stride"])
        name_rel = int(layout["name_rel"])
        arr_end = arr_off + count * stride
        if not (arr_off <= ref_off < arr_end):
            continue
        rel = ref_off - arr_off
        idx = rel // stride
        rel_in_record = rel % stride
        if rel_in_record != name_rel:
            # Keep near misses out of the main output; they are usually not the host name lane.
            continue
        base = arr_off + idx * stride
        parsed = parse_prop_record(payload, base) if name == "props" else parse_drawable_record(payload, base)
        parsed.update({
            "array_match_confidence": "high",
            "array_name": name,
            "array_offset_hex": span.get("array_offset_hex", ""),
            "array_count": count,
            "array_index": idx,
            "reference_rel_in_record": rel_in_record,
            "sector_offset_hex": span.get("sector_offset_hex", ""),
            "sector_name": span.get("sector_name", ""),
            "sector_scope": span.get("sector_scope", ""),
            "sector_bound_min": span.get("sector_bound_min", ""),
            "sector_bound_max": span.get("sector_bound_max", ""),
            "sector_district": span.get("sector_district", ""),
        })
        matches.append(parsed)
    return matches


def host_category(host: str, sample: str = "") -> str:
    low = f"{host} {sample}".lower()
    if any(t in low for t in ("wagonbroken", "wagonparked", "wagonparts", "lumbercart", "p_gen_cart", "cart", "wagon")):
        return "wagon_cart_vehicle_host"
    if "hitch" in low or "horse" in low:
        return "hitch_or_horse_host"
    if "train" in low:
        return "trainstation_or_train_host"
    if "door" in low:
        return "door_or_interior_host"
    return "general_gringo_annotation_host"


def score_candidate(row: dict[str, Any]) -> tuple[int, str, str]:
    host = str(row.get("host_name", "")).lower()
    rec_kind = str(row.get("record_kind", ""))
    arr = str(row.get("array_name", ""))
    category = host_category(str(row.get("host_name", "")), str(row.get("full_string_value", "")))
    score = 70
    reasons: list[str] = []
    if rec_kind == "prop_record_0x30":
        score -= 24; reasons.append("actual props placement record resolved")
    elif rec_kind == "drawable_instance_0xE0":
        score -= 18; reasons.append("actual drawable instance transform resolved")
    else:
        score += 18; reasons.append("not resolved to known placement array")
    if category == "wagon_cart_vehicle_host":
        score -= 20; reasons.append("wagon/cart vehicle-adjacent host")
    elif category == "hitch_or_horse_host":
        score -= 12; reasons.append("hitch/horse gringo-adjacent host")
    elif category == "trainstation_or_train_host":
        score += 22; reasons.append("train/station asset; likely structural/high-risk")
    if any(t in host for t in ("broken", "parts", "parked")):
        score -= 7; reasons.append("static clutter/parked/broken target")
    if host.startswith("blk_"):
        score += 18; reasons.append("Blackwater structural/prefab name")
    if str(row.get("transform_confidence", "")) == "high":
        score -= 6; reasons.append("high-confidence transform")
    elif str(row.get("transform_confidence", "")) == "medium":
        score -= 3; reasons.append("medium-confidence position")
    if arr not in ("props", "drawable_instances", "drawable_instances2"):
        score += 12; reasons.append("array lane not a preferred test target")
    action = "inspect only"
    if score <= 32:
        action = "best single-placement copied-RPF experiment candidate; do not bulk patch"
    elif score <= 48:
        action = "good resolver proof candidate; inspect placement bytes before patching"
    elif score <= 65:
        action = "secondary candidate; useful for mapping, not first patch"
    else:
        action = "avoid for first patch; keep as research context"
    return score, "; ".join(reasons), action


def resolve_payload(payload_item: dict[str, Any], hosts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve host strings to known WSI placement arrays.

    This intentionally stays on the proven fast path: string occurrence -> virtual
    pointer reference -> props/drawable array membership. Hash-only evidence is
    kept out of this pass because it is noisier and not needed for placement proof.
    """
    source = str(payload_item["source"])
    payload: bytes = payload_item["payload"]
    sectors = [parse_sector(payload, off) for off in sector_offsets(payload)]
    spans = build_array_spans(payload, sectors)
    pointer_index = build_pointer_index(payload)
    ascii_runs = build_ascii_runs(payload)
    all_candidates: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for host_row in hosts:
        host = str(host_row.get("host_name", ""))
        string_info = string_info_for_host(ascii_runs, host)
        by_offset = {int(x["string_offset"]): x for x in string_info}
        pointer_refs = find_pointer_refs_from_index(pointer_index, by_offset.keys())
        host_candidate_count = 0

        for ref in pointer_refs:
            ref_off = int(ref["reference_offset"])
            matching_string = by_offset.get(int(ref["string_offset"]), {})
            array_matches = resolve_reference_to_array(payload, ref_off, spans)
            if not array_matches:
                row = {
                    "wsi_source": source,
                    "host_name": host,
                    "host_hash_guess": host_row.get("host_hash_guess", f"0x{rdr_hash(host):08X}"),
                    "host_source": host_row.get("host_source", ""),
                    "full_string_value": matching_string.get("full_string_value", ""),
                    "string_offset_hex": ref.get("string_offset_hex", ""),
                    "string_ptr_hex": ref.get("string_ptr_hex", ""),
                    "reference_offset_hex": ref.get("reference_offset_hex", ""),
                    "reference_resolution": "string_pointer_ref_found_but_no_known_array_record_match",
                    "record_kind": "unresolved_pointer_reference",
                    "array_match_confidence": "low",
                }
                score, reason, action = score_candidate(row)
                row["candidate_score_lower_is_safer"] = score
                row["candidate_reason"] = reason
                row["recommended_action"] = action
                all_candidates.append(row)
                continue

            for parsed in array_matches:
                row = {
                    "wsi_source": source,
                    "host_name": host,
                    "host_hash_guess": host_row.get("host_hash_guess", f"0x{rdr_hash(host):08X}"),
                    "host_source": host_row.get("host_source", ""),
                    "candidate_score_from_correlator": host_row.get("candidate_score_from_correlator", ""),
                    "full_string_value": matching_string.get("full_string_value", ""),
                    "string_offset_hex": ref.get("string_offset_hex", ""),
                    "string_ptr_hex": ref.get("string_ptr_hex", ""),
                    "reference_offset_hex": ref.get("reference_offset_hex", ""),
                    "reference_resolution": "resolved_to_known_array_record",
                    **parsed,
                }
                score, reason, action = score_candidate(row)
                row["candidate_score_lower_is_safer"] = score
                row["candidate_reason"] = reason
                row["recommended_action"] = action
                all_candidates.append(row)
                host_candidate_count += 1

        sample_strings = []
        seen_samples: set[str] = set()
        for item in string_info:
            text = str(item.get("full_string_value", ""))
            if text and text not in seen_samples:
                seen_samples.add(text)
                sample_strings.append(text)
            if len(sample_strings) >= 20:
                break
        summary.append({
            "wsi_source": source,
            "host_name": host,
            "host_hash_guess": host_row.get("host_hash_guess", f"0x{rdr_hash(host):08X}"),
            "string_occurrence_count": len(string_info),
            "pointer_reference_count": len(pointer_refs),
            "hash_reference_count": "not_used_in_pass3",
            "resolved_known_array_candidate_count": host_candidate_count,
            "sample_full_strings": " | ".join(sample_strings)[:1000],
        })
        if not host_candidate_count:
            unresolved.append({
                "wsi_source": source,
                "host_name": host,
                "host_hash_guess": host_row.get("host_hash_guess", f"0x{rdr_hash(host):08X}"),
                "string_occurrence_count": len(string_info),
                "pointer_reference_count": len(pointer_refs),
                "hash_reference_count": "not_used_in_pass3",
                "reason": "no pointer reference resolved to props/drawable_instances known record layout",
            })
    return all_candidates, summary, unresolved, sectors


def build_safe_candidates(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("reference_resolution") != "resolved_to_known_array_record":
            continue
        key = (
            str(row.get("host_name", "")),
            str(row.get("record_kind", "")),
            str(row.get("record_offset_hex", "")),
            str(row.get("array_name", "")),
        )
        prev = unique.get(key)
        if prev is None or int(row.get("candidate_score_lower_is_safer", 999)) < int(prev.get("candidate_score_lower_is_safer", 999)):
            unique[key] = row
    out = list(unique.values())
    out.sort(key=lambda r: (int(r.get("candidate_score_lower_is_safer", 999)), str(r.get("host_name", "")), str(r.get("record_offset_hex", ""))))
    return out[: max(1, limit)]


def write_experiment_plan(path: Path, safe_rows: list[dict[str, Any]]) -> None:
    top = safe_rows[0] if safe_rows else {}
    text = f"""# Code RED — Single Placement Vehicle-Gringo Experiment Plan

This plan is generated by `tools/codered_wsi_host_placement_resolver.py`.

## Best current candidate

- Host: `{top.get('host_name', 'none')}`
- Record kind: `{top.get('record_kind', 'none')}`
- Record offset: `{top.get('record_offset_hex', 'none')}`
- Array: `{top.get('array_name', 'none')}` index `{top.get('array_index', 'none')}`
- Position guess: `{top.get('position_guess', 'none')}`
- Score: `{top.get('candidate_score_lower_is_safer', 'none')}`
- Reason: {top.get('candidate_reason', 'No safe candidate found.')}

## Rule

Do not bulk patch Blackwater WSI, WGD, WVD, or WBD. Use a copied archive only,
change one resolved placement at a time, reopen the RPF, decode the WSI, and export
proof JSON before in-game testing.

## Recommended next patch lane

1. Use the resolver output to inspect the exact record bytes for the best wagon/cart/broken/parked host.
2. Do not replace the host with raw `car01` again.
3. After field layout proof, test a single copied-RPF binding toward an existing gringo path such as:
   - `content\\scripting\\gringo\\CommonScripts\\Vehicle_Generator`
   - `content\\scripting\\gringo\\CommonScripts\\car_gringo`
   - `content\\scripting\\gringo\\CommonScripts\\PlayerCar`
4. Separately inspect WGD attributes / FBI mission scripts to determine whether tokens like
   `VEHICLE_Wagon02`, `VEHICLE_Coach01`, or `VEHICLE_WagonPrison01` are parameters rather than WSI names.

## Rollback

Keep the original RPF untouched. The experiment output should be a separate copied RPF plus a
patch proof JSON containing source archive, target archive, WSI path, record offset, old bytes,
new bytes, decoded SHA1, and reopen verification.
"""
    path.write_text(text, encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    hosts = load_hosts(args)
    payloads = load_wsi_payloads(args)

    all_rows: list[dict[str, Any]] = []
    all_summary: list[dict[str, Any]] = []
    all_unresolved: list[dict[str, Any]] = []
    all_sector_rows: list[dict[str, Any]] = []

    for payload_item in payloads:
        rows, summary, unresolved, sectors = resolve_payload(payload_item, hosts)
        all_rows.extend(rows)
        all_summary.extend(summary)
        all_unresolved.extend(unresolved)
        for sector in sectors:
            sector = dict(sector)
            sector["wsi_source"] = payload_item["source"]
            all_sector_rows.append(sector)

    safe_rows = build_safe_candidates(all_rows, args.safe_limit)

    write_csv(outdir / "blackwater_host_candidates.csv", all_rows)
    write_csv(outdir / "blackwater_safe_vehicle_test_candidates.csv", safe_rows)
    write_csv(outdir / "host_reference_summary.csv", all_summary)
    write_csv(outdir / "unresolved_hosts.csv", all_unresolved)
    write_csv(outdir / "sector_context.csv", all_sector_rows)
    (outdir / "blackwater_host_candidates.json").write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
    write_experiment_plan(outdir / "single_placement_experiment_plan.md", safe_rows)

    master = {
        "tool": "codered_wsi_host_placement_resolver.py",
        "payload_count": len(payloads),
        "host_count": len(hosts),
        "sector_count": len(all_sector_rows),
        "candidate_rows": len(all_rows),
        "safe_candidate_rows": len(safe_rows),
        "unresolved_hosts": len(all_unresolved),
        "payloads": [{"source": p["source"], "decoded_size": len(p["payload"]), "decoded_sha1": sha1(p["payload"])} for p in payloads],
        "outputs": {
            "blackwater_host_candidates": "blackwater_host_candidates.csv",
            "blackwater_safe_vehicle_test_candidates": "blackwater_safe_vehicle_test_candidates.csv",
            "host_reference_summary": "host_reference_summary.csv",
            "unresolved_hosts": "unresolved_hosts.csv",
            "sector_context": "sector_context.csv",
            "single_placement_experiment_plan": "single_placement_experiment_plan.md",
        },
        "risk_rule": "Read-only resolver. Patch copied archives only after exact field layout proof. Never bulk patch WSI/WGD/WVD/WBD.",
    }
    (outdir / "blackwater_host_resolver_master.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
    print(json.dumps(master, indent=2))
    print("Wrote", outdir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code RED WSI host placement resolver")
    parser.add_argument("--wsi-decoded", nargs="*", default=[], help="Decoded WSI payload(s), for example 0224_0x19839F99.wsi.decoded")
    parser.add_argument("--wsi-archive", help="RPF containing .wsi resources. Requires codered_wsi_explorer.py beside this tool.")
    parser.add_argument("--wsi-path", help="Specific .wsi path inside --wsi-archive. If omitted, all .wsi entries are scanned.")
    parser.add_argument("--candidate-hosts", nargs="*", default=[], help="CSV from correlator: wsi_annotation_candidate_hosts.csv")
    parser.add_argument("--host", nargs="*", default=[], help="Manual host names to resolve")
    parser.add_argument("--default-priority-hosts", action="store_true", help="Also include the current Code RED wagon/cart/hitch priority host list")
    parser.add_argument("--outdir", default="exports/wsi_host_placement_resolver")
    parser.add_argument("--safe-limit", type=int, default=50)
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
