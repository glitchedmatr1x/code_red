#!/usr/bin/env python3
"""Code RED SCO/RPF safety probe.

This tool is intentionally conservative. It scans arbitrary binary script-like
files, performs same-size string/byte edits, compares byte-for-byte changes,
and delegates RPF reads/writes to the existing Code RED RPF helpers.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOOL_ROOT = Path(__file__).resolve().parent
CODE_RED_ROOT = TOOL_ROOT.parents[1]
TOOLS_ROOT = CODE_RED_ROOT / "tools"
BACKEND_WORKBENCH = CODE_RED_ROOT / "backend" / "python_workbench.py"

SUSPICIOUS_TERMS = [
    "rdr2init",
    "player_car",
    "playercar",
    "PlayerCar",
    "FBI04",
    "fbi04",
    "mission",
    "Mission",
    "vehicle",
    "car",
    "truck",
    "gringo",
    "smallbrain",
    "decor",
    "exclude",
    "remove",
]

KNOWN_RPF_TARGETS = [
    "content/release64/init/rdr2init.wsc",
    "content/release64/init/rdr2init.sco",
    "content/scripting/gringo/SimpleGringo/playercar.wsc",
    "content/North/Missions/FBI04/FBI04.wsc",
    "content/ai/game_main.tr",
    "content/ai/general_rules.tr",
    "content/ai/human_reactions.tr",
    "content/ai/tasks.tr",
]

FOLDER_TARGET_NAMES = {
    "rdr2init.sco",
    "rdr2init.wsc",
    "playercar.wsc",
    "fbi04.wsc",
}

SCRIPT_KEYWORD_GROUPS = {
    "rdr2init": [
        "rdr2init",
        "init/rdr2init",
        "rdr2init_each_load",
        "DLC_PRE_INIT_CONTENT",
        "DLC_INIT_CONTENT",
        "ZombiePack",
        "FuiEventMonitor",
        "short_update_thread",
        "medium_update_thread",
        "long_update_thread",
    ],
    "playercar": [
        "playercar",
        "player_car",
        "PlayerCar",
        "PlayerCarGringo_Car",
        "Stop use request actor mismatch",
        "GringoNoQuit",
        "DenyDamageTermination",
        "DoNotCleanUpUserSettings",
        "DisableResetProp",
        "Gringo_PropInUse",
        "Obstructed",
        "NoTeleport",
        "UseQuit",
        "MoveAllowance",
        "StartingPhaseTimeout",
        "UseLocationTolerance",
        "ActivationRadius",
        "ReuseDelay",
        "SET_PHYSINST_FROZEN",
        "SUSPEND_MOVER",
        "SET_MOVER_FROZEN",
    ],
    "fbi04": [
        "FBI04",
        "fbi04",
        "North/Missions/FBI04",
        "bACTOR_AVOID_SMALLBRAINS",
        "DISABLE_HORSE_WHISTLE",
        "PlayerHouse_NoHorse",
        "COMPANION_RELEASE_ACTOR",
    ],
    "tr": [
        "VehicleExit",
        "DriverAbandonFlee",
        "GetOnFoot",
        "human_reactions",
        "general_rules",
        "game_main",
        "tasks",
        "flee",
        "panic",
        "bail",
        "abandon",
    ],
    "vehicle_init": [
        "VEHICLE_Car01",
        "VEHICLE_Truck01",
        "template_vehiclecar01",
        "template_vehicletruck01",
        "simplegringo/car",
        "simplegringo/fix_car",
        "SimpleGringo/player_car",
        "Gen_Vehicle_Brain",
        "vehicle_generator",
    ],
}

BULK_SCRIPT_TYPES = {"SCO", "RSC85", "ZSTD"}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_workbench() -> Any:
    wb = load_module(BACKEND_WORKBENCH, "codered_sco_probe_workbench")
    if not hasattr(wb, "parse_rpf6"):
        raise RuntimeError(f"backend does not expose parse_rpf6: {BACKEND_WORKBENCH}")
    return wb


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def byte_hex(data: bytes, limit: int | None = None) -> str:
    view = data if limit is None else data[:limit]
    return view.hex(" ").upper()


@dataclass
class StringHit:
    offset: int
    byte_length: int
    text: str
    encoding: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "offset": self.offset,
            "offset_hex": f"0x{self.offset:X}",
            "byte_length": self.byte_length,
            "encoding": self.encoding,
            "text": self.text,
        }


def printable_ascii_strings(data: bytes, min_len: int = 4) -> list[StringHit]:
    hits: list[StringHit] = []
    for match in re.finditer(rb"[\x20-\x7E]{%d,}" % min_len, data):
        text = match.group(0).decode("ascii", errors="replace")
        hits.append(StringHit(match.start(), len(match.group(0)), text, "ascii"))
    return hits


def printable_utf16le_strings(data: bytes, min_chars: int = 4) -> list[StringHit]:
    hits: list[StringHit] = []
    pattern = re.compile((rb"(?:[\x20-\x7E]\x00){%d,}" % min_chars))
    for match in pattern.finditer(data):
        raw = match.group(0)
        try:
            text = raw.decode("utf-16le")
        except UnicodeDecodeError:
            continue
        hits.append(StringHit(match.start(), len(raw), text, "utf-16le"))
    return hits


def collect_strings(data: bytes) -> list[StringHit]:
    hits = printable_ascii_strings(data)
    hits.extend(printable_utf16le_strings(data))
    return sorted(hits, key=lambda hit: (hit.offset, hit.encoding))


def classify_header(data: bytes) -> dict[str, Any]:
    first16 = data[:16]
    magic4 = data[:4]
    magic4_be = int.from_bytes(magic4, "big", signed=False) if len(magic4) == 4 else None
    magic4_le = int.from_bytes(magic4, "little", signed=False) if len(magic4) == 4 else None
    known = []
    if magic4 == b"RSC\x85":
        known.append("RSC85_resource")
    if magic4 == b"\x85CSR":
        known.append("RSC85_swapped_or_85CSR")
    if magic4.startswith(b"SCR"):
        known.append("SCR_style_script_wrapper")
    if magic4 == b"\x28\xB5\x2F\xFD":
        known.append("zstandard_frame")
    return {
        "first_16_bytes": byte_hex(first16),
        "magic_4_ascii": magic4.decode("ascii", errors="replace"),
        "magic_4_hex": byte_hex(magic4),
        "magic_4_u32_be": magic4_be,
        "magic_4_u32_le": magic4_le,
        "known_header_hints": known,
    }


def guess_payload_type(path: str, data: bytes) -> str:
    suffix = Path(path.replace("\\", "/")).suffix.lower()
    magic = data[:4]
    if magic == b"RSC\x85" or magic == b"\x85CSR":
        return "RSC85"
    if magic == b"\x28\xB5\x2F\xFD":
        return "ZSTD"
    if data.lstrip().startswith(b"<"):
        return "XML"
    if suffix == ".xml":
        return "XML"
    if suffix == ".tr":
        return "TR"
    if suffix == ".wsc":
        return "WSC"
    if suffix == ".sco":
        return "SCO"
    if b"<scxml" in data[:256].lower():
        return "XML"
    if magic.startswith(b"SCR"):
        return "SCO"
    return "unknown"


def likely_script_paths(strings: list[StringHit]) -> list[dict[str, Any]]:
    out = []
    path_markers = ("/", "\\", "$/content", "content/", ".wsc", ".sco", ".xsc", ".csc", ".tr")
    for hit in strings:
        text = hit.text
        if any(marker.lower() in text.lower() for marker in path_markers):
            out.append(hit.to_dict())
    return out


def likely_native_or_function_names(strings: list[StringHit]) -> list[dict[str, Any]]:
    out = []
    name_re = re.compile(r"^[A-Z_][A-Z0-9_]{4,}$|^Function_\d+$|^[A-Za-z]+[A-Za-z0-9_]{4,}$")
    for hit in strings:
        if name_re.match(hit.text) and not any(ch in hit.text for ch in "/\\"):
            out.append(hit.to_dict())
    return out


def suspicious_hits(strings: list[StringHit]) -> list[dict[str, Any]]:
    rows = []
    for hit in strings:
        low = hit.text.lower()
        terms = [term for term in SUSPICIOUS_TERMS if term.lower() in low]
        if terms:
            row = hit.to_dict()
            row["matched_terms"] = terms
            rows.append(row)
    return rows


def scan_sco(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except Exception as exc:
        return {
            "input": str(path),
            "ok": False,
            "unsupported_format": True,
            "error": str(exc),
        }
    strings = collect_strings(data)
    return {
        "input": str(path),
        "ok": True,
        "unsupported_format": False,
        "file_size": len(data),
        "sha256": sha256_bytes(data),
        "header": classify_header(data),
        "string_count": len(strings),
        "strings": [hit.to_dict() for hit in strings],
        "possible_script_paths": likely_script_paths(strings),
        "possible_native_or_function_names": likely_native_or_function_names(strings),
        "suspicious_strings": suspicious_hits(strings),
        "notes": [
            "This is a binary/string inspection report only.",
            "No SCO bytecode semantics are inferred from string hits alone.",
        ],
    }


def strings_sco(path: Path) -> str:
    report = scan_sco(path)
    lines = [
        f"# strings-sco: {path}",
        f"ok={report.get('ok')}",
        f"sha256={report.get('sha256', '')}",
        "",
        "offset_hex,offset,byte_length,encoding,text",
    ]
    for row in report.get("strings", []):
        text = str(row["text"]).replace("\r", "\\r").replace("\n", "\\n")
        lines.append(f"{row['offset_hex']},{row['offset']},{row['byte_length']},{row['encoding']},{text}")
    return "\n".join(lines) + "\n"


def compare_bytes(original: bytes, candidate: bytes) -> dict[str, Any]:
    limit = max(len(original), len(candidate))
    changed_offsets = []
    runs = []
    run_start = None
    run_old = bytearray()
    run_new = bytearray()
    for i in range(limit):
        old = original[i] if i < len(original) else None
        new = candidate[i] if i < len(candidate) else None
        if old != new:
            changed_offsets.append(i)
            if run_start is None:
                run_start = i
                run_old = bytearray()
                run_new = bytearray()
            if old is not None:
                run_old.append(old)
            if new is not None:
                run_new.append(new)
        elif run_start is not None:
            runs.append(
                {
                    "offset": run_start,
                    "offset_hex": f"0x{run_start:X}",
                    "length_old": len(run_old),
                    "length_new": len(run_new),
                    "old_hex": byte_hex(bytes(run_old)),
                    "new_hex": byte_hex(bytes(run_new)),
                }
            )
            run_start = None
    if run_start is not None:
        runs.append(
            {
                "offset": run_start,
                "offset_hex": f"0x{run_start:X}",
                "length_old": len(run_old),
                "length_new": len(run_new),
                "old_hex": byte_hex(bytes(run_old)),
                "new_hex": byte_hex(bytes(run_new)),
            }
        )
    return {
        "same_size": len(original) == len(candidate),
        "original_size": len(original),
        "candidate_size": len(candidate),
        "changed_byte_count": len(changed_offsets),
        "changed_run_count": len(runs),
        "changed_runs": runs,
    }


def compare_sco(original: Path, candidate: Path) -> dict[str, Any]:
    old = original.read_bytes()
    new = candidate.read_bytes()
    return {
        "original": str(original),
        "candidate": str(candidate),
        "original_sha256": sha256_bytes(old),
        "candidate_sha256": sha256_bytes(new),
        **compare_bytes(old, new),
    }


def encode_patch_text(value: str, encoding: str) -> bytes:
    if encoding.lower() in {"ascii", "utf-8", "utf8"}:
        return value.encode("utf-8")
    if encoding.lower() in {"utf-16le", "utf16le"}:
        return value.encode("utf-16le")
    raise ValueError(f"unsupported patch encoding: {encoding}")


def load_patch_file(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("patches"), list):
        return data["patches"]
    raise ValueError("patch file must be a list or an object with a 'patches' list")


def apply_sco_string_patches(input_path: Path, patch_path: Path, output_path: Path, allow_padding: bool) -> dict[str, Any]:
    original = input_path.read_bytes()
    data = bytearray(original)
    patches = load_patch_file(patch_path)
    changes: list[dict[str, Any]] = []
    for index, patch in enumerate(patches):
        encoding = str(patch.get("encoding", "utf-8"))
        old_text = str(patch.get("old", ""))
        new_text = str(patch.get("new", ""))
        if old_text == "":
            raise ValueError(f"patch {index}: old string must not be empty")
        old_bytes = encode_patch_text(old_text, encoding)
        new_bytes_raw = encode_patch_text(new_text, encoding)
        if len(new_bytes_raw) > len(old_bytes):
            raise ValueError(
                f"patch {index}: replacement is longer ({len(new_bytes_raw)}) than original ({len(old_bytes)})"
            )
        padded = False
        if len(new_bytes_raw) < len(old_bytes):
            if not allow_padding:
                raise ValueError(
                    f"patch {index}: replacement is shorter ({len(new_bytes_raw)}) than original ({len(old_bytes)}); "
                    "rerun with --allow-padding to null-pad"
                )
            new_bytes = new_bytes_raw + (b"\x00" * (len(old_bytes) - len(new_bytes_raw)))
            padded = True
        else:
            new_bytes = new_bytes_raw
        if "offset" in patch:
            offsets = [int(patch["offset"], 0) if isinstance(patch["offset"], str) else int(patch["offset"])]
        else:
            offsets = [m.start() for m in re.finditer(re.escape(old_bytes), bytes(data))]
        if not offsets:
            raise ValueError(f"patch {index}: old string not found: {old_text!r}")
        max_replacements = int(patch.get("max_replacements", len(offsets)))
        if len(offsets) > max_replacements:
            raise ValueError(
                f"patch {index}: found {len(offsets)} matches for {old_text!r}, over max_replacements={max_replacements}"
            )
        for offset in offsets:
            existing = bytes(data[offset : offset + len(old_bytes)])
            if existing != old_bytes:
                raise ValueError(
                    f"patch {index}: bytes at 0x{offset:X} do not match expected old string"
                )
            data[offset : offset + len(old_bytes)] = new_bytes
            changes.append(
                {
                    "patch_index": index,
                    "offset": offset,
                    "offset_hex": f"0x{offset:X}",
                    "encoding": encoding,
                    "old_text": old_text,
                    "new_text": new_text,
                    "old_byte_length": len(old_bytes),
                    "new_byte_length": len(new_bytes),
                    "null_padded": padded,
                    "old_hex": byte_hex(old_bytes),
                    "new_hex": byte_hex(new_bytes),
                }
            )
    if len(data) != len(original):
        raise AssertionError("internal error: patch changed file length")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(data))
    return {
        "input": str(input_path),
        "patch_file": str(patch_path),
        "output": str(output_path),
        "allow_padding": allow_padding,
        "original_size": len(original),
        "output_size": len(data),
        "size_unchanged": len(original) == len(data),
        "original_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(bytes(data)),
        "change_count": len(changes),
        "changes": changes,
        "compare": compare_bytes(original, bytes(data)),
    }


def find_entries_by_substrings(info: dict[str, Any], substrings: list[str]) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {}
    for term in substrings:
        low_term = term.lower()
        matches: list[dict[str, Any]] = []
        for ent in info.get("entries", []):
            if ent.get("type") != "file":
                continue
            haystack = " ".join(
                [
                    str(ent.get("path") or ""),
                    str(ent.get("name") or ""),
                    str(ent.get("extension") or ""),
                ]
            ).lower()
            if low_term in haystack:
                matches.append(
                    {
                        "index": ent.get("index"),
                        "path": ent.get("path"),
                        "name": ent.get("name"),
                        "offset": ent.get("offset"),
                        "size_in_archive": ent.get("size_in_archive"),
                        "total_size": ent.get("total_size"),
                        "is_resource": ent.get("is_resource"),
                        "resource_type": ent.get("resource_type"),
                    }
                )
        results[term] = matches
    return results


def dump_all_backend_entries(info: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ent in info.get("entries", []):
        rows.append(
            {
                "index": ent.get("index"),
                "type": ent.get("type"),
                "path": ent.get("path"),
                "name": ent.get("name"),
                "extension": ent.get("extension"),
                "offset": ent.get("offset"),
                "offset_raw": ent.get("offset_raw"),
                "size_in_archive": ent.get("size_in_archive"),
                "total_size": ent.get("total_size"),
                "is_resource": ent.get("is_resource"),
                "resource_type": ent.get("resource_type"),
                "is_compressed": ent.get("is_compressed"),
                "flag1": ent.get("flag1"),
                "flag2": ent.get("flag2"),
            }
        )
    return rows


def raw_string_search(archive: Path, terms: list[str]) -> list[dict[str, Any]]:
    data = archive.read_bytes()
    results: list[dict[str, Any]] = []
    for term in terms:
        needle = term.encode("utf-8")
        hits: list[dict[str, Any]] = []
        start = 0
        while True:
            offset = data.find(needle, start)
            if offset < 0:
                break
            before = max(0, offset - 32)
            after = min(len(data), offset + len(needle) + 32)
            hits.append(
                {
                    "offset": offset,
                    "offset_hex": f"0x{offset:X}",
                    "term": term,
                    "context_hex": byte_hex(data[before:after]),
                    "context_ascii": data[before:after].decode("ascii", errors="replace"),
                }
            )
            start = offset + max(1, len(needle))
        results.append({"term": term, "hit_count": len(hits), "hits": hits})
    return results


def classify_rpf_entries(archive: Path, info: dict[str, Any]) -> list[dict[str, Any]]:
    wb = load_workbench()
    rows: list[dict[str, Any]] = []
    with archive.open("rb") as fh:
        for ent in info.get("entries", []):
            if ent.get("type") != "file":
                continue
            path = str(ent.get("path") or ent.get("name") or f"entry_{ent.get('index')}")
            packed_size = int(ent.get("size_in_archive") or 0)
            offset = int(ent.get("offset") or 0)
            raw_first16 = b""
            try:
                if offset >= 0 and packed_size > 0:
                    fh.seek(offset)
                    raw_first16 = fh.read(min(16, packed_size))
            except Exception:
                raw_first16 = b""
            extracted = b""
            extract_error = ""
            try:
                extracted = wb.extract_rpf_entry(archive, ent)
            except Exception as exc:
                extract_error = str(exc)
            first16 = extracted[:16] if extracted else raw_first16
            rows.append(
                {
                    "index": ent.get("index"),
                    "resolved_path": ent.get("path"),
                    "name": ent.get("name"),
                    "offset": offset,
                    "offset_hex": f"0x{offset:X}",
                    "packed_size": packed_size,
                    "unpacked_size": ent.get("total_size"),
                    "is_resource": ent.get("is_resource"),
                    "resource_type": ent.get("resource_type"),
                    "is_compressed": ent.get("is_compressed"),
                    "flag1": ent.get("flag1"),
                    "flag2": ent.get("flag2"),
                    "first_16_bytes": byte_hex(first16),
                    "raw_first_16_bytes": byte_hex(raw_first16),
                    "guessed_type": guess_payload_type(path, first16),
                    "extractable": bool(extracted),
                    "entry_sha256": sha256_bytes(extracted) if extracted else "",
                    "extracted_size": len(extracted) if extracted else 0,
                    "extract_error": extract_error,
                }
            )
    return rows


def default_rdr_exe_candidates() -> list[Path]:
    return [
        CODE_RED_ROOT.parent / "game" / "RDR.exe",
        CODE_RED_ROOT.parent / "RDR.exe",
        CODE_RED_ROOT / "RDR.exe",
    ]


def try_decode_rsc85(data: bytes, temp_path: Path) -> dict[str, Any]:
    if not (data.startswith(b"RSC\x85") or data.startswith(b"\x85CSR")):
        return {"attempted": False, "ok": False, "reason": "not_rsc85_header", "decoded": b""}
    try:
        if str(CODE_RED_ROOT) not in sys.path:
            sys.path.insert(0, str(CODE_RED_ROOT))
        from codered_wsc.resource import KeyOptions, open_script
    except Exception as exc:
        return {"attempted": True, "ok": False, "error": f"codered_wsc import failed: {exc}", "decoded": b""}
    errors: list[str] = []
    exe_candidates = [path for path in default_rdr_exe_candidates() if path.exists()]
    option_sets = [KeyOptions()]
    option_sets.extend(KeyOptions(rdr_exe=str(path)) for path in exe_candidates)
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(data)
    for options in option_sets:
        try:
            resource = open_script(temp_path, options)
        except Exception as exc:
            errors.append(str(exc))
            continue
        if resource.decoded:
            return {
                "attempted": True,
                "ok": True,
                "decoded": resource.decoded,
                "header": resource.header_dict(),
            }
        errors.append(resource.decode_error or "RSC85 resource opened but produced no decoded payload")
    return {
        "attempted": True,
        "ok": False,
        "error": "; ".join(dict.fromkeys(errors))[:2000],
        "decoded": b"",
    }


def try_decode_zstd(data: bytes) -> dict[str, Any]:
    if not data.startswith(b"\x28\xB5\x2F\xFD"):
        return {"attempted": False, "ok": False, "reason": "not_zstd_frame", "decoded": b""}
    try:
        import zstandard as zstd
    except Exception as exc:
        return {"attempted": True, "ok": False, "error": f"zstandard import failed: {exc}", "decoded": b""}
    try:
        decoded = zstd.ZstdDecompressor().decompress(data)
    except Exception as exc:
        return {"attempted": True, "ok": False, "error": str(exc), "decoded": b""}
    return {"attempted": True, "ok": True, "decoded": decoded}


def match_script_keywords(strings: list[dict[str, Any]], index: int) -> tuple[dict[str, int], list[dict[str, Any]], int]:
    group_scores = {group: 0 for group in SCRIPT_KEYWORD_GROUPS}
    rows: list[dict[str, Any]] = []
    unique_hits: set[tuple[str, str]] = set()
    for item in strings:
        text = str(item.get("text") or "")
        low = text.lower()
        for group, keywords in SCRIPT_KEYWORD_GROUPS.items():
            for keyword in keywords:
                if keyword.lower() not in low:
                    continue
                group_scores[group] += 1
                unique_hits.add((group, keyword.lower()))
                rows.append(
                    {
                        "index": index,
                        "group": group,
                        "keyword": keyword,
                        "source": item.get("source"),
                        "offset": item.get("offset"),
                        "offset_hex": item.get("offset_hex"),
                        "encoding": item.get("encoding"),
                        "text": text,
                    }
                )
    return group_scores, rows, len(unique_hits)


def script_candidate_rank(row: dict[str, Any]) -> float:
    type_bonus = {"RSC85": 20.0, "SCO": 18.0, "ZSTD": 12.0, "unknown": 0.0}.get(str(row.get("guessed_type")), 0.0)
    hit_score = float(row.get("keyword_hit_count") or 0) * 25.0
    unique_score = float(row.get("unique_keyword_hit_count") or 0) * 45.0
    decoded_score = min(float(row.get("decoded_string_count") or 0), 500.0) * 0.2
    raw_score = min(float(row.get("raw_string_count") or 0), 500.0) * 0.05
    size = float(row.get("extracted_size") or row.get("packed_size") or 0)
    size_score = 8.0 if 512 <= size <= 1024 * 1024 else 0.0
    return unique_score + hit_score + decoded_score + raw_score + type_bonus + size_score


def format_top_candidates(candidates: list[dict[str, Any]], limit: int = 25) -> str:
    lines = [
        "# Code RED Script Candidate Hunt",
        "",
        "Ranked by keyword hits, decoded string count, printable string count, likely type, size, and index.",
        "",
        "| Rank | Index | Type | Score | Groups | Hits | Raw Strings | Decoded Strings | Size | Path/Name |",
        "|---:|---:|---|---:|---|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(candidates[:limit], start=1):
        groups = ", ".join(
            f"{group}:{score}"
            for group, score in sorted((row.get("group_scores") or {}).items())
            if score
        )
        path = str(row.get("resolved_path") or row.get("name") or "")
        lines.append(
            f"| {rank} | {row.get('index')} | {row.get('guessed_type')} | {row.get('rank_score'):.2f} | "
            f"{groups or '-'} | {row.get('keyword_hit_count')} | {row.get('raw_string_count')} | "
            f"{row.get('decoded_string_count')} | {row.get('extracted_size')} | `{path}` |"
        )
    lines.extend(["", "## Top Candidate Details", ""])
    for row in candidates[:limit]:
        lines.append(f"### Index {row.get('index')} - {row.get('guessed_type')} - score {row.get('rank_score'):.2f}")
        lines.append(f"- Path/name: `{row.get('resolved_path') or row.get('name') or ''}`")
        lines.append(f"- Offset: {row.get('offset_hex')} packed={row.get('packed_size')} extracted={row.get('extracted_size')}")
        groups = {k: v for k, v in (row.get("group_scores") or {}).items() if v}
        lines.append(f"- Groups: {groups if groups else 'none'}")
        if row.get("sample_keyword_strings"):
            lines.append("- Sample keyword strings:")
            for text in row.get("sample_keyword_strings", [])[:8]:
                clean = str(text).replace("\n", "\\n").replace("\r", "\\r")
                lines.append(f"  - `{clean[:180]}`")
        elif row.get("sample_strings"):
            lines.append("- Sample strings:")
            for text in row.get("sample_strings", [])[:5]:
                clean = str(text).replace("\n", "\\n").replace("\r", "\\r")
                lines.append(f"  - `{clean[:180]}`")
        lines.append("")
    return "\n".join(lines)


def bulk_scan_rpf_scripts(archive: Path, out_folder: Path, unknown_max_size: int = 256 * 1024) -> dict[str, Any]:
    wb = load_workbench()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"RPF6 parser returned None: {archive}")
    out_folder.mkdir(parents=True, exist_ok=True)
    classified = classify_rpf_entries(archive, info)
    inventory: list[dict[str, Any]] = []
    strings_rows: list[dict[str, Any]] = []
    keyword_rows: list[dict[str, Any]] = []
    scanned_count = 0
    skipped_count = 0
    temp_root = Path(tempfile.mkdtemp(prefix="codered_script_candidates_"))
    try:
        by_index = {
            int(ent.get("index")): ent
            for ent in info.get("entries", [])
            if ent.get("type") == "file" and ent.get("index") is not None
        }
        for row in classified:
            guessed = str(row.get("guessed_type") or "unknown")
            extracted_size = int(row.get("extracted_size") or 0)
            packed_size = int(row.get("packed_size") or 0)
            should_scan = guessed in BULK_SCRIPT_TYPES or (guessed == "unknown" and 0 < extracted_size <= unknown_max_size)
            if not row.get("extractable") or not should_scan:
                skipped_count += 1
                continue
            index = int(row["index"])
            ent = by_index.get(index)
            if not ent:
                skipped_count += 1
                continue
            try:
                data = wb.extract_rpf_entry(archive, ent)
            except Exception as exc:
                item = dict(row)
                item.update(
                    {
                        "scan_error": str(exc),
                        "raw_string_count": 0,
                        "decoded_string_count": 0,
                        "keyword_hit_count": 0,
                        "unique_keyword_hit_count": 0,
                        "group_scores": {group: 0 for group in SCRIPT_KEYWORD_GROUPS},
                        "rank_score": 0.0,
                    }
                )
                inventory.append(item)
                continue
            scanned_count += 1
            raw_hits = collect_strings(data)
            string_dicts: list[dict[str, Any]] = []
            for hit in raw_hits:
                entry = hit.to_dict()
                entry.update({"index": index, "source": "raw"})
                string_dicts.append(entry)
                strings_rows.append(entry)
            decoded_payloads: list[tuple[str, bytes, dict[str, Any]]] = []
            if guessed == "RSC85" or data.startswith((b"RSC\x85", b"\x85CSR")):
                decode = try_decode_rsc85(data, temp_root / f"entry_{index}.bin")
                if decode.get("ok") and decode.get("decoded"):
                    decoded_payloads.append(("rsc85_decoded", decode["decoded"], decode))
                elif decode.get("attempted"):
                    decode_notes.append(
                        {
                            "source": "rsc85",
                            "decoded_size": 0,
                            "error": str(decode.get("error") or decode.get("reason") or "decode_failed")[:2000],
                        }
                    )
            if guessed == "ZSTD" or data.startswith(b"\x28\xB5\x2F\xFD"):
                decode = try_decode_zstd(data)
                if decode.get("ok") and decode.get("decoded"):
                    decoded_payloads.append(("zstd_decoded", decode["decoded"], decode))
                elif decode.get("attempted"):
                    decode_notes.append(
                        {
                            "source": "zstd",
                            "decoded_size": 0,
                            "error": str(decode.get("error") or decode.get("reason") or "decode_failed")[:2000],
                        }
                    )
            decoded_string_count = 0
            decode_notes: list[dict[str, Any]] = []
            for source, payload, meta in decoded_payloads:
                decoded_hits = collect_strings(payload)
                decoded_string_count += len(decoded_hits)
                decode_notes.append(
                    {
                        "source": source,
                        "decoded_size": len(payload),
                        "decoded_sha256": sha256_bytes(payload),
                    }
                )
                for hit in decoded_hits:
                    entry = hit.to_dict()
                    entry.update({"index": index, "source": source})
                    string_dicts.append(entry)
                    strings_rows.append(entry)
            if not decoded_payloads and (guessed in {"RSC85", "ZSTD"}):
                decode_notes.append({"source": guessed.lower(), "decoded_size": 0, "note": "decode_not_available_or_failed"})
            group_scores, hits, unique_keyword_hit_count = match_script_keywords(string_dicts, index)
            keyword_rows.extend(hits)
            sample_keyword_strings = []
            seen_samples: set[str] = set()
            for hit in hits:
                text = str(hit.get("text") or "")
                if text and text not in seen_samples:
                    seen_samples.add(text)
                    sample_keyword_strings.append(text)
            sample_strings = []
            for item in string_dicts[:20]:
                text = str(item.get("text") or "")
                if text and text not in sample_strings:
                    sample_strings.append(text)
            item = dict(row)
            item.update(
                {
                    "entry_sha256": sha256_bytes(data),
                    "extracted_size": len(data),
                    "raw_string_count": len(raw_hits),
                    "decoded_string_count": decoded_string_count,
                    "printable_string_count": len(string_dicts),
                    "keyword_hit_count": len(hits),
                    "unique_keyword_hit_count": unique_keyword_hit_count,
                    "group_scores": group_scores,
                    "decode_notes": decode_notes,
                    "sample_keyword_strings": sample_keyword_strings[:12],
                    "sample_strings": sample_strings[:12],
                }
            )
            item["rank_score"] = script_candidate_rank(item)
            inventory.append(item)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    inventory.sort(key=lambda item: (-float(item.get("rank_score") or 0), int(item.get("index") or 0)))
    write_json(out_folder / "script_candidate_inventory.json", inventory)
    write_csv(
        out_folder / "script_candidate_inventory.csv",
        [
            {
                **item,
                "group_scores": json.dumps(item.get("group_scores") or {}, sort_keys=True),
                "decode_notes": json.dumps(item.get("decode_notes") or []),
                "sample_keyword_strings": " | ".join(item.get("sample_keyword_strings") or []),
                "sample_strings": " | ".join(item.get("sample_strings") or []),
            }
            for item in inventory
        ],
        [
            "index",
            "resolved_path",
            "name",
            "offset",
            "offset_hex",
            "packed_size",
            "unpacked_size",
            "extracted_size",
            "guessed_type",
            "entry_sha256",
            "raw_string_count",
            "decoded_string_count",
            "printable_string_count",
            "keyword_hit_count",
            "unique_keyword_hit_count",
            "rank_score",
            "group_scores",
            "decode_notes",
            "sample_keyword_strings",
            "sample_strings",
            "extract_error",
            "scan_error",
        ],
    )
    write_csv(
        out_folder / "script_candidate_strings.csv",
        strings_rows,
        ["index", "source", "offset", "offset_hex", "byte_length", "encoding", "text"],
    )
    write_csv(
        out_folder / "script_candidate_keyword_hits.csv",
        keyword_rows,
        ["index", "group", "keyword", "source", "offset", "offset_hex", "encoding", "text"],
    )
    write_text(out_folder / "top_candidates.md", format_top_candidates(inventory, limit=25))
    summary = {
        "archive": str(archive),
        "archive_sha256": sha256_file(archive),
        "out_folder": str(out_folder),
        "classified_file_entries": len(classified),
        "scanned_candidate_count": scanned_count,
        "skipped_count": skipped_count,
        "inventory_count": len(inventory),
        "string_row_count": len(strings_rows),
        "keyword_hit_row_count": len(keyword_rows),
        "top_indices": [item.get("index") for item in inventory[:25]],
        "reports": {
            "inventory_json": str(out_folder / "script_candidate_inventory.json"),
            "inventory_csv": str(out_folder / "script_candidate_inventory.csv"),
            "strings_csv": str(out_folder / "script_candidate_strings.csv"),
            "keyword_hits_csv": str(out_folder / "script_candidate_keyword_hits.csv"),
            "top_candidates": str(out_folder / "top_candidates.md"),
        },
    }
    write_json(out_folder / "bulk_scan_summary.json", summary)
    return summary


def scan_rpf(
    path: Path,
    find_substrings: list[str] | None = None,
    dump_all_entries: bool = False,
    raw_search_terms: list[str] | None = None,
    classify_entries: bool = False,
) -> dict[str, Any]:
    wb = load_workbench()
    try:
        info = wb.parse_rpf6(path)
    except Exception as exc:
        return {"input": str(path), "ok": False, "error": str(exc), "unsupported_format": True}
    if info is None:
        return {"input": str(path), "ok": False, "error": "RPF6 parser returned None", "unsupported_format": True}
    entries = []
    target_map: dict[str, Any] = {}
    path_lookup = {
        str(ent.get("path") or "").replace("\\", "/").lower(): ent
        for ent in info.get("entries", [])
        if ent.get("type") == "file"
    }
    for ent in info.get("entries", []):
        if ent.get("type") != "file":
            continue
        entries.append(
            {
                "index": ent.get("index"),
                "path": ent.get("path"),
                "name": ent.get("name"),
                "offset": ent.get("offset"),
                "size_in_archive": ent.get("size_in_archive"),
                "total_size": ent.get("total_size"),
                "is_resource": ent.get("is_resource"),
                "resource_type": ent.get("resource_type"),
                "is_compressed": ent.get("is_compressed"),
            }
        )
    for target in KNOWN_RPF_TARGETS:
        full = f"root/{target}".lower()
        ent = path_lookup.get(full)
        target_map[target] = (
            {
                "present": True,
                "index": ent.get("index"),
                "path": ent.get("path"),
                "size_in_archive": ent.get("size_in_archive"),
                "total_size": ent.get("total_size"),
                "is_resource": ent.get("is_resource"),
                "resource_type": ent.get("resource_type"),
            }
            if ent
            else {"present": False}
        )
    report = {
        "input": str(path),
        "ok": True,
        "unsupported_format": False,
        "sha256": sha256_file(path),
        "entry_count": info.get("entry_count"),
        "file_count": info.get("file_count"),
        "dir_count": info.get("dir_count"),
        "encrypted": info.get("encrypted"),
        "known_targets": target_map,
        "entries": entries,
    }
    if find_substrings:
        report["find_entry_substring"] = find_entries_by_substrings(info, find_substrings)
    if dump_all_entries:
        report["all_backend_entries"] = dump_all_backend_entries(info)
    if raw_search_terms:
        report["raw_string_search"] = raw_string_search(path, raw_search_terms)
    if classify_entries:
        report["classified_entries"] = classify_rpf_entries(path, info)
    return report


def extract_rpf_entry(archive: Path, entry_path: str, out_file: Path) -> dict[str, Any]:
    wb = load_workbench()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"RPF6 parser returned None: {archive}")
    ent = find_rpf_entry(info, entry_path)
    data = wb.extract_rpf_entry(archive, ent)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(data)
    return {
        "archive": str(archive),
        "entry_path": entry_path,
        "resolved_entry_path": ent.get("path"),
        "output": str(out_file),
        "size": len(data),
        "sha256": sha256_bytes(data),
    }


def extract_rpf_entry_index(archive: Path, index: int, out_file: Path) -> dict[str, Any]:
    wb = load_workbench()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"RPF6 parser returned None: {archive}")
    ent = find_rpf_entry(info, str(index))
    data = wb.extract_rpf_entry(archive, ent)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(data)
    return {
        "archive": str(archive),
        "entry_index": index,
        "resolved_entry_path": ent.get("path"),
        "output": str(out_file),
        "size": len(data),
        "sha256": sha256_bytes(data),
        "header": classify_header(data),
        "guessed_type": guess_payload_type(str(ent.get("path") or ent.get("name") or ""), data[:64]),
    }


def scan_extracted_folder(folder: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    target_hits: list[dict[str, Any]] = []
    for file in sorted(folder.rglob("*")):
        if not file.is_file():
            continue
        rel = file.relative_to(folder).as_posix()
        name_low = file.name.lower()
        is_target = name_low in FOLDER_TARGET_NAMES or file.suffix.lower() == ".tr"
        row = {
            "relative_path": rel,
            "name": file.name,
            "size": file.stat().st_size,
            "sha256": sha256_file(file),
            "suffix": file.suffix.lower(),
            "is_target_candidate": is_target,
        }
        if is_target:
            data = file.read_bytes()[:64]
            row["header"] = classify_header(data)
            row["guessed_type"] = guess_payload_type(rel, data)
            target_hits.append(row)
        rows.append(row)
    return {
        "folder": str(folder),
        "file_count": len(rows),
        "target_hit_count": len(target_hits),
        "target_hits": target_hits,
        "files": rows,
    }


def replace_rpf_entry(archive: Path, entry_path: str, replacement_file: Path, output_archive: Path) -> dict[str, Any]:
    wb = load_workbench()
    info = wb.parse_rpf6(archive)
    if info is None:
        raise RuntimeError(f"RPF6 parser returned None: {archive}")
    ent = find_rpf_entry(info, entry_path)
    payload = replacement_file.read_bytes()
    patch_root = output_archive.parent / f"{output_archive.stem}_patch_root"
    if patch_root.exists():
        shutil.rmtree(patch_root)
    internal = str(ent.get("path") or entry_path).replace("\\", "/")
    rel = internal[5:] if internal.startswith("root/") else internal
    patch_file = patch_root / rel
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(replacement_file, patch_file)
    result = wb._codered_apply_patch_folder_to_archive_copy(archive, patch_root, output_archive=output_archive)
    validation_failures = int(result.get("blocked") or 0) + len(result.get("unmatched") or [])
    return {
        "archive": str(archive),
        "entry_path": entry_path,
        "resolved_entry_path": ent.get("path"),
        "replacement_file": str(replacement_file),
        "output_archive": str(output_archive),
        "input_sha256": sha256_file(archive),
        "output_sha256": sha256_file(output_archive),
        "input_sha1": sha1_file(archive),
        "output_sha1": sha1_file(output_archive),
        "replacement_size": len(payload),
        "replacement_sha256": sha256_bytes(payload),
        "resource_replacement": bool(ent.get("is_resource")) or payload[:4] == b"RSC\x85",
        "backend_result": json.loads(json.dumps(result, default=str)),
        "validation_failures": validation_failures,
        "warning": "Output archive is a copy. Input archive was not overwritten.",
    }


def find_rpf_entry(info: dict[str, Any], entry_ref: str) -> dict[str, Any]:
    wanted = entry_ref.replace("\\", "/").lower()
    if wanted.isdigit():
        idx = int(wanted)
        for ent in info.get("entries", []):
            if ent.get("index") == idx and ent.get("type") == "file":
                return ent
    candidates = [wanted]
    if not wanted.startswith("root/"):
        candidates.append("root/" + wanted)
    for ent in info.get("entries", []):
        if ent.get("type") != "file":
            continue
        path = str(ent.get("path") or "").replace("\\", "/").lower()
        name = str(ent.get("name") or "").lower()
        if path in candidates or name == wanted:
            return ent
    raise KeyError(entry_ref)


def command_scan_sco(args: argparse.Namespace) -> int:
    report = scan_sco(Path(args.input))
    write_json(Path(args.out), report)
    return 0 if report.get("ok") else 2


def command_strings_sco(args: argparse.Namespace) -> int:
    write_text(Path(args.out), strings_sco(Path(args.input)))
    return 0


def command_compare_sco(args: argparse.Namespace) -> int:
    write_json(Path(args.out), compare_sco(Path(args.original), Path(args.candidate)))
    return 0


def command_patch_sco_strings(args: argparse.Namespace) -> int:
    report = apply_sco_string_patches(
        Path(args.input),
        Path(args.patch),
        Path(args.out),
        bool(args.allow_padding),
    )
    manifest = Path(args.manifest) if args.manifest else Path(str(args.out) + ".manifest.json")
    write_json(manifest, report)
    print(json.dumps({"output": args.out, "manifest": str(manifest), "change_count": report["change_count"]}, indent=2))
    return 0


def command_scan_rpf(args: argparse.Namespace) -> int:
    report = scan_rpf(
        Path(args.content_rpf),
        list(args.find_entry_substring or []),
        dump_all_entries=bool(args.dump_all_entries),
        raw_search_terms=list(args.raw_string_search or []),
        classify_entries=bool(args.classify_entries),
    )
    write_json(Path(args.out), report)
    return 0 if report.get("ok") else 2


def command_extract_rpf_entry(args: argparse.Namespace) -> int:
    report = extract_rpf_entry(Path(args.content_rpf), args.entry_path, Path(args.out))
    manifest = Path(str(args.out) + ".manifest.json")
    write_json(manifest, report)
    print(json.dumps({"output": args.out, "manifest": str(manifest)}, indent=2))
    return 0


def command_extract_rpf_entry_index(args: argparse.Namespace) -> int:
    report = extract_rpf_entry_index(Path(args.content_rpf), int(args.index), Path(args.out))
    manifest = Path(str(args.out) + ".manifest.json")
    write_json(manifest, report)
    print(json.dumps({"output": args.out, "manifest": str(manifest)}, indent=2))
    return 0


def command_scan_extracted_folder(args: argparse.Namespace) -> int:
    report = scan_extracted_folder(Path(args.folder))
    write_json(Path(args.out), report)
    return 0


def command_replace_rpf_entry(args: argparse.Namespace) -> int:
    source = Path(args.content_rpf)
    output = Path(args.out)
    if source.resolve() == output.resolve():
        raise ValueError("refusing to overwrite input archive; choose a different --out path")
    report = replace_rpf_entry(source, args.entry_path, Path(args.replacement_file), output)
    manifest = Path(args.manifest) if args.manifest else Path(str(output) + ".manifest.json")
    write_json(manifest, report)
    print(json.dumps({"output": str(output), "manifest": str(manifest), "validation_failures": report["validation_failures"]}, indent=2))
    return 0 if report["validation_failures"] == 0 else 2


def command_bulk_scan_rpf_scripts(args: argparse.Namespace) -> int:
    summary = bulk_scan_rpf_scripts(Path(args.content_rpf), Path(args.out), int(args.unknown_max_size))
    print(json.dumps(summary, indent=2))
    return 0


def command_extract_candidate(args: argparse.Namespace) -> int:
    report = extract_rpf_entry_index(Path(args.content_rpf), int(args.index), Path(args.out))
    manifest = Path(str(args.out) + ".manifest.json")
    write_json(manifest, report)
    print(json.dumps({"output": args.out, "manifest": str(manifest)}, indent=2))
    return 0


def command_replace_rpf_entry_index(args: argparse.Namespace) -> int:
    source = Path(args.content_rpf)
    output = Path(args.out)
    if source.resolve() == output.resolve():
        raise ValueError("refusing to overwrite input archive; choose a different --out path")
    report = replace_rpf_entry(source, str(int(args.index)), Path(args.replacement_file), output)
    manifest = Path(args.manifest) if args.manifest else Path(str(output) + ".manifest.json")
    write_json(manifest, report)
    print(json.dumps({"output": str(output), "manifest": str(manifest), "validation_failures": report["validation_failures"]}, indent=2))
    return 0 if report["validation_failures"] == 0 else 2


def command_nochange_replace_rpf_index(args: argparse.Namespace) -> int:
    source = Path(args.content_rpf)
    output = Path(args.out)
    replacement = Path(args.same_file)
    if source.resolve() == output.resolve():
        raise ValueError("refusing to overwrite input archive; choose a different --out path")
    with tempfile.TemporaryDirectory(prefix="codered_nochange_index_") as temp:
        extracted = Path(temp) / f"entry_{int(args.index)}.bin"
        extracted_report = extract_rpf_entry_index(source, int(args.index), extracted)
        replacement_sha = sha256_file(replacement)
        if extracted_report["sha256"] != replacement_sha:
            report = {
                "archive": str(source),
                "entry_index": int(args.index),
                "same_file": str(replacement),
                "output_archive": str(output),
                "ok": False,
                "error": "replacement file SHA256 does not match extracted entry; refusing no-change replace",
                "extracted_sha256": extracted_report["sha256"],
                "replacement_sha256": replacement_sha,
            }
            manifest = Path(args.manifest) if args.manifest else Path(str(output) + ".manifest.json")
            write_json(manifest, report)
            print(json.dumps({"manifest": str(manifest), "error": report["error"]}, indent=2))
            return 2
    report = replace_rpf_entry(source, str(int(args.index)), replacement, output)
    report["nochange_precheck"] = {
        "ok": True,
        "entry_index": int(args.index),
        "same_file_sha256": sha256_file(replacement),
    }
    manifest = Path(args.manifest) if args.manifest else Path(str(output) + ".manifest.json")
    write_json(manifest, report)
    print(json.dumps({"output": str(output), "manifest": str(manifest), "validation_failures": report["validation_failures"]}, indent=2))
    return 0 if report["validation_failures"] == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code RED SCO/RPF safety probe")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan-sco", help="Inspect a .sco-like binary and write JSON")
    scan.add_argument("input")
    scan.add_argument("--out", required=True)
    scan.set_defaults(func=command_scan_sco)

    strings = sub.add_parser("strings-sco", help="Extract printable strings from a binary")
    strings.add_argument("input")
    strings.add_argument("--out", required=True)
    strings.set_defaults(func=command_strings_sco)

    compare = sub.add_parser("compare-sco", help="Compare two binaries byte-for-byte")
    compare.add_argument("original")
    compare.add_argument("candidate")
    compare.add_argument("--out", required=True)
    compare.set_defaults(func=command_compare_sco)

    patch = sub.add_parser("patch-sco-strings", help="Apply same-size string patches")
    patch.add_argument("input")
    patch.add_argument("--patch", required=True)
    patch.add_argument("--out", required=True)
    patch.add_argument("--manifest", default="")
    patch.add_argument("--allow-padding", action="store_true", help="Allow shorter replacement strings padded with NUL bytes")
    patch.set_defaults(func=command_patch_sco_strings)

    scan_rpf_cmd = sub.add_parser("scan-rpf", help="Inspect a content.rpf with existing Code RED helpers")
    scan_rpf_cmd.add_argument("content_rpf")
    scan_rpf_cmd.add_argument("--out", required=True)
    scan_rpf_cmd.add_argument(
        "--find-entry-substring",
        action="append",
        default=[],
        help="Report entries whose path/name contains this substring. May be repeated.",
    )
    scan_rpf_cmd.add_argument("--dump-all-entries", action="store_true", help="Include every backend-visible entry, including dirs/hash-only entries.")
    scan_rpf_cmd.add_argument("--raw-string-search", action="append", default=[], help="Search raw archive bytes for an ASCII/UTF-8 term. May be repeated.")
    scan_rpf_cmd.add_argument("--classify-entries", action="store_true", help="Extract/classify every file entry and report magic/SHA256 when possible.")
    scan_rpf_cmd.set_defaults(func=command_scan_rpf)

    bulk = sub.add_parser("bulk-scan-rpf-scripts", help="Extract by index in temp space and rank script-like entries by internal strings")
    bulk.add_argument("content_rpf")
    bulk.add_argument("--out", required=True)
    bulk.add_argument("--unknown-max-size", type=int, default=256 * 1024, help="Scan unknown extractable entries up to this byte size")
    bulk.set_defaults(func=command_bulk_scan_rpf_scripts)

    extract = sub.add_parser("extract-rpf-entry", help="Extract one RPF entry by path")
    extract.add_argument("content_rpf")
    extract.add_argument("entry_path")
    extract.add_argument("--out", required=True)
    extract.set_defaults(func=command_extract_rpf_entry)

    extract_index = sub.add_parser("extract-rpf-entry-index", help="Extract one RPF entry by numeric backend index")
    extract_index.add_argument("content_rpf")
    extract_index.add_argument("index", type=int)
    extract_index.add_argument("--out", required=True)
    extract_index.set_defaults(func=command_extract_rpf_entry_index)

    extract_candidate = sub.add_parser("extract-candidate", help="Alias for extracting one RPF entry by numeric candidate index")
    extract_candidate.add_argument("content_rpf")
    extract_candidate.add_argument("index", type=int)
    extract_candidate.add_argument("--out", required=True)
    extract_candidate.set_defaults(func=command_extract_candidate)

    scan_folder = sub.add_parser("scan-extracted-folder", help="Scan a MagicRDR/extracted folder for target files")
    scan_folder.add_argument("folder")
    scan_folder.add_argument("--out", required=True)
    scan_folder.set_defaults(func=command_scan_extracted_folder)

    replace = sub.add_parser("replace-rpf-entry", help="Replace one RPF entry into a copied output archive")
    replace.add_argument("content_rpf")
    replace.add_argument("entry_path")
    replace.add_argument("replacement_file")
    replace.add_argument("--out", required=True)
    replace.add_argument("--manifest", default="")
    replace.set_defaults(func=command_replace_rpf_entry)

    replace_index = sub.add_parser("replace-rpf-entry-index", help="Replace one RPF entry by numeric index into a copied output archive")
    replace_index.add_argument("content_rpf")
    replace_index.add_argument("index", type=int)
    replace_index.add_argument("replacement_file")
    replace_index.add_argument("--out", required=True)
    replace_index.add_argument("--manifest", default="")
    replace_index.set_defaults(func=command_replace_rpf_entry_index)

    nochange_index = sub.add_parser("nochange-replace-rpf-index", help="No-change replace one RPF entry by index after SHA precheck")
    nochange_index.add_argument("content_rpf")
    nochange_index.add_argument("index", type=int)
    nochange_index.add_argument("same_file")
    nochange_index.add_argument("--out", required=True)
    nochange_index.add_argument("--manifest", default="")
    nochange_index.set_defaults(func=command_nochange_replace_rpf_index)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
