#!/usr/bin/env python3
"""Build cloned RPF variants for converted XENON->PC WSC runtime probing.

This pass is intentionally archive-only. It does not touch the live game
content.rpf, RDR.exe, ASI files, trainer files, PSN CSC/RSC86 files, or script
bytecode inside the converted MP WSC payloads.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PASS5_BASE = ROOT / "build" / "mp_content_restore_pass5" / "content_mp_restore_pass5_access_trainer_sectors.rpf"
CONVERTED_WSC_TREE = ROOT / "build" / "mp_script_conversion_probe" / "import_ready_xsc_converted_wsc"
BUILD_ROOT = ROOT / "build" / "mp_converted_runtime_probe_pass1"
REPORT_ROOT = ROOT / "reports" / "mp_converted_runtime_probe_pass1"
OVERLAY_TOOL = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
RPF_UTILS_TOOL = ROOT / "tools" / "codered_rpf_utils.py"
RDR_EXE = ROOT.parent / "RDR.exe"

MAIN_ARCHIVES = [
    "root/content/release64/main.wsc",
    "root/content/release64/main_z.wsc",
]
PRESSSTART_D_CANDIDATES = [
    ROOT / "build" / "mp_converted_runtime_probe_inputs" / "pressstart_D_full_force" / "boot.sc.xml",
    ROOT / "build" / "mp_converted_runtime_probe_inputs" / "pressstart_D_full_force" / "pressstart.wsc",
    ROOT / "build" / "pressstart_D_full_force",
]
OPTIONAL_XML_BYPASS_CANDIDATES = [
    # Explicitly conservative: only savegame/savegame2/netstats candidate names
    # are accepted here. LAN/PlayMpConf auth experiments are not included in D.
    ROOT / "build" / "mp_converted_runtime_probe_inputs" / "known_safe_savegame_netstats_bypass",
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def path_to_archive_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if not rel.startswith("content/"):
        raise ValueError(f"Import tree file is outside content/: {path}")
    return "root/" + rel


def collect_converted_wsc_rows() -> list[dict[str, Any]]:
    if not CONVERTED_WSC_TREE.exists():
        raise FileNotFoundError(CONVERTED_WSC_TREE)
    rows: list[dict[str, Any]] = []
    for path in sorted(CONVERTED_WSC_TREE.rglob("*.wsc"), key=lambda p: str(p).lower()):
        data = path.read_bytes()
        if data[:4] != b"RSC\x85":
            raise RuntimeError(f"Converted WSC is not a PC RSC85 resource: {path}")
        rows.append(
            {
                "layer": "converted_xenon_pc_wsc",
                "source_path": str(path),
                "archive_path": path_to_archive_path(path, CONVERTED_WSC_TREE),
                "payload": data,
                "expected_sha1": sha1_bytes(data),
                "expected_size": len(data),
                "resource_entry": True,
                "operation": "replace",
                "note": "XENON XSC -> LZX decoded -> PC RSC85 WSC rewrap; runtime compatibility unproven",
            }
        )
    return rows


def discover_pressstart_d_rows() -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    for candidate in PRESSSTART_D_CANDIDATES:
        if not candidate.exists():
            continue
        files = [candidate] if candidate.is_file() else [p for p in sorted(candidate.rglob("*")) if p.is_file()]
        rows: list[dict[str, Any]] = []
        for path in files:
            low = path.name.lower()
            if low == "boot.sc.xml":
                archive_path = "root/content/ui/boot.sc.xml"
            elif low == "pressstart.wsc":
                archive_path = "root/content/release64/pressstart.wsc"
            else:
                warnings.append(f"ignored unrecognized pressstart_D file: {path}")
                continue
            data = path.read_bytes()
            rows.append(
                {
                    "layer": "pressstart_D_full_force",
                    "source_path": str(path),
                    "archive_path": archive_path,
                    "payload": data,
                    "expected_sha1": sha1_bytes(data),
                    "expected_size": len(data),
                    "resource_entry": data[:4] == b"RSC\x85",
                    "operation": "replace",
                    "note": "pressstart_D_full_force artifact discovered and applied",
                }
            )
        if rows:
            return rows, warnings
    warnings.append("pressstart_D_full_force artifact was not found; B/C/D record this as unavailable and do not synthesize a fake patch")
    return [], warnings


def archive_path_from_optional_xml(path: Path, base: Path) -> str | None:
    name = path.name
    lower_name = name.lower()
    if "savegame2" in lower_name:
        return "root/content/ui/savegame2.sc.xml"
    if "savegame" in lower_name and "pausemenu" in lower_name:
        return "root/content/ui/pausemenu/savegame.sc.xml"
    if "savegame" in lower_name:
        return "root/content/ui/savegame.sc.xml"
    if "netstats_main" in lower_name:
        return "root/content/ui/pausemenu/netstats/main.sc.xml"
    if "netstats_errormsgrecovery" in lower_name:
        return "root/content/ui/pausemenu/netstats/errormsgrecovery.sc.xml"
    if "netstats_errormsg" in lower_name:
        return "root/content/ui/pausemenu/netstats/errormsg.sc.xml"
    if "netstats_boards" in lower_name:
        return "root/content/ui/pausemenu/netstats/boards.sc.xml"
    if "netstats_prompts" in lower_name:
        return "root/content/ui/pausemenu/netstats/prompts.sc.xml"
    try:
        rel = path.relative_to(base).as_posix()
    except ValueError:
        rel = path.name
    if rel.startswith("root/content/ui/") and ("savegame" in rel.lower() or "netstats" in rel.lower()):
        return rel
    return None


def discover_optional_xml_bypass_rows() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for folder in OPTIONAL_XML_BYPASS_CANDIDATES:
        if not folder.exists():
            continue
        files = [folder] if folder.is_file() else [p for p in sorted(folder.rglob("*")) if p.is_file()]
        for path in files:
            if path.suffix.lower() not in {".xml", ".scxml"} and not path.name.lower().endswith(".sc.xml"):
                continue
            archive_path = archive_path_from_optional_xml(path, folder)
            if archive_path is None:
                warnings.append(f"ignored optional XML bypass outside savegame/netstats scope: {path}")
                continue
            data = path.read_bytes()
            rows.append(
                {
                    "layer": "known_safe_savegame_netstats_xml_bypass",
                    "source_path": str(path),
                    "archive_path": archive_path,
                    "payload": data,
                    "expected_sha1": sha1_bytes(data),
                    "expected_size": len(data),
                    "resource_entry": False,
                    "operation": "replace",
                    "note": "explicit optional savegame/savegame2/netstats XML bypass candidate",
                }
            )
    if not rows:
        warnings.append("no explicit known-safe savegame/savegame2/netstats XML bypass candidates were found; D does not add an auth or PlayMpConf experiment")
    return rows, warnings


def patch_wsc_main_payload(data: bytes, source_label: str) -> tuple[bytes, dict[str, Any]]:
    from codered_wsc.resource import KeyOptions, open_script_from_bytes, open_script, repack_script

    temp = BUILD_ROOT / "_tmp_extract_for_patch" / source_label.replace("/", "__")
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(data)
    resource = open_script(temp, KeyOptions(rdr_exe=str(RDR_EXE)))
    find = b"no_autosave"
    replace = b"xmlsave" + (b"\x00" * (len(find) - len(b"xmlsave")))
    count = resource.decoded.count(find)
    if count == 0:
        return data, {
            "source_label": source_label,
            "status": "no_match",
            "find": find.decode("ascii"),
            "replace": "xmlsave+NUL padding",
            "count": 0,
            "validate_ok": True,
        }
    patched_decoded = resource.decoded.replace(find, replace)
    output, repack_report = repack_script(resource, patched_decoded, allow_growth=True)
    reopened = open_script_from_bytes(output, temp, resource.key or b"", originally_xsc=False)
    validate_ok = reopened.decoded == patched_decoded
    if not validate_ok:
        raise RuntimeError(f"patched WSC did not reopen cleanly: {source_label}")
    return output, {
        "source_label": source_label,
        "status": "patched",
        "find": find.decode("ascii"),
        "replace": "xmlsave+NUL padding",
        "count": count,
        "validate_ok": validate_ok,
        "repack": repack_report,
    }


def extract_entry(utils, wb, archive: Path, archive_path: str) -> tuple[bytes, dict[str, Any]]:
    info = utils.parse_archive(archive)
    entry = utils.find_entry(info, archive_path)
    data = utils.extract_entry_payload(wb, archive, entry)
    return data, entry


def collect_main_patch_rows(base_rpf: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    utils = load_module(RPF_UTILS_TOOL, "codered_rpf_utils_probe")
    wb = utils.load_backend()
    rows: list[dict[str, Any]] = []
    patch_reports: list[dict[str, Any]] = []
    for archive_path in MAIN_ARCHIVES:
        original, _entry = extract_entry(utils, wb, base_rpf, archive_path)
        patched, report = patch_wsc_main_payload(original, archive_path)
        patch_reports.append(report | {"archive_path": archive_path})
        rows.append(
            {
                "layer": "main_no_autosave_to_xmlsave",
                "source_path": f"{base_rpf}:{archive_path}",
                "archive_path": archive_path,
                "payload": patched,
                "expected_sha1": sha1_bytes(patched),
                "expected_size": len(patched),
                "resource_entry": True,
                "operation": "replace",
                "note": report["status"],
            }
        )
    return rows, patch_reports


def ensure_resource_node(overlay, wb, node, payload: bytes) -> None:
    if payload[:4] != b"RSC\x85":
        raise RuntimeError("resource node payload is not RSC85")
    node.resource_replace = True
    node.resource_flag1, node.resource_flag2 = struct.unpack_from("<2I", payload, 8)


def pack_toc_with_added_resources(overlay, wb, nodes: list[Any], encrypted: bool) -> bytes:
    toc = bytearray()
    for node in nodes:
        if node.kind == "dir":
            toc.extend(struct.pack(">5I", node.name_off, 0, 0x80000000 | node.start, node.count, 0))
            continue
        if node.operation in {"add", "replace"}:
            b = node.stored_size & 0x0FFFFFFF
            if node.resource_replace:
                c = ((node.new_offset // 8) & 0x7FFFFF00) | 2
                d = node.resource_flag1
                e = node.resource_flag2
            else:
                c = (node.new_offset // 8) & 0x7FFFFFFF
                compression_bit = 0x40000000 if node.force_compressed else 0
                d = compression_bit | (node.decoded_size & 0x3FFFFFFF)
                e = 0
        else:
            ent = node.original or {}
            b = int(ent.get("size_in_archive") or 0) & 0x0FFFFFFF
            if ent.get("is_resource"):
                c = ((node.new_offset // 8) & 0x7FFFFF00) | (wb._rpf_resource_type(int(ent["offset_raw"])) & 0xFF)
            else:
                c = (node.new_offset // 8) & 0x7FFFFFFF
            d = int(ent.get("flag1") or 0)
            e = int(ent.get("flag2") or 0)
        toc.extend(struct.pack(">5I", node.name_off, b, c, d, e))
    padded_size = overlay.align(len(toc), 16)
    toc.extend(b"\x00" * (padded_size - len(toc)))
    return wb._codered_rpf6_encrypt(bytes(toc)) if encrypted else bytes(toc)


def build_overlay_rpf(source_rpf: Path, output_rpf: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    overlay = load_module(OVERLAY_TOOL, "codered_overlay_probe")
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source_rpf)
    if info is None:
        raise RuntimeError(f"source RPF did not parse: {source_rpf}")
    root = overlay.build_existing_tree(info)
    operations: list[dict[str, Any]] = []
    for row in rows:
        action, node = overlay.add_or_replace_file(
            wb,
            root,
            row["archive_path"],
            row["payload"],
            row.get("operation", "replace"),
            allow_resource_replace=bool(row.get("resource_entry")),
        )
        if row.get("resource_entry"):
            ensure_resource_node(overlay, wb, node, row["payload"])
        operations.append(
            {
                "archive_path": row["archive_path"],
                "source_path": row["source_path"],
                "layer": row["layer"],
                "action": action,
                "resource_entry": bool(row.get("resource_entry")),
                "expected_size": row["expected_size"],
                "expected_sha1": row["expected_sha1"],
                "note": row.get("note", ""),
            }
        )
    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    payload_floor = min(int(entry["offset"]) for entry in info["entries"] if entry.get("type") == "file")
    if 16 + toc_size > payload_floor:
        raise RuntimeError(f"new TOC would overlap payload: toc_end={16 + toc_size} payload_floor={payload_floor}")
    output_bytes = bytearray(source_rpf.read_bytes())
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = overlay.align(len(output_bytes), overlay.payload_alignment(node))
        if node.new_offset > len(output_bytes):
            output_bytes.extend(b"\x00" * (node.new_offset - len(output_bytes)))
        output_bytes.extend(node.source_bytes or b"")
        padded = overlay.align(len(output_bytes), 8)
        if padded > len(output_bytes):
            output_bytes.extend(b"\x00" * (padded - len(output_bytes)))
    toc = pack_toc_with_added_resources(overlay, wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", output_bytes, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    output_bytes[16 : 16 + len(toc)] = toc
    output_rpf.parent.mkdir(parents=True, exist_ok=True)
    output_rpf.write_bytes(output_bytes)
    parsed = wb.parse_rpf6(output_rpf)
    if parsed is None:
        raise RuntimeError(f"output RPF did not parse: {output_rpf}")
    return {
        "source_rpf": str(source_rpf),
        "output_rpf": str(output_rpf),
        "entry_count_before": info.get("entry_count"),
        "entry_count_after": parsed.get("entry_count"),
        "file_count_after": parsed.get("file_count"),
        "operations": operations,
    }


def verify_rows(output_rpf: Path, rows: list[dict[str, Any]], variant: str) -> list[dict[str, Any]]:
    utils = load_module(RPF_UTILS_TOOL, f"codered_rpf_utils_verify_{variant}")
    wb = utils.load_backend()
    info = utils.parse_archive(output_rpf)
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            entry = utils.find_entry(info, row["archive_path"])
            data = utils.extract_entry_payload(wb, output_rpf, entry)
            actual_sha1 = sha1_bytes(data)
            out.append(
                {
                    "variant": variant,
                    "archive_path": row["archive_path"],
                    "layer": row["layer"],
                    "entry_index": entry.get("index"),
                    "is_resource": entry.get("is_resource"),
                    "resource_type": entry.get("resource_type"),
                    "expected_size": row["expected_size"],
                    "actual_size": len(data),
                    "expected_sha1": row["expected_sha1"],
                    "actual_sha1": actual_sha1,
                    "status": "exact_match" if actual_sha1 == row["expected_sha1"] else "mismatch",
                    "note": row.get("note", ""),
                }
            )
        except Exception as exc:
            out.append(
                {
                    "variant": variant,
                    "archive_path": row["archive_path"],
                    "layer": row["layer"],
                    "entry_index": "",
                    "is_resource": "",
                    "resource_type": "",
                    "expected_size": row["expected_size"],
                    "actual_size": "",
                    "expected_sha1": row["expected_sha1"],
                    "actual_sha1": "",
                    "status": "error",
                    "note": str(exc),
                }
            )
    return out


def inventory_summary(archive: Path) -> dict[str, Any]:
    utils = load_module(RPF_UTILS_TOOL, f"codered_rpf_utils_inv_{archive.stem}")
    info = utils.parse_archive(archive)
    paths = [str(entry.get("path") or "").replace("\\", "/").lower() for entry in info.get("entries", []) if entry.get("type") == "file"]
    return {
        "archive": str(archive),
        "sha1": sha1_file(archive),
        "entry_count": info.get("entry_count"),
        "file_count": info.get("file_count"),
        "converted_mp_wsc_count": sum(1 for path in paths if "/multiplayer/" in path and path.endswith(".wsc")),
        "converted_release64_core_present": {
            "freemode": "root/content/release64/multiplayer/freemode/freemode.wsc" in paths,
            "multiplayer_system_thread": "root/content/release64/multiplayer/multiplayer_system_thread.wsc" in paths,
            "pr_multiplayer": "root/content/release64/multiplayer/pr_multiplayer.wsc" in paths,
            "mp_actorpicker": "root/content/release64/multiplayer/support/mp_actorpicker.wsc" in paths,
        },
    }


def write_reports(summary: dict[str, Any], manifests: list[dict[str, Any]], verifications: list[dict[str, Any]], warnings: list[str], main_patch_reports: list[dict[str, Any]]) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_ROOT / "mp_converted_runtime_probe_pass1_summary.json", summary)
    write_csv(REPORT_ROOT / "mp_converted_runtime_probe_pass1_manifest.csv", manifests)
    write_csv(REPORT_ROOT / "mp_converted_runtime_probe_pass1_readback.csv", verifications)
    write_json(REPORT_ROOT / "mp_converted_runtime_probe_pass1_main_patch_report.json", main_patch_reports)

    matrix = [
        "# MP Converted Runtime Probe Pass 1 Test Matrix",
        "",
        "Use one cloned RPF at a time. Restore the known-good content.rpf between tests.",
        "",
        "| Variant | Path | Layers | Primary signal | Failure meaning |",
        "|---|---|---|---|---|",
    ]
    for item in summary["variants"]:
        matrix.append(
            f"| {item['variant']} | `{item['path']}` | {item['layers']} | {item['primary_signal']} | {item['failure_meaning']} |"
        )
    (REPORT_ROOT / "mp_converted_runtime_probe_pass1_test_matrix.md").write_text("\n".join(matrix) + "\n", encoding="utf-8")

    report = [
        "# MP Converted Runtime Probe Pass 1",
        "",
        "No live game files were modified. All outputs are cloned RPF variants.",
        "",
        f"- Base RPF: `{summary['base_rpf']}`",
        f"- Converted WSC tree: `{CONVERTED_WSC_TREE}`",
        "",
        "## Variants",
        "",
    ]
    for item in summary["variants"]:
        report.extend(
            [
                f"### {item['variant']}",
                f"- Path: `{item['path']}`",
                f"- SHA1: `{item['sha1']}`",
                f"- Layers: {item['layers']}",
                f"- Entry count: `{item['entry_count']}`",
                f"- Converted MP WSC count: `{item['converted_mp_wsc_count']}`",
                "",
            ]
        )
    if warnings:
        report.extend(["## Warnings", ""])
        report.extend(f"- {warning}" for warning in warnings)
        report.append("")
    report.extend(
        [
            "## Runtime Interpretation",
            "",
            "- Crash on boot: bad import path/resource wrapper.",
            "- Crash only after online/MP entry: converted MP script runtime issue or frontend successfully reached backend.",
            "- No behavior change: frontend route still does not reach converted MP scripts.",
            "- Changed prompt/loading/menu behavior: keep that variant as the next base and isolate the next gate.",
            "",
        ]
    )
    (REPORT_ROOT / "mp_converted_runtime_probe_pass1_report.md").write_text("\n".join(report), encoding="utf-8")


def build() -> dict[str, Any]:
    if not PASS5_BASE.exists():
        raise FileNotFoundError(PASS5_BASE)
    if not RDR_EXE.exists():
        raise FileNotFoundError(RDR_EXE)
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    converted_rows = collect_converted_wsc_rows()
    press_rows, press_warnings = discover_pressstart_d_rows()
    optional_xml_rows, optional_xml_warnings = discover_optional_xml_bypass_rows()
    main_patch_rows, main_patch_reports = collect_main_patch_rows(PASS5_BASE)

    warnings = press_warnings + optional_xml_warnings
    variant_defs = [
        (
            "A_converted_wsc_tree_only",
            converted_rows,
            "converted XENON->PC WSC tree only",
            "game boots with no menu regression",
            "bad converted resource import if boot crash",
        ),
        (
            "B_converted_plus_pressstart_D",
            converted_rows + press_rows,
            "A + pressstart_D_full_force" if press_rows else "A only; pressstart_D_full_force unavailable",
            "press start or initial online/menu route changes",
            "pressstart layer if B differs from A; otherwise same as A",
        ),
        (
            "C_converted_plus_core_D",
            converted_rows + press_rows + main_patch_rows,
            "B + main/main_z no_autosave->xmlsave WSC patches",
            "core save/profile gate behavior changes",
            "main/main_z patch if C differs from B",
        ),
        (
            "D_full_runtime_probe",
            converted_rows + press_rows + main_patch_rows + optional_xml_rows,
            "C + explicit savegame/savegame2/netstats XML bypasses" if optional_xml_rows else "C only; no explicit savegame/savegame2/netstats bypass artifacts available",
            "net.EnterOnline/loading/freemode route advances past prior prompt",
            "converted backend runtime if crash only after MP entry",
        ),
    ]

    variants: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    verifications: list[dict[str, Any]] = []
    for name, rows, layer_desc, signal, failure in variant_defs:
        output = BUILD_ROOT / f"{name}.rpf"
        build_report = build_overlay_rpf(PASS5_BASE, output, rows)
        readback = verify_rows(output, rows, name)
        verifications.extend(readback)
        inv = inventory_summary(output)
        variants.append(
            {
                "variant": name,
                "path": str(output),
                "sha1": inv["sha1"],
                "entry_count": inv["entry_count"],
                "file_count": inv["file_count"],
                "converted_mp_wsc_count": inv["converted_mp_wsc_count"],
                "converted_release64_core_present": inv["converted_release64_core_present"],
                "layers": layer_desc,
                "primary_signal": signal,
                "failure_meaning": failure,
            }
        )
        for op in build_report["operations"]:
            manifests.append({"variant": name, **op})

    summary = {
        "base_rpf": str(PASS5_BASE),
        "base_sha1": sha1_file(PASS5_BASE),
        "build_root": str(BUILD_ROOT),
        "report_root": str(REPORT_ROOT),
        "converted_source_count": len(converted_rows),
        "pressstart_D_rows": len(press_rows),
        "optional_xml_bypass_rows": len(optional_xml_rows),
        "main_patch_reports": main_patch_reports,
        "warnings": warnings,
        "variants": variants,
        "readback_status_counts": {},
    }
    for row in verifications:
        summary["readback_status_counts"][row["status"]] = summary["readback_status_counts"].get(row["status"], 0) + 1
    write_reports(summary, manifests, verifications, warnings, main_patch_reports)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
