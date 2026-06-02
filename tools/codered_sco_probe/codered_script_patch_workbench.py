#!/usr/bin/env python3
"""Code RED script patch workbench.

Index-first workbench for safe RDR PC content.rpf experiments:
- extract a hash-only RPF entry by index
- decode RSC85/WSC resources when possible
- apply same-size/raw patch recipes
- rebuild RSC85 entries with validation
- replace the entry into a copied RPF variant

This tool is infrastructure only. It does not contain gameplay-specific binary
patches beyond user-editable JSON recipes.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import struct
import sys
from pathlib import Path
from typing import Any


TOOL_ROOT = Path(__file__).resolve().parent
CODE_RED_ROOT = TOOL_ROOT.parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
if str(CODE_RED_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_RED_ROOT))

import codered_sco_probe as probe  # noqa: E402
from codered_wsc.resource import KeyOptions, ResourceError, open_script, repack_script  # noqa: E402


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def hex_to_bytes(value: str) -> bytes:
    return bytes.fromhex(value.replace(" ", "").replace("0x", ""))


def encode_text(value: str, encoding: str) -> bytes:
    enc = encoding.lower()
    if enc in {"utf-8", "utf8", "ascii"}:
        return value.encode("utf-8")
    if enc in {"utf-16le", "utf16le"}:
        return value.encode("utf-16le")
    raise ValueError(f"unsupported text encoding: {encoding}")


def find_all(data: bytes, needle: bytes) -> list[int]:
    if not needle:
        return []
    out: list[int] = []
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            return out
        out.append(pos)
        start = pos + max(1, len(needle))


def decode_entry(path: Path, guessed_type: str) -> tuple[bytes, str, Any | None, dict[str, Any]]:
    data = path.read_bytes()
    if guessed_type == "RSC85" or data.startswith((b"RSC\x85", b"\x85CSR")):
        try:
            resource = open_script(path, KeyOptions())
        except Exception as exc:
            return data, "raw", None, {"decode_ok": False, "error": str(exc)}
        if resource.decoded:
            return resource.decoded, "rsc85_decoded", resource, {"decode_ok": True, "resource": resource.header_dict()}
        return data, "raw", resource, {"decode_ok": False, "error": resource.decode_error or "no decoded payload"}
    if guessed_type == "ZSTD" or data.startswith(b"\x28\xB5\x2F\xFD"):
        try:
            import zstandard as zstd

            decoded = zstd.ZstdDecompressor().decompress(data)
            return decoded, "zstd_decoded", None, {"decode_ok": True, "compression": "zstandard"}
        except Exception as exc:
            return data, "raw", None, {"decode_ok": False, "error": str(exc)}
    return data, "raw", None, {"decode_ok": False, "note": "raw scan/patch lane"}


def numeric_constants(data: bytes, limit: int = 20000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, max(0, len(data) - 3), 4):
        chunk = data[offset : offset + 4]
        int_value = struct.unpack("<i", chunk)[0]
        uint_value = struct.unpack("<I", chunk)[0]
        float_value = struct.unpack("<f", chunk)[0]
        if -1000000 <= int_value <= 1000000 and int_value not in {0, -1}:
            rows.append(
                {
                    "offset": offset,
                    "offset_hex": f"0x{offset:X}",
                    "type": "int32",
                    "value": int_value,
                    "hex": probe.byte_hex(chunk),
                }
            )
        if math.isfinite(float_value) and 0.00001 <= abs(float_value) <= 1000000:
            # Keep float noise manageable by preferring common gameplay-ish values.
            rounded = round(float_value, 6)
            if rounded in {0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0, 60.0, 100.0, 120.0}:
                rows.append(
                    {
                        "offset": offset,
                        "offset_hex": f"0x{offset:X}",
                        "type": "float32",
                        "value": rounded,
                        "hex": probe.byte_hex(chunk),
                    }
                )
        if len(rows) >= limit:
            rows.append({"offset": -1, "offset_hex": "", "type": "truncated", "value": f"limit={limit}", "hex": ""})
            break
    return rows


def inspect_entry(rpf: Path, index: int, out: Path, write_decoded: bool = True) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    entry_path = out / f"entry_{index}.bin"
    extract_report = probe.extract_rpf_entry_index(rpf, index, entry_path)
    raw = entry_path.read_bytes()
    guessed_type = probe.guess_payload_type(str(extract_report.get("resolved_entry_path") or index), raw[:64])
    decoded, patch_lane, _resource, decode_report = decode_entry(entry_path, guessed_type)
    raw_strings = [hit.to_dict() | {"source": "raw"} for hit in probe.collect_strings(raw)]
    decoded_strings = [hit.to_dict() | {"source": patch_lane} for hit in probe.collect_strings(decoded)] if decoded != raw else []
    constants = numeric_constants(decoded)
    write_json(out / "entry_extract_manifest.json", extract_report)
    write_json(out / "inspect_report.json", {
        "rpf": str(rpf),
        "index": index,
        "entry_file": str(entry_path),
        "entry_sha256": probe.sha256_bytes(raw),
        "entry_size": len(raw),
        "guessed_type": guessed_type,
        "patch_lane": patch_lane,
        "header": probe.classify_header(raw),
        "decode": decode_report,
        "raw_string_count": len(raw_strings),
        "decoded_string_count": len(decoded_strings),
        "numeric_constant_count": len(constants),
    })
    write_csv(out / "strings.csv", raw_strings + decoded_strings, ["source", "offset", "offset_hex", "byte_length", "encoding", "text"])
    write_csv(out / "numeric_constants.csv", constants, ["offset", "offset_hex", "type", "value", "hex"])
    if write_decoded and decoded != raw:
        (out / "decoded_payload.bin").write_bytes(decoded)
    write_text(
        out / "inspect_report.md",
        "\n".join(
            [
                f"# Inspect Entry {index}",
                "",
                f"- RPF: `{rpf}`",
                f"- Extracted: `{entry_path}`",
                f"- Type: `{guessed_type}`",
                f"- Patch lane: `{patch_lane}`",
                f"- Size: `{len(raw)}`",
                f"- SHA256: `{probe.sha256_bytes(raw)}`",
                f"- Decode OK: `{decode_report.get('decode_ok')}`",
                f"- Raw strings: `{len(raw_strings)}`",
                f"- Decoded strings: `{len(decoded_strings)}`",
                f"- Numeric constants: `{len(constants)}`",
            ]
        )
        + "\n",
    )
    return {
        "out": str(out),
        "entry": str(entry_path),
        "guessed_type": guessed_type,
        "patch_lane": patch_lane,
        "decode_ok": bool(decode_report.get("decode_ok")),
    }


def add_change(changes: list[dict[str, Any]], patch_index: int, patch_type: str, offset: int, old: bytes, new: bytes, note: str = "") -> None:
    changes.append(
        {
            "patch_index": patch_index,
            "type": patch_type,
            "offset": offset,
            "offset_hex": f"0x{offset:X}",
            "length": len(old),
            "old_hex": probe.byte_hex(old),
            "new_hex": probe.byte_hex(new),
            "old_text": old.decode("utf-8", errors="replace"),
            "new_text": new.decode("utf-8", errors="replace"),
            "note": note,
        }
    )


def apply_recipe_to_payload(payload: bytes, recipe: dict[str, Any], allow_many: bool = False) -> tuple[bytes, dict[str, Any]]:
    data = bytearray(payload)
    changes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    patches = recipe.get("patches") or []
    for idx, patch in enumerate(patches):
        patch_type = str(patch.get("type", ""))
        required = bool(patch.get("required", False))
        report_only = bool(patch.get("report_only", False) or patch_type == "native_call_report_only")
        try:
            if patch_type in {"string_replace_same_size", "string_replace_padded"}:
                encoding = str(patch.get("encoding", "utf-8"))
                old = encode_text(str(patch["old"]), encoding)
                new_raw = encode_text(str(patch["new"]), encoding)
                if patch_type == "string_replace_same_size" and len(old) != len(new_raw):
                    raise ValueError(f"same-size string patch length mismatch old={len(old)} new={len(new_raw)}")
                if patch_type == "string_replace_padded":
                    if len(new_raw) > len(old):
                        raise ValueError("padded string replacement is longer than old string")
                    pad = b"\x00" * (len(old) - len(new_raw))
                    new_raw = new_raw + pad
                offsets = find_all(bytes(data), old)
                max_hits = patch.get("max_hits")
                if not offsets:
                    skipped.append({"patch_index": idx, "type": patch_type, "reason": "old string not found", "old": patch.get("old")})
                    if required:
                        raise ValueError("required string was not found")
                    continue
                if max_hits is not None and len(offsets) > int(max_hits) and not report_only:
                    raise ValueError(f"hit count {len(offsets)} exceeds max_hits={max_hits}")
                if max_hits is None and len(offsets) > 1 and not allow_many and not patch.get("allow_many") and not report_only:
                    raise ValueError(f"hit count {len(offsets)} exceeds default one-hit safety gate")
                for offset in offsets:
                    old_bytes = bytes(data[offset : offset + len(old)])
                    if not report_only:
                        data[offset : offset + len(old)] = new_raw
                        add_change(changes, idx, patch_type, offset, old_bytes, new_raw, str(patch.get("note", "")))
                reports.append({"patch_index": idx, "type": patch_type, "hit_count": len(offsets), "report_only": report_only})
            elif patch_type in {"float_replace", "int_replace"}:
                if patch_type == "float_replace":
                    old = struct.pack("<f", float(patch["old_float"]))
                    new = struct.pack("<f", float(patch["new_float"]))
                else:
                    old = struct.pack("<i", int(patch["old_int"]))
                    new = struct.pack("<i", int(patch["new_int"]))
                offsets = find_all(bytes(data), old)
                max_hits = patch.get("max_hits")
                if not offsets:
                    skipped.append({"patch_index": idx, "type": patch_type, "reason": "constant bytes not found"})
                    if required:
                        raise ValueError("required constant was not found")
                    continue
                if max_hits is not None and len(offsets) > int(max_hits) and not report_only:
                    raise ValueError(f"hit count {len(offsets)} exceeds max_hits={max_hits}")
                if max_hits is None and len(offsets) > 1 and not allow_many and not patch.get("allow_many") and not report_only:
                    raise ValueError(f"hit count {len(offsets)} exceeds default one-hit safety gate")
                for offset in offsets:
                    if not report_only:
                        old_bytes = bytes(data[offset : offset + 4])
                        data[offset : offset + 4] = new
                        add_change(changes, idx, patch_type, offset, old_bytes, new, str(patch.get("note", "")))
                reports.append({"patch_index": idx, "type": patch_type, "hit_count": len(offsets), "report_only": report_only})
            elif patch_type == "byte_patch":
                offset = int(patch["offset"], 0) if isinstance(patch["offset"], str) else int(patch["offset"])
                old = hex_to_bytes(str(patch["old_hex"]))
                new = hex_to_bytes(str(patch["new_hex"]))
                if len(old) != len(new):
                    raise ValueError("byte_patch must preserve length")
                existing = bytes(data[offset : offset + len(old)])
                if existing != old:
                    raise ValueError(f"old bytes do not match at 0x{offset:X}")
                if not report_only:
                    data[offset : offset + len(old)] = new
                    add_change(changes, idx, patch_type, offset, old, new, str(patch.get("note", "")))
                reports.append({"patch_index": idx, "type": patch_type, "hit_count": 1, "report_only": report_only})
            elif patch_type == "guard_decor_remove_by_string":
                real = encode_text(str(patch["real_key"]), str(patch.get("encoding", "utf-8")))
                dummy = encode_text(str(patch["dummy_key_same_length"]), str(patch.get("encoding", "utf-8")))
                if len(real) != len(dummy):
                    raise ValueError("dummy_key_same_length is not the same length as real_key")
                offsets = find_all(bytes(data), real)
                if not offsets:
                    skipped.append({"patch_index": idx, "type": patch_type, "reason": "real key not found", "key": patch.get("real_key")})
                    if required:
                        raise ValueError("required guard key was not found")
                    continue
                max_hits = patch.get("max_hits", 1)
                if len(offsets) > int(max_hits) and not report_only:
                    raise ValueError(f"hit count {len(offsets)} exceeds max_hits={max_hits}")
                for offset in offsets:
                    if not report_only:
                        old_bytes = bytes(data[offset : offset + len(real)])
                        data[offset : offset + len(real)] = dummy
                        add_change(changes, idx, patch_type, offset, old_bytes, dummy, str(patch.get("note", "")))
                reports.append({"patch_index": idx, "type": patch_type, "hit_count": len(offsets), "report_only": report_only})
            elif patch_type == "native_call_report_only":
                found: list[dict[str, Any]] = []
                for term in patch.get("search_strings") or []:
                    offsets = find_all(bytes(data), encode_text(str(term), str(patch.get("encoding", "utf-8"))))
                    found.append({"term": term, "hit_count": len(offsets), "offsets": [f"0x{o:X}" for o in offsets[:20]]})
                reports.append({"patch_index": idx, "type": patch_type, "report_only": True, "found": found})
            else:
                raise ValueError(f"unsupported patch type: {patch_type}")
        except Exception as exc:
            blocked.append({"patch_index": idx, "type": patch_type, "error": str(exc)})
            if required:
                raise
    return bytes(data), {
        "change_count": len(changes),
        "changes": changes,
        "skipped": skipped,
        "blocked": blocked,
        "reports": reports,
        "same_size": len(data) == len(payload),
        "original_sha256": probe.sha256_bytes(payload),
        "patched_payload_sha256": probe.sha256_bytes(bytes(data)),
    }


def apply_patch_recipe(rpf: Path, index: int, recipe_path: Path, out: Path, allow_many: bool = False) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    entry_path = out / f"entry_{index}_original.bin"
    extract_report = probe.extract_rpf_entry_index(rpf, index, entry_path)
    raw = entry_path.read_bytes()
    guessed_type = probe.guess_payload_type(str(extract_report.get("resolved_entry_path") or index), raw[:64])
    decoded, patch_lane, resource, decode_report = decode_entry(entry_path, guessed_type)
    recipe = load_json(recipe_path)
    (out / "decoded_original.bin").write_bytes(decoded)
    patched_payload, patch_report = apply_recipe_to_payload(decoded, recipe, allow_many=allow_many)
    (out / "decoded_patched.bin").write_bytes(patched_payload)
    if patch_lane == "rsc85_decoded":
        if resource is None:
            raise RuntimeError("internal error: decoded RSC85 has no resource handle")
        rebuilt, rebuild_report = repack_script(resource, patched_payload, allow_growth=bool(recipe.get("allow_rsc85_growth", False)))
        patched_entry = rebuilt
        patched_entry_path = out / f"entry_{index}_patched.bin"
        patched_entry_path.write_bytes(patched_entry)
        redecode, _, _, redecode_report = decode_entry(patched_entry_path, "RSC85")
        validation = {
            "rebuild": rebuild_report,
            "redecode_ok": redecode == patched_payload,
            "redecode_report": redecode_report,
        }
    else:
        if len(patched_payload) != len(raw):
            raise ValueError("raw/SCO patch lane cannot change file length")
        patched_entry_path = out / f"entry_{index}_patched.bin"
        patched_entry_path.write_bytes(patched_payload)
        validation = {"raw_same_size": True, "redecode_ok": True}
    compare = probe.compare_bytes(raw if patch_lane == "raw" else decoded, patched_payload)
    manifest = {
        "rpf": str(rpf),
        "index": index,
        "recipe": str(recipe_path),
        "guessed_type": guessed_type,
        "patch_lane": patch_lane,
        "extract": extract_report,
        "decode": decode_report,
        "patched_entry": str(patched_entry_path),
        "patched_entry_sha256": probe.sha256_file(patched_entry_path),
        "patched_entry_size": patched_entry_path.stat().st_size,
        "entry_size_changed": patched_entry_path.stat().st_size != len(raw),
        "original_entry_size": len(raw),
        "patch": patch_report,
        "compare": compare,
        "validation": validation,
        "warnings": [
            "RPF was not modified by apply-patch-recipe. Use build-rpf-variant after reviewing this manifest.",
            "Readable strings are anchors, not proof of bytecode behavior.",
        ],
    }
    write_json(out / "patch_manifest.json", manifest)
    write_json(out / "compare_report.json", compare)
    write_csv(out / "changed_offsets.csv", patch_report["changes"], ["patch_index", "type", "offset", "offset_hex", "length", "old_hex", "new_hex", "old_text", "new_text", "note"])
    write_text(
        out / "patch_report.md",
        "\n".join(
            [
                f"# Patch Entry {index}",
                "",
                f"- Recipe: `{recipe_path}`",
                f"- Type: `{guessed_type}`",
                f"- Patch lane: `{patch_lane}`",
                f"- Changes: `{patch_report['change_count']}`",
                f"- Blocked: `{len(patch_report['blocked'])}`",
                f"- Skipped: `{len(patch_report['skipped'])}`",
                f"- Entry size changed: `{manifest['entry_size_changed']}`",
                f"- Patched entry: `{patched_entry_path}`",
                f"- Re-decode OK: `{validation.get('redecode_ok')}`",
            ]
        )
        + "\n",
    )
    return manifest


def make_recipe_template(index: int, out: Path, name: str = "") -> dict[str, Any]:
    recipe = {
        "name": name or f"entry_{index}_recipe",
        "target": {"index": index},
        "allow_rsc85_growth": False,
        "patches": [
            {"type": "string_replace_same_size", "old": "OLD_TEXT", "new": "NEW_TEXT", "encoding": "utf-8", "max_hits": 1, "required": False},
            {"type": "byte_patch", "offset": "0x0", "old_hex": "00", "new_hex": "00", "required": False},
            {"type": "native_call_report_only", "search_strings": ["SET_PHYSINST_FROZEN", "SUSPEND_MOVER", "SET_MOVER_FROZEN"]},
        ],
    }
    write_json(out, recipe)
    return recipe


def direct_replace_rpf_entry_index(rpf: Path, index: int, patched_entry: Path, out_rpf: Path) -> dict[str, Any]:
    wb = probe.load_workbench()
    info = wb.parse_rpf6(rpf)
    if info is None:
        raise RuntimeError(f"RPF6 parser returned None: {rpf}")
    ent = probe.find_rpf_entry(info, str(index))
    payload = patched_entry.read_bytes()
    out_rpf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rpf, out_rpf)
    copied = wb.parse_rpf6(out_rpf)
    if copied is None:
        raise RuntimeError(f"copied RPF could not be parsed: {out_rpf}")
    live = probe.find_rpf_entry(copied, str(index))
    slot_size = int(live.get("size_in_archive") or 0)
    original_offset = int(live.get("offset") or 0)
    relocated = len(payload) > slot_size
    if relocated:
        new_offset = wb._codered_append_archive_payload(out_rpf, payload)
        wb._codered_update_rpf6_entry_metadata(
            out_rpf,
            copied,
            live,
            new_size_in_archive=len(payload),
            new_total_size=live.get("total_size"),
            new_offset=new_offset,
        )
    else:
        with out_rpf.open("r+b") as f:
            f.seek(original_offset)
            f.write(payload)
            if len(payload) < slot_size:
                f.write(b"\x00" * (slot_size - len(payload)))
        wb._codered_update_rpf6_entry_metadata(
            out_rpf,
            copied,
            live,
            new_size_in_archive=len(payload),
            new_total_size=live.get("total_size"),
        )
        new_offset = original_offset
    reparsed = wb.parse_rpf6(out_rpf)
    if reparsed is None:
        raise RuntimeError("variant RPF failed to reparse after replacement")
    updated = probe.find_rpf_entry(reparsed, str(index))
    readback = wb.extract_rpf_entry(out_rpf, updated)
    ok = readback == payload
    return {
        "archive": str(rpf),
        "entry_index": index,
        "resolved_entry_path": ent.get("path"),
        "patched_entry": str(patched_entry),
        "output_archive": str(out_rpf),
        "input_sha256": probe.sha256_file(rpf),
        "output_sha256": probe.sha256_file(out_rpf),
        "replacement_sha256": probe.sha256_bytes(payload),
        "replacement_size": len(payload),
        "old_size_in_archive": slot_size,
        "size_delta": len(payload) - slot_size,
        "old_offset": original_offset,
        "new_offset": int(updated.get("offset") or new_offset),
        "relocated": relocated,
        "readback_sha256": probe.sha256_bytes(readback),
        "readback_matches_replacement": ok,
        "validation_failures": 0 if ok else 1,
        "warning": "Output archive is a copy. Input archive was not overwritten. Direct index replacement assumes patched_entry is already archive-ready bytes.",
    }


def build_rpf_variant(rpf: Path, index: int, patched_entry: Path, out_rpf: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    if rpf.resolve() == out_rpf.resolve():
        raise ValueError("refusing to overwrite original RPF")
    if "build" not in [part.lower() for part in out_rpf.resolve().parts]:
        raise ValueError("RPF variants must be written under a build directory")
    report = direct_replace_rpf_entry_index(rpf, index, patched_entry, out_rpf)
    manifest = manifest_path or Path(str(out_rpf) + ".manifest.json")
    write_json(manifest, report)
    return report


def command_inspect_entry(args: argparse.Namespace) -> int:
    report = inspect_entry(Path(args.rpf), int(args.index), Path(args.out), write_decoded=not args.no_decoded_payload)
    print(json.dumps(report, indent=2))
    return 0


def command_make_patch_recipe(args: argparse.Namespace) -> int:
    recipe = make_recipe_template(int(args.index), Path(args.out), args.name)
    print(json.dumps({"output": args.out, "patch_count": len(recipe["patches"])}, indent=2))
    return 0


def command_apply_patch_recipe(args: argparse.Namespace) -> int:
    manifest = apply_patch_recipe(Path(args.rpf), int(args.index), Path(args.recipe), Path(args.out), allow_many=bool(args.allow_many))
    print(json.dumps({"patched_entry": manifest["patched_entry"], "change_count": manifest["patch"]["change_count"], "redecode_ok": manifest["validation"].get("redecode_ok")}, indent=2))
    return 0 if manifest["validation"].get("redecode_ok") else 2


def command_build_rpf_variant(args: argparse.Namespace) -> int:
    report = build_rpf_variant(Path(args.rpf), int(args.index), Path(args.patched_entry), Path(args.out), Path(args.manifest) if args.manifest else None)
    print(json.dumps({"output": args.out, "validation_failures": report.get("validation_failures"), "manifest": args.manifest or str(args.out) + ".manifest.json"}, indent=2))
    return 0 if report.get("validation_failures") == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code RED script patch workbench")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect-entry", help="Extract/decode/scan one RPF entry by index")
    inspect.add_argument("--rpf", required=True)
    inspect.add_argument("--index", required=True, type=int)
    inspect.add_argument("--out", required=True)
    inspect.add_argument("--no-decoded-payload", action="store_true")
    inspect.set_defaults(func=command_inspect_entry)

    make = sub.add_parser("make-patch-recipe", help="Create a starter JSON recipe")
    make.add_argument("--index", required=True, type=int)
    make.add_argument("--out", required=True)
    make.add_argument("--name", default="")
    make.set_defaults(func=command_make_patch_recipe)

    apply = sub.add_parser("apply-patch-recipe", help="Patch extracted/decoded entry and rebuild when possible")
    apply.add_argument("--rpf", required=True)
    apply.add_argument("--index", required=True, type=int)
    apply.add_argument("--recipe", required=True)
    apply.add_argument("--out", required=True)
    apply.add_argument("--allow-many", action="store_true", help="Allow multi-hit int/float/string patches without per-patch allow_many")
    apply.set_defaults(func=command_apply_patch_recipe)

    build = sub.add_parser("build-rpf-variant", help="Replace a patched entry by index into a copied RPF")
    build.add_argument("--rpf", required=True)
    build.add_argument("--index", required=True, type=int)
    build.add_argument("--patched-entry", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--manifest", default="")
    build.set_defaults(func=command_build_rpf_variant)

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
