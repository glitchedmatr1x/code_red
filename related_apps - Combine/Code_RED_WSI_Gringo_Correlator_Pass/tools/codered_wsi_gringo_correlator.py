#!/usr/bin/env python3
"""Code RED WSI <-> WGD gringo correlator.

This tool connects the current safe WSI research lane to the gringo dictionary lane:

- Decode/export WSI sector context from a copied/vanilla RPF or decoded WSI payload.
- Scan WSI strings and 32-bit hash lanes for gringo/vehicle-related references.
- Parse direct WGD files or previously exported WGD component JSON/CSV.
- Resolve WSI names/hashes against WGD QueryName, ScriptName, GringoName,
  HashCode, and HashedName fields.
- Emit conservative proof tables before any WSI/WGD patch is attempted.

The output is intentionally read-only. It does not patch WSI, WGD, WVD, or WBD.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import struct
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from codered_wsi_explorer import RPF6, VBASE, SAG_SECTORINFO_VFT, hash_map, load_names, rdr_hash, rsc_decode, sha1

try:
    from codered_gringo_wgd_export import scan_wgd  # type: ignore
except Exception:  # pragma: no cover - keeps --wgd-components usable if parser import fails
    scan_wgd = None  # type: ignore


DEFAULT_KEYWORDS = "gringo|has_gringo|gringo_available|vehicle|car|wagon|coach|cart|train|turret|gatling|maxim|horse"
STRING_RE = re.compile(rb"[\x20-\x7E]{4,}")


def u8(data: bytes, off: int) -> int:
    return data[off] if 0 <= off < len(data) else 0


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0] if off + 2 <= len(data) else 0


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0] if off + 4 <= len(data) else 0


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0] if off + 4 <= len(data) else 0.0


def vec4(data: bytes, off: int) -> list[float]:
    if off + 16 > len(data):
        return []
    return [round(v, 6) for v in struct.unpack_from("<4f", data, off)]


def target(ptr: int, size: int) -> int | None:
    if VBASE <= ptr < VBASE + size:
        return ptr - VBASE
    return None


def ptr_hex(value: int) -> str:
    return f"0x{value:08X}" if value else ""


def read_cstr(data: bytes, off: int | None, max_len: int = 500) -> str:
    if off is None or off < 0 or off >= len(data):
        return ""
    end = off
    while end < len(data) and end - off < max_len and data[end] != 0:
        end += 1
    return data[off:end].decode("latin-1", "replace")


def arr_desc(data: bytes, off: int) -> dict[str, Any]:
    ptr = u32(data, off)
    return {
        "ptr": ptr,
        "ptr_hex": ptr_hex(ptr),
        "offset": target(ptr, len(data)),
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


def json_rows(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text("utf-8", errors="replace"))
    if isinstance(obj, list):
        return [row for row in obj if isinstance(row, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "components", "all_components"):
            value = obj.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def sector_offsets(payload: bytes) -> list[int]:
    sig = struct.pack("<I", SAG_SECTORINFO_VFT)
    offsets: list[int] = []
    start = 0
    while True:
        off = payload.find(sig, start)
        if off < 0:
            break
        if off % 4 == 0 and off + 0x1D4 <= len(payload):
            offsets.append(off)
        start = off + 4
    return offsets


def parse_sector(payload: bytes, off: int, names: dict[int, str]) -> dict[str, Any]:
    name_ptr = u32(payload, off + 8)
    scope_ptr = u32(payload, off + 0x1B0)
    scoped_hash = u32(payload, off + 0x1C)
    name_hash = u32(payload, off + 0x178)
    flags = u32(payload, off + 0x1C8)
    arrays = {
        "props": 0xD4,
        "doors_attributes": 0xDC,
        "children": 0xE8,
        "child_ptrs": 0xF4,
        "drawable_instances": 0xFC,
        "drawable_instances2": 0x104,
        "occluders": 0x17C,
        "locators": 0x1A0,
    }
    row: dict[str, Any] = {
        "sector_offset": off,
        "sector_offset_hex": f"0x{off:08X}",
        "sector_name": read_cstr(payload, target(name_ptr, len(payload))),
        "sector_scope": read_cstr(payload, target(scope_ptr, len(payload))),
        "scoped_name_hash": f"0x{scoped_hash:08X}" if scoped_hash else "",
        "scoped_name_resolved": names.get(scoped_hash, ""),
        "sector_name_hash": f"0x{name_hash:08X}" if name_hash else "",
        "sector_name_resolved": names.get(name_hash, ""),
        "bound_min": vec4(payload, off + 0xB0),
        "bound_max": vec4(payload, off + 0xC0),
        "flags": f"0x{flags:08X}",
        "disabled_flag_guess": bool(flags & 0x01000000),
        "resident_status": u32(payload, off + 0x188),
        "district": u8(payload, off + 0x1BD),
        "ref_count": u8(payload, off + 0x1C5),
    }
    for name, rel in arrays.items():
        desc = arr_desc(payload, off + rel)
        row[f"{name}_offset"] = desc["offset"]
        row[f"{name}_count"] = desc["count"]
    return row


def sector_context(sectors: list[dict[str, Any]], hit_offset: int) -> dict[str, Any]:
    if not sectors:
        return {}
    before = [s for s in sectors if int(s.get("sector_offset", -1)) <= hit_offset]
    sector = before[-1] if before else min(sectors, key=lambda s: abs(int(s.get("sector_offset", 0)) - hit_offset))
    return {
        "sector_offset_hex": sector.get("sector_offset_hex", ""),
        "sector_name": sector.get("sector_name", ""),
        "sector_scope": sector.get("sector_scope", ""),
        "sector_name_resolved": sector.get("sector_name_resolved", ""),
        "scoped_name_resolved": sector.get("scoped_name_resolved", ""),
        "bound_min": json.dumps(sector.get("bound_min", [])),
        "bound_max": json.dumps(sector.get("bound_max", [])),
        "district": sector.get("district", ""),
        "disabled_flag_guess": sector.get("disabled_flag_guess", ""),
    }


def keyword_match(text: str, pattern: re.Pattern[str]) -> bool:
    return bool(text and pattern.search(text))


def collect_name_variants(text: str) -> set[str]:
    variants: set[str] = set()
    if not text:
        return variants
    clean = text.strip().replace("/", "\\")
    if not clean:
        return variants
    variants.add(clean)
    variants.add(clean.replace("\\", "/"))
    tail = re.split(r"[/\\]", clean)[-1]
    if tail:
        variants.add(tail)
        variants.add(tail.rsplit(".", 1)[0])
    variants.add(clean.rsplit(".", 1)[0])
    return {v for v in variants if v}


def component_identity(row: dict[str, Any]) -> dict[str, Any]:
    script = str(row.get("script_name", "") or "")
    gringo = str(row.get("gringo_name", "") or "")
    query = str(row.get("query_name", "") or "")
    primary = gringo or query or script
    return {
        "wgd_offset_hex": row.get("offset_hex", ""),
        "wgd_component_type": row.get("component_type", ""),
        "wgd_query_name": query,
        "wgd_script_name": script,
        "wgd_gringo_name": gringo,
        "wgd_primary_name": primary,
        "wgd_hash_code": row.get("hash_code", ""),
        "wgd_hashed_name": row.get("hashed_name", ""),
        "wgd_activation_radius": row.get("activation_radius", ""),
        "wgd_child_count": row.get("child_count", ""),
        "wgd_use_context_count": row.get("use_context_count", ""),
        "wgd_instanced_item_count": row.get("instanced_item_count", ""),
        "wgd_instance_slot_count": row.get("instance_slot_count", ""),
        "wgd_critical": row.get("critical", ""),
        "wgd_maintain_state": row.get("maintain_state", ""),
        "wgd_player_usable": row.get("player_usable", ""),
        "wgd_gringo_handles_movement": row.get("gringo_handles_movement", ""),
        "wgd_requires_physics_check": row.get("requires_physics_check", ""),
        "wgd_allow_ai_shoot": row.get("allow_ai_shoot", ""),
        "wgd_allow_navigate_to": row.get("allow_navigate_to", ""),
    }


def normalize_hex(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = int(text, 0)
        if parsed == 0:
            return ""
        return f"0x{parsed:08X}"
    except Exception:
        if text.lower() in ("0x00000000", "00000000"):
            return ""
        return text.upper() if text.lower().startswith("0x") else text


def enrich_use_context_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_parent: dict[str, int] = {}
    for row in rows:
        if str(row.get("component_type", "")) != "UseContext":
            continue
        parent = row.get("parent_offset")
        if parent in (None, "", "None"):
            continue
        try:
            key = f"0x{int(parent):08X}"
        except Exception:
            continue
        by_parent[key] = by_parent.get(key, 0) + 1
    for row in rows:
        off = row.get("offset")
        key = ""
        try:
            key = f"0x{int(off):08X}"
        except Exception:
            key = str(row.get("offset_hex", ""))
        row["use_context_count"] = by_parent.get(key, row.get("use_context_count", 0))
    return rows


def load_wgd_components(paths: Iterable[str], components_paths: Iterable[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in components_paths:
        path = Path(item)
        if not path.exists():
            continue
        if path.suffix.lower() == ".csv":
            rows.extend(read_csv(path))
        elif path.suffix.lower() == ".json":
            rows.extend(json_rows(path))
    for item in paths:
        path = Path(item)
        if not path.exists():
            continue
        if scan_wgd is None:
            raise SystemExit("Direct --wgd parsing requires tools/codered_gringo_wgd_export.py to import cleanly. Use --wgd-components as a fallback.")
        _decoded, found = scan_wgd(path)
        for row in found:
            row["source_file"] = str(path)
        rows.extend(found)
    return enrich_use_context_counts(rows)


def build_wgd_indexes(rows: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], set[str]]:
    by_text: dict[str, list[dict[str, Any]]] = {}
    by_hash: dict[str, list[dict[str, Any]]] = {}
    name_set: set[str] = set()
    for row in rows:
        text_fields = [
            str(row.get("query_name", "") or ""),
            str(row.get("script_name", "") or ""),
            str(row.get("gringo_name", "") or ""),
            str(row.get("user_tag", "") or ""),
            str(row.get("race_type", "") or ""),
        ]
        for text in text_fields:
            for variant in collect_name_variants(text):
                key = variant.lower()
                by_text.setdefault(key, []).append(row)
                name_set.add(variant)
                by_hash.setdefault(f"0x{rdr_hash(variant):08X}", []).append(row)
        for hfield in ("hash_code", "hashed_name"):
            h = normalize_hex(row.get(hfield))
            if h:
                by_hash.setdefault(h, []).append(row)
    return by_text, by_hash, name_set


def wgd_keyword_rows(rows: list[dict[str, Any]], pattern: re.Pattern[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        hay = " ".join(str(row.get(k, "") or "") for k in ("query_name", "script_name", "gringo_name", "user_tag", "race_type"))
        if keyword_match(hay, pattern):
            out.append(component_identity(row))
    return out


def scan_wsi_strings(payload: bytes, sectors: list[dict[str, Any]], pattern: re.Pattern[str], source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in STRING_RE.finditer(payload):
        text = match.group(0).decode("latin-1", "replace")
        if not keyword_match(text, pattern):
            continue
        row = {
            "wsi_source": source,
            "hit_kind": "ascii_string_keyword",
            "wsi_offset": match.start(),
            "wsi_offset_hex": f"0x{match.start():08X}",
            "wsi_value": text,
            "wsi_hash_guess": f"0x{rdr_hash(text):08X}",
        }
        row.update(sector_context(sectors, match.start()))
        rows.append(row)
    return rows


def classify_wsi_host(text: str) -> dict[str, Any]:
    """Extract useful host/annotation hints from WSI string-pool entries.

    Many Blackwater WSI hits are not direct WGD names. They are prop or
    drawable names with annotation suffixes, for example:

        i_gen_hitchingPost02x/a_has_gringo_gringoannotation_has_gringo
        i_gen_bench15x/gringo_available__sitbenchchair_

    These are still valuable because they point at existing placed objects that
    already carry a gringo annotation lane.
    """
    value = str(text or "").strip()
    host, sep, annotation = value.partition("/")
    host_low = host.lower()
    value_low = value.lower()
    annotation_low = annotation.lower()
    vehicle_terms = ("vehicle", "car", "wagon", "coach", "cart", "train", "turret", "gatling", "maxim")
    gringo_terms = ("has_gringo", "gringo_available", "gringoannotation", "has_a_gringo")
    if any(term in value_low for term in gringo_terms):
        category = "gringo_annotation_host"
    elif any(term in host_low for term in vehicle_terms):
        category = "transport_or_vehicle_static_host"
    elif "horse" in value_low or "hitch" in host_low:
        category = "horse_hitch_or_mount_host"
    else:
        category = "keyword_host"
    return {
        "host_name": host,
        "annotation_suffix": annotation if sep else "",
        "host_hash_guess": f"0x{rdr_hash(host):08X}" if host else "",
        "annotation_category": category,
        "contains_gringo_annotation": any(term in value_low for term in gringo_terms),
        "contains_transport_term": any(term in value_low for term in vehicle_terms),
        "contains_horse_or_hitch_term": ("horse" in value_low or "hitch" in value_low),
    }


def summarize_wsi_hosts(string_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for hit in string_hits:
        meta = classify_wsi_host(str(hit.get("wsi_value", "")))
        key = (str(hit.get("wsi_source", "")), meta["host_name"], meta["annotation_suffix"])
        row = grouped.setdefault(key, {
            "wsi_source": hit.get("wsi_source", ""),
            "host_name": meta["host_name"],
            "host_hash_guess": meta["host_hash_guess"],
            "annotation_suffix": meta["annotation_suffix"],
            "annotation_category": meta["annotation_category"],
            "hit_count": 0,
            "first_wsi_offset_hex": hit.get("wsi_offset_hex", ""),
            "sample_wsi_value": hit.get("wsi_value", ""),
            "sector_name_samples": set(),
            "sector_scope_samples": set(),
            "contains_gringo_annotation": meta["contains_gringo_annotation"],
            "contains_transport_term": meta["contains_transport_term"],
            "contains_horse_or_hitch_term": meta["contains_horse_or_hitch_term"],
            "recommended_action": "annotation/string-pool lead only; locate actual placement record before patching",
        })
        row["hit_count"] += 1
        if hit.get("sector_name"):
            row["sector_name_samples"].add(str(hit.get("sector_name")))
        if hit.get("sector_scope"):
            row["sector_scope_samples"].add(str(hit.get("sector_scope")))
        row["contains_gringo_annotation"] = bool(row["contains_gringo_annotation"] or meta["contains_gringo_annotation"])
        row["contains_transport_term"] = bool(row["contains_transport_term"] or meta["contains_transport_term"])
        row["contains_horse_or_hitch_term"] = bool(row["contains_horse_or_hitch_term"] or meta["contains_horse_or_hitch_term"])
    out: list[dict[str, Any]] = []
    for row in grouped.values():
        row["sector_name_samples"] = "; ".join(sorted(row["sector_name_samples"]))
        row["sector_scope_samples"] = "; ".join(sorted(row["sector_scope_samples"]))
        out.append(row)
    out.sort(key=lambda r: (str(r.get("annotation_category", "")), str(r.get("host_name", "")), str(r.get("annotation_suffix", ""))))
    return out


def annotation_candidate_score(row: dict[str, Any]) -> tuple[int, str]:
    score = 75
    reasons: list[str] = []
    cat = str(row.get("annotation_category", ""))
    host = str(row.get("host_name", "")).lower()
    suffix = str(row.get("annotation_suffix", "")).lower()
    if cat == "transport_or_vehicle_static_host":
        score -= 20; reasons.append("transport/static vehicle host")
    if cat == "horse_hitch_or_mount_host":
        score -= 18; reasons.append("horse hitch/mount host")
    if cat == "gringo_annotation_host":
        score -= 12; reasons.append("already has gringo annotation")
    if any(t in host for t in ("cart", "wagon", "coach", "train")):
        score -= 8; reasons.append("wagon/cart/train prop family")
    if "hitch" in host:
        score -= 8; reasons.append("hitching post family")
    if "available" in suffix or "has_gringo" in suffix:
        score -= 4; reasons.append("explicit availability/has-gringo suffix")
    try:
        count = int(row.get("hit_count", 0))
        if count > 5:
            score -= 3; reasons.append("repeated in WSI string pool")
    except Exception:
        pass
    return score, "; ".join(reasons) if reasons else "annotation lead"


def build_annotation_candidates(host_rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in host_rows:
        if not (row.get("contains_gringo_annotation") or row.get("contains_transport_term") or row.get("contains_horse_or_hitch_term")):
            continue
        score, reason = annotation_candidate_score(row)
        cand = dict(row)
        cand["candidate_score_lower_is_safer"] = score
        cand["candidate_reason"] = reason
        cand["candidate_source"] = "wsi_string_annotation_host"
        candidates.append(cand)
    candidates.sort(key=lambda r: (int(r.get("candidate_score_lower_is_safer", 999)), str(r.get("host_name", ""))))
    return candidates[:max(1, limit)]


def scan_wsi_hashes(payload: bytes, sectors: list[dict[str, Any]], wgd_by_hash: dict[str, list[dict[str, Any]]], source: str, max_rows: int = 250000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    noisy_hashes = {"0x00000000", "0xFFFFFFFF"}
    for off in range(0, max(0, len(payload) - 4), 4):
        value = u32(payload, off)
        if value in (0, 0xFFFFFFFF):
            continue
        h = f"0x{value:08X}"
        if h in noisy_hashes:
            continue
        matches = wgd_by_hash.get(h)
        if not matches:
            continue
        base = {
            "wsi_source": source,
            "hit_kind": "hash_match_to_wgd",
            "wsi_offset": off,
            "wsi_offset_hex": f"0x{off:08X}",
            "wsi_value": h,
            "wsi_hash_guess": h,
        }
        base.update(sector_context(sectors, off))
        for match in matches:
            row = dict(base)
            row.update(component_identity(match))
            rows.append(row)
            if len(rows) >= max_rows:
                return rows
    return rows


def wsi_string_candidates(text: str) -> set[str]:
    """Return full-string, path-tail, and embedded token candidates from a WSI ASCII run."""
    candidates: set[str] = set()
    for variant in collect_name_variants(text):
        candidates.add(variant)
    for token in re.findall(r"[A-Za-z0-9_$\\/.-]{4,}", text):
        for variant in collect_name_variants(token):
            candidates.add(variant)
    return {c for c in candidates if c}


def correlate_string_hits(string_hits: list[dict[str, Any]], by_text: dict[str, list[dict[str, Any]]], by_hash: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hit in string_hits:
        value = str(hit.get("wsi_value", "") or "")
        matched: list[tuple[str, dict[str, Any]]] = []
        seen: set[tuple[str, str]] = set()
        for variant in wsi_string_candidates(value):
            for row in by_text.get(variant.lower(), []):
                key = ("text", str(row.get("offset_hex", row.get("offset", ""))))
                if key not in seen:
                    seen.add(key)
                    matched.append(("text_exact_tail_or_embedded_token", row))
            h = f"0x{rdr_hash(variant):08X}"
            for row in by_hash.get(h, []):
                key = ("hash", str(row.get("offset_hex", row.get("offset", ""))))
                if key not in seen:
                    seen.add(key)
                    matched.append(("hash_of_wsi_string_variant", row))
        if not matched:
            rows.append({**hit, "match_kind": "keyword_only_no_wgd_match"})
            continue
        for reason, row in matched:
            out = dict(hit)
            out["match_kind"] = reason
            out.update(component_identity(row))
            rows.append(out)
    return rows


def load_wsi_payloads(archive: str | None, wsi_path: str | None, decoded_paths: list[str], names: list[str], no_debug: bool) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if archive:
        rpf = RPF6(archive, not no_debug)
        hmap = hash_map(rpf, load_names(names))
        entries = [rpf.find(wsi_path)] if wsi_path else rpf.files(".wsi")
        for entry in entries:
            if entry is None:
                raise KeyError(wsi_path)
            header, payload = rsc_decode(rpf.slot(entry))
            payloads.append({
                "source": entry.path,
                "source_archive": archive,
                "payload": payload,
                "rsc_header_hex": header.hex(),
                "entry": asdict(entry),
                "names": hmap,
            })
    for item in decoded_paths:
        path = Path(item)
        data = path.read_bytes()
        payloads.append({
            "source": str(path),
            "source_archive": "",
            "payload": data,
            "rsc_header_hex": "",
            "entry": {},
            "names": {},
        })
    return payloads


def choose_candidate(row: dict[str, Any]) -> tuple[int, str]:
    """Lower score means safer to inspect first. This is not an auto-patch decision."""
    text = " ".join(str(row.get(k, "") or "") for k in ("wgd_primary_name", "wgd_script_name", "wgd_gringo_name", "wsi_value"))
    low = text.lower()
    score = 50
    reasons: list[str] = []
    if any(term in low for term in ("vehicle_generator", "playercar", "car_gringo", "carcrank")):
        score -= 25
        reasons.append("vehicle-gringo lead")
    if any(term in low for term in ("wagon", "coach", "cart", "horse")):
        score -= 8
        reasons.append("stock transport token")
    if str(row.get("wgd_critical", "")) in ("1", "True", "true"):
        score += 20
        reasons.append("critical component")
    if str(row.get("wgd_maintain_state", "")) in ("1", "True", "true"):
        score += 6
        reasons.append("maintain-state component")
    if str(row.get("disabled_flag_guess", "")) in ("True", "true", "1"):
        score += 10
        reasons.append("disabled-sector guess")
    if not row.get("sector_name") and not row.get("sector_scope"):
        score += 5
        reasons.append("weak sector context")
    return score, "; ".join(reasons) if reasons else "neutral"


def correlate(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(args.keyword, re.I)

    wgd_rows = load_wgd_components(args.wgd, args.wgd_components)
    by_text, by_hash, wgd_names = build_wgd_indexes(wgd_rows)
    wgd_hits = wgd_keyword_rows(wgd_rows, pattern)

    wsi_payloads = load_wsi_payloads(args.wsi_archive, args.wsi_path, args.wsi_decoded, args.names, args.no_debug)
    if not wsi_payloads:
        raise SystemExit("No WSI input provided. Use --wsi-archive and optional --wsi-path, or --wsi-decoded.")
    if not wgd_rows:
        raise SystemExit("No WGD components provided. Use --wgd or --wgd-components.")

    all_sector_rows: list[dict[str, Any]] = []
    all_string_hits: list[dict[str, Any]] = []
    all_hash_hits: list[dict[str, Any]] = []
    all_correlations: list[dict[str, Any]] = []
    all_host_rows: list[dict[str, Any]] = []

    for item in wsi_payloads:
        payload: bytes = item["payload"]
        names: dict[int, str] = dict(item.get("names", {}))
        for name in wgd_names:
            names.setdefault(rdr_hash(name), name)
        source = str(item["source"])
        sectors = [parse_sector(payload, off, names) for off in sector_offsets(payload)]
        for sector in sectors:
            sector["wsi_source"] = source
            sector["decoded_sha1"] = sha1(payload)
        strings = scan_wsi_strings(payload, sectors, pattern, source)
        hashes = scan_wsi_hashes(payload, sectors, by_hash, source)
        correlations = correlate_string_hits(strings, by_text, by_hash) + hashes
        host_rows = summarize_wsi_hosts(strings)

        all_sector_rows.extend(sectors)
        all_string_hits.extend(strings)
        all_hash_hits.extend(hashes)
        all_correlations.extend(correlations)
        all_host_rows.extend(host_rows)

    candidate_rows: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str, str]] = set()
    for row in all_correlations:
        if not row.get("wgd_primary_name") and row.get("match_kind") == "keyword_only_no_wgd_match":
            continue
        score, reason = choose_candidate(row)
        key = (str(row.get("wsi_source", "")), str(row.get("wsi_offset_hex", "")), str(row.get("wgd_offset_hex", "")))
        if key in seen_candidates:
            continue
        seen_candidates.add(key)
        cand = dict(row)
        cand["candidate_score_lower_is_safer"] = score
        cand["candidate_reason"] = reason
        cand["recommended_action"] = "inspect-only; do not patch until WSI field format is verified"
        candidate_rows.append(cand)
    candidate_rows.sort(key=lambda r: (int(r.get("candidate_score_lower_is_safer", 999)), str(r.get("sector_name", "")), str(r.get("wgd_primary_name", ""))))
    annotation_candidates = build_annotation_candidates(all_host_rows, args.candidate_limit)

    write_csv(outdir / "wsi_sector_context.csv", all_sector_rows)
    write_csv(outdir / "wsi_keyword_string_hits.csv", all_string_hits)
    write_csv(outdir / "wsi_hash_matches_to_wgd.csv", all_hash_hits)
    write_csv(outdir / "wgd_keyword_components.csv", wgd_hits)
    write_csv(outdir / "wsi_wgd_correlations.csv", all_correlations)
    write_csv(outdir / "wsi_gringo_annotation_hosts.csv", all_host_rows)
    write_csv(outdir / "wsi_annotation_candidate_hosts.csv", annotation_candidates)
    write_csv(outdir / "safe_candidate_gringo_hosts.csv", candidate_rows[: max(1, args.candidate_limit)])

    master = {
        "keyword": args.keyword,
        "wgd_component_count": len(wgd_rows),
        "wgd_keyword_hit_count": len(wgd_hits),
        "wsi_payload_count": len(wsi_payloads),
        "wsi_sector_count": len(all_sector_rows),
        "wsi_keyword_string_hit_count": len(all_string_hits),
        "wsi_hash_match_count": len(all_hash_hits),
        "correlation_count": len(all_correlations),
        "candidate_count": len(candidate_rows),
        "wsi_annotation_host_count": len(all_host_rows),
        "wsi_annotation_candidate_count": len(annotation_candidates),
        "outputs": {
            "wsi_sector_context": "wsi_sector_context.csv",
            "wsi_keyword_string_hits": "wsi_keyword_string_hits.csv",
            "wsi_hash_matches_to_wgd": "wsi_hash_matches_to_wgd.csv",
            "wgd_keyword_components": "wgd_keyword_components.csv",
            "wsi_wgd_correlations": "wsi_wgd_correlations.csv",
            "wsi_gringo_annotation_hosts": "wsi_gringo_annotation_hosts.csv",
            "wsi_annotation_candidate_hosts": "wsi_annotation_candidate_hosts.csv",
            "safe_candidate_gringo_hosts": "safe_candidate_gringo_hosts.csv",
        },
        "risk_rule": "Read-only correlator. Patch copied archives only, one changed placement at a time, after WSI field format proof.",
    }
    (outdir / "wsi_gringo_correlation_master.json").write_text(json.dumps(master, indent=2), encoding="utf-8")
    print(json.dumps(master, indent=2))
    print("Wrote", outdir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code RED WSI <-> WGD gringo correlator")
    parser.add_argument("--wsi-archive", help="RPF containing .wsi resources, for example territory_swall/dlc03x/content archive")
    parser.add_argument("--wsi-path", help="Specific WSI path inside --wsi-archive. If omitted, all .wsi files are scanned.")
    parser.add_argument("--wsi-decoded", nargs="*", default=[], help="Already-decoded WSI payload(s), useful for prior exports/tests")
    parser.add_argument("--wgd", nargs="*", default=[], help="Decoded .wgd file(s) or raw RSC/zstd WGD slots")
    parser.add_argument("--wgd-components", nargs="*", default=[], help="Existing WGD component export JSON/CSV files from codered_gringo_wgd_export.py")
    parser.add_argument("--names", nargs="*", default=[], help="Optional names/hash dictionaries used to resolve WSI hashes")
    parser.add_argument("--keyword", default=DEFAULT_KEYWORDS)
    parser.add_argument("--outdir", default="exports/wsi_gringo_correlation")
    parser.add_argument("--candidate-limit", type=int, default=100)
    parser.add_argument("--max-hash-match-rows", type=int, default=250000, help="Safety cap for WSI hash-to-WGD rows after null/noisy hashes are ignored.")
    parser.add_argument("--no-debug", action="store_true", help="Disable encrypted debug-name recovery for RPFs")
    args = parser.parse_args()
    correlate(args)


if __name__ == "__main__":
    main()
