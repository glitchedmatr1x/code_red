#!/usr/bin/env python3
"""Build reconstructed SP FreeMode sector graft baseline and safe probes.

This pass intentionally does not activate multiplayer.  It reconstructs the
known A_disable_update_thread_refs behavior by replacing only references to the
multiplayer update thread in normal single-player WSC resources, then builds
the control/probe RPF clones that can be validated without inventing WSC code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OVERLAY_TOOL = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
RPF_UTILS_TOOL = ROOT / "tools" / "codered_rpf_utils.py"
MAGICRDR_COMPAT = ROOT / "tools" / "codered_magicrdr_wsc_compat.py"
RDR_EXE = ROOT.parent / "RDR.exe"
DEFAULT_SOURCE = ROOT / "build" / "mp_content_restore_pass5" / "content_mp_restore_pass5_access_trainer_sectors.rpf"
BUILD_ROOT = ROOT / "build" / "sp_freemode_sector_graft_pass1"
REPORT_ROOT = ROOT / "reports" / "sp_freemode_sector_graft_pass1"

MAIN_WSC = "root/content/release64/main.wsc"
RDR2INIT_WSC = "root/content/release64/init/rdr2init.wsc"
SP_IDLE_WSC = "root/content/release64/sp_idle.wsc"

FULL_MP_UPDATE = b"$/content/multiplayer/multiplayer_update_thread"
FULL_DISABLED = b"$/content/multiplayer/codered_disabled_thread__"
PARTIAL_MP_UPDATE = b"multiplayer/multiplayer_update_thread"
PARTIAL_DISABLED = b"multiplayer/codered_disabled_thread__"


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def find_entry(info: dict[str, Any], archive_path: str) -> dict[str, Any]:
    wanted = archive_path.replace("\\", "/").lower()
    for entry in info.get("entries", []):
        if entry.get("type") == "file" and str(entry.get("path") or "").replace("\\", "/").lower() == wanted:
            return entry
    raise KeyError(archive_path)


def extract_entry_payload(wb: Any, archive: Path, info: dict[str, Any], archive_path: str) -> bytes:
    entry = find_entry(info, archive_path)
    return wb.extract_rpf_entry(archive, entry)


def patch_disable_update_refs(payload: bytes, source_label: str, temp_dir: Path) -> tuple[bytes, dict[str, Any]]:
    from codered_wsc.resource import KeyOptions, open_script, open_script_from_bytes, repack_script

    temp = temp_dir / source_label.replace("/", "__")
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(payload)
    resource = open_script(temp, KeyOptions(rdr_exe=str(RDR_EXE)))
    decoded = bytearray(resource.decoded)
    changes: list[dict[str, Any]] = []

    def replace_all(find: bytes, replace: bytes, label: str) -> None:
        if len(find) != len(replace):
            raise RuntimeError(f"replacement is not same-size for {label}")
        start = 0
        while True:
            offset = bytes(decoded).find(find, start)
            if offset < 0:
                break
            decoded[offset : offset + len(find)] = replace
            changes.append(
                {
                    "source_label": source_label,
                    "decoded_offset": offset,
                    "decoded_offset_hex": f"0x{offset:X}",
                    "find": find.decode("ascii"),
                    "replace": replace.decode("ascii"),
                    "length": len(find),
                    "kind": label,
                }
            )
            start = offset + len(replace)

    replace_all(FULL_MP_UPDATE, FULL_DISABLED, "full_script_path")
    replace_all(PARTIAL_MP_UPDATE, PARTIAL_DISABLED, "partial_script_path")
    patched_decoded = bytes(decoded)
    if not changes:
        raise RuntimeError(f"No multiplayer_update_thread references found in {source_label}")
    output, repack_report = repack_script(resource, patched_decoded, allow_growth=True)
    reopened = open_script_from_bytes(output, temp, resource.key or b"", originally_xsc=False)
    validate_ok = reopened.decoded == patched_decoded
    if not validate_ok:
        raise RuntimeError(f"repacked WSC did not reopen to patched decoded bytes: {source_label}")
    return output, {
        "source_label": source_label,
        "status": "patched",
        "change_count": len(changes),
        "changes": changes,
        "decoded_sha1": sha1_bytes(patched_decoded),
        "output_sha1": sha1_bytes(output),
        "output_size": len(output),
        "repack": repack_report,
        "codered_reopen_ok": validate_ok,
    }


def repack_unchanged_wsc(payload: bytes, source_label: str, temp_dir: Path) -> tuple[bytes, dict[str, Any]]:
    from codered_wsc.resource import KeyOptions, open_script, open_script_from_bytes, repack_script

    temp = temp_dir / source_label.replace("/", "__")
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(payload)
    resource = open_script(temp, KeyOptions(rdr_exe=str(RDR_EXE)))
    output, repack_report = repack_script(resource, resource.decoded, allow_growth=True)
    reopened = open_script_from_bytes(output, temp, resource.key or b"", originally_xsc=False)
    validate_ok = reopened.decoded == resource.decoded
    if not validate_ok:
        raise RuntimeError(f"unchanged repack did not reopen cleanly: {source_label}")
    return output, {
        "source_label": source_label,
        "status": "repacked_no_decoded_change",
        "decoded_sha1": sha1_bytes(resource.decoded),
        "input_sha1": sha1_bytes(payload),
        "output_sha1": sha1_bytes(output),
        "input_size": len(payload),
        "output_size": len(output),
        "repack": repack_report,
        "codered_reopen_ok": validate_ok,
    }


def pack_toc_with_resource_flags(overlay: Any, wb: Any, nodes: list[Any], encrypted: bool) -> bytes:
    toc = bytearray()
    for node in nodes:
        if node.kind == "dir":
            toc.extend(struct.pack(">5I", node.name_off, 0, 0x80000000 | node.start, node.count, 0))
            continue
        if node.operation in {"add", "replace"}:
            b = node.stored_size & 0x0FFFFFFF
            c = overlay.file_offset_raw(wb, node)
            if node.resource_replace:
                d = node.resource_flag1
                e = node.resource_flag2
            else:
                compression_bit = 0x40000000 if node.force_compressed else 0
                d = compression_bit | (node.decoded_size & 0x3FFFFFFF)
                e = 0
        else:
            ent = node.original or {}
            b = int(ent.get("size_in_archive") or 0) & 0x0FFFFFFF
            c = overlay.file_offset_raw(wb, node)
            d = int(ent.get("flag1") or 0)
            e = int(ent.get("flag2") or 0)
        toc.extend(struct.pack(">5I", node.name_off, b, c, d, e))
    padded_size = overlay.align(len(toc), 16)
    toc.extend(b"\x00" * (padded_size - len(toc)))
    return wb._codered_rpf6_encrypt(bytes(toc)) if encrypted else bytes(toc)


def build_overlay_rpf(source_rpf: Path, output_rpf: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    overlay = load_module(OVERLAY_TOOL, "codered_overlay_sp_sector_graft")
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
            allow_resource_replace=bool(row.get("allow_resource_replace")),
        )
        op = {key: value for key, value in row.items() if key != "payload"}
        op.update(
            {
                "result": action,
                "stored_size": node.stored_size,
                "decoded_size": node.decoded_size,
                "resource_replace": node.resource_replace,
                "resource_flag1": f"0x{node.resource_flag1:08X}" if node.resource_replace else "",
                "resource_flag2": f"0x{node.resource_flag2:08X}" if node.resource_replace else "",
                "expected_sha1": sha1_bytes(row["payload"]),
                "expected_size": len(row["payload"]),
            }
        )
        operations.append(op)

    nodes = overlay.flatten_tree(root)
    new_toc_size = overlay.align(len(nodes) * 20, 16)
    original_payload_floor = min(int(ent["offset"]) for ent in info["entries"] if ent.get("type") == "file")
    if 16 + new_toc_size > original_payload_floor:
        raise RuntimeError(f"new TOC ({16 + new_toc_size}) would overlap first payload at {original_payload_floor}")

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
        payload = node.source_bytes or b""
        output_bytes.extend(payload)
        padded = overlay.align(len(output_bytes), 8)
        if padded > len(output_bytes):
            output_bytes.extend(b"\x00" * (padded - len(output_bytes)))

    toc = pack_toc_with_resource_flags(overlay, wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", output_bytes, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    output_bytes[16 : 16 + len(toc)] = toc
    output_rpf.parent.mkdir(parents=True, exist_ok=True)
    output_rpf.write_bytes(output_bytes)
    parsed = wb.parse_rpf6(output_rpf)
    if parsed is None:
        raise RuntimeError(f"output RPF did not parse: {output_rpf}")
    return {
        "source_rpf": str(source_rpf),
        "source_sha1": sha1_file(source_rpf),
        "output_rpf": str(output_rpf),
        "output_sha1": sha1_file(output_rpf),
        "entry_count": parsed.get("entry_count"),
        "file_count": parsed.get("file_count"),
        "dir_count": parsed.get("dir_count"),
        "operations": operations,
        "status": "pass",
    }


def verify_readback(rpf: Path, rows: list[dict[str, Any]], report_label: str) -> list[dict[str, Any]]:
    wb = load_module(RPF_UTILS_TOOL, "codered_rpf_utils_sp_sector_graft").load_backend()
    info = wb.parse_rpf6(rpf)
    if info is None:
        raise RuntimeError(f"RPF did not parse for readback: {rpf}")
    results: list[dict[str, Any]] = []
    for row in rows:
        data = extract_entry_payload(wb, rpf, info, row["archive_path"])
        results.append(
            {
                "label": report_label,
                "rpf": str(rpf),
                "archive_path": row["archive_path"],
                "expected_sha1": sha1_bytes(row["payload"]),
                "actual_sha1": sha1_bytes(data),
                "expected_size": len(row["payload"]),
                "actual_size": len(data),
                "match": data == row["payload"],
            }
        )
    return results


def validate_wsc_payloads(rows: list[dict[str, Any]], temp_dir: Path, label: str) -> list[dict[str, Any]]:
    from codered_wsc.resource import KeyOptions, open_script

    out: list[dict[str, Any]] = []
    for row in rows:
        if not row["archive_path"].lower().endswith(".wsc"):
            continue
        path = temp_dir / label / row["archive_path"].replace("/", "__")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(row["payload"])
        result: dict[str, Any] = {
            "label": label,
            "archive_path": row["archive_path"],
            "file": str(path),
            "sha1": sha1_bytes(row["payload"]),
            "size": len(row["payload"]),
            "codered_reopen_ok": False,
            "error": "",
        }
        try:
            resource = open_script(path, KeyOptions(rdr_exe=str(RDR_EXE)))
            result.update({"codered_reopen_ok": True, "decoded_size": len(resource.decoded), "decoded_sha1": sha1_bytes(resource.decoded)})
        except Exception as exc:
            result["error"] = str(exc)
        out.append(result)
    return out


def run_magicrdr(source: Path, out: Path, title: str) -> dict[str, Any]:
    if not MAGICRDR_COMPAT.exists():
        return {"tested": 0, "passed": 0, "failed": 0, "error": f"missing {MAGICRDR_COMPAT}"}
    cmd = [
        sys.executable,
        str(MAGICRDR_COMPAT),
        "--source",
        str(source),
        "--out",
        str(out),
        "--title",
        title,
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    payload = {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    try:
        payload.update(json.loads(proc.stdout.strip().splitlines()[-1]))
    except Exception:
        pass
    return payload


def make_rows_from_payloads(payloads: dict[str, bytes], layer: str, note: str) -> list[dict[str, Any]]:
    return [
        {
            "layer": layer,
            "archive_path": archive_path,
            "payload": payload,
            "operation": "replace",
            "allow_resource_replace": archive_path.lower().endswith(".wsc"),
            "note": note,
        }
        for archive_path, payload in payloads.items()
    ]


def build(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.source).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = BUILD_ROOT / "_tmp_wsc"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    overlay = load_module(OVERLAY_TOOL, "codered_overlay_sp_sector_graft_extract")
    wb = overlay.load_backend()
    source_info = wb.parse_rpf6(source)
    if source_info is None:
        raise RuntimeError(f"source RPF did not parse: {source}")

    source_sha = sha1_file(source)
    reconstructed_name = f"reconstructed_A_disable_update_thread_refs_from_{source_sha}.rpf"
    reconstructed_rpf = BUILD_ROOT / reconstructed_name

    main_payload = extract_entry_payload(wb, source, source_info, MAIN_WSC)
    rdr2init_payload = extract_entry_payload(wb, source, source_info, RDR2INIT_WSC)
    patched_main, main_report = patch_disable_update_refs(main_payload, MAIN_WSC, temp_dir)
    patched_rdr2init, rdr2init_report = patch_disable_update_refs(rdr2init_payload, RDR2INIT_WSC, temp_dir)
    recon_rows = make_rows_from_payloads(
        {MAIN_WSC: patched_main, RDR2INIT_WSC: patched_rdr2init},
        "reconstructed_A_disable_update_thread_refs",
        "same-size decoded string reroute of multiplayer_update_thread references only",
    )
    recon_report = build_overlay_rpf(source, reconstructed_rpf, recon_rows)

    validation_rows: list[dict[str, Any]] = []
    readback_rows: list[dict[str, Any]] = []
    variant_rows: list[dict[str, Any]] = []
    patch_change_rows: list[dict[str, Any]] = []
    for report in (main_report, rdr2init_report):
        patch_change_rows.extend(report["changes"])
    validation_rows.extend(validate_wsc_payloads(recon_rows, temp_dir, "reconstructed_base"))
    readback_rows.extend(verify_readback(reconstructed_rpf, recon_rows, "reconstructed_base"))

    variant_rows.append(
        {
            "variant": "reconstructed_base",
            "status": "built",
            "rpf": str(reconstructed_rpf),
            "sha1": sha1_file(reconstructed_rpf),
            "changed_files": f"{MAIN_WSC}; {RDR2INIT_WSC}",
            "notes": "Approved reconstructed base; no MP activation calls added.",
        }
    )

    # A0: force a resource replacement using the exact reconstructed payloads.
    recon_info = wb.parse_rpf6(reconstructed_rpf)
    if recon_info is None:
        raise RuntimeError("reconstructed RPF failed to parse after build")
    a0_payloads = {
        MAIN_WSC: extract_entry_payload(wb, reconstructed_rpf, recon_info, MAIN_WSC),
        RDR2INIT_WSC: extract_entry_payload(wb, reconstructed_rpf, recon_info, RDR2INIT_WSC),
    }
    a0_rows = make_rows_from_payloads(a0_payloads, "A0_repack_control", "exact reconstructed WSC payload replacement control")
    a0_rpf = BUILD_ROOT / "A0_repack_control.rpf"
    a0_report = build_overlay_rpf(reconstructed_rpf, a0_rpf, a0_rows)
    validation_rows.extend(validate_wsc_payloads(a0_rows, temp_dir, "A0_repack_control"))
    readback_rows.extend(verify_readback(a0_rpf, a0_rows, "A0_repack_control"))
    variant_rows.append(
        {
            "variant": "A0_repack_control",
            "status": "built",
            "rpf": str(a0_rpf),
            "sha1": sha1_file(a0_rpf),
            "changed_files": f"{MAIN_WSC}; {RDR2INIT_WSC}",
            "notes": "No decoded content changes from reconstructed base; resource replacement/readback control.",
        }
    )

    # A1: unchanged sp_idle WSC repack probe. This intentionally does not add
    # logging because we do not have validated WSC code insertion in this pass.
    sp_idle_payload = extract_entry_payload(wb, reconstructed_rpf, recon_info, SP_IDLE_WSC)
    sp_idle_repacked, sp_idle_report = repack_unchanged_wsc(sp_idle_payload, SP_IDLE_WSC, temp_dir)
    a1_rows = make_rows_from_payloads(
        {SP_IDLE_WSC: sp_idle_repacked},
        "A1_sp_wsc_noop_probe",
        "sp_idle WSC decode/repack/reopen probe; decoded bytes unchanged",
    )
    a1_rpf = BUILD_ROOT / "A1_sp_wsc_noop_probe.rpf"
    a1_report = build_overlay_rpf(reconstructed_rpf, a1_rpf, a1_rows)
    validation_rows.extend(validate_wsc_payloads(a1_rows, temp_dir, "A1_sp_wsc_noop_probe"))
    readback_rows.extend(verify_readback(a1_rpf, a1_rows, "A1_sp_wsc_noop_probe"))
    variant_rows.append(
        {
            "variant": "A1_sp_wsc_noop_probe",
            "status": "built",
            "rpf": str(a1_rpf),
            "sha1": sha1_file(a1_rpf),
            "changed_files": SP_IDLE_WSC,
            "notes": "No-op WSC resource probe only; no sector calls or log calls inserted.",
        }
    )

    blocked_reason = (
        "blocked: no validated WSC authoring/control-flow primitive exists yet for adding ENABLE_CHILD_SECTOR "
        "calls. String-only edits would not execute sectors, so no fake sector RPF was produced."
    )
    for variant, sectors in [
        ("A2_one_mp_sector_only", "mp_tes_coop01ax"),
        ("A3_one_mp_sector_plus_sp_counterpart_unload", "mp_tes_coop01ax + SP counterpart unload"),
        ("A4_small_region_sector_set", "mp_tes_coop01ax; mp_tes_coop01bx; mp_tes_coop01cx; mp_tes_coop02x"),
        ("A5_gap_mine_lid_test", "mp_gap_mineLid01x"),
    ]:
        variant_rows.append(
            {
                "variant": variant,
                "status": "blocked_no_rpf_built",
                "rpf": "",
                "sha1": "",
                "changed_files": "",
                "sectors": sectors,
                "notes": blocked_reason,
            }
        )

    # Export changed WSC payloads for MagicRDR standalone validation.
    magic_source = BUILD_ROOT / "magicrdr_validation_inputs"
    if magic_source.exists():
        shutil.rmtree(magic_source)
    for label, rows in [("reconstructed_base", recon_rows), ("A0_repack_control", a0_rows), ("A1_sp_wsc_noop_probe", a1_rows)]:
        for row in rows:
            out = magic_source / label / Path(row["archive_path"]).name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(row["payload"])
    magic_summary = run_magicrdr(magic_source, REPORT_ROOT / "magicrdr_wsc_open", "SP FreeMode Sector Graft Pass 1 MagicRDR WSC Open")

    write_csv(REPORT_ROOT / "reconstructed_base_changed_offsets.csv", patch_change_rows)
    write_csv(REPORT_ROOT / "sector_test_variants.csv", variant_rows)
    write_csv(REPORT_ROOT / "wsc_edit_validation.csv", validation_rows)
    write_csv(REPORT_ROOT / "rpf_readback_validation.csv", readback_rows)
    write_json(REPORT_ROOT / "reconstructed_base_patch_report.json", {"main": main_report, "rdr2init": rdr2init_report})
    write_json(REPORT_ROOT / "rpf_build_reports.json", {"reconstructed": recon_report, "A0": a0_report, "A1": a1_report})
    write_json(REPORT_ROOT / "magicrdr_summary.json", magic_summary)

    report_lines = [
        "# SP FreeMode Sector Graft Pass 1 - Build Report",
        "",
        "Status: reconstructed base built; A0 and A1 built; A2-A5 blocked for safety.",
        "",
        f"- source RPF: `{source}`",
        f"- source SHA1: `{source_sha}`",
        f"- reconstructed base: `{reconstructed_rpf}`",
        f"- reconstructed SHA1: `{sha1_file(reconstructed_rpf)}`",
        "",
        "## Reconstructed A_disable_update_thread_refs",
        "",
        "Applied only same-size decoded string reroutes for multiplayer_update_thread references:",
        "",
        f"- `{FULL_MP_UPDATE.decode('ascii')}` -> `{FULL_DISABLED.decode('ascii')}`",
        f"- `{PARTIAL_MP_UPDATE.decode('ascii')}` -> `{PARTIAL_DISABLED.decode('ascii')}`",
        "",
        "No calls were added to net.EnterOnline, TriggerMultiplayerLoad, freemode, PR_Multiplayer, or multiplayer_update_thread.",
        "No save prompt, auth, XML, EXE, ASI, or trainer files were changed.",
        "",
        "## Built Variants",
        "",
        "| Variant | Status | Output | SHA1 |",
        "|---|---|---|---|",
    ]
    for row in variant_rows:
        report_lines.append(f"| `{row['variant']}` | `{row['status']}` | `{row.get('rpf', '')}` | `{row.get('sha1', '')}` |")
    report_lines.extend(
        [
            "",
            "## Sector Variants",
            "",
            "A2, A3, A4, and A5 were not built because this pass does not yet have a validated WSC authoring path for adding sector native calls.",
            "Changing sector name strings alone would be a fake patch: it would not call ENABLE_CHILD_SECTOR or ENABLE_WORLD_SECTOR.",
            "",
            "## Validation Outputs",
            "",
            "- `reconstructed_base_changed_offsets.csv`",
            "- `wsc_edit_validation.csv`",
            "- `rpf_readback_validation.csv`",
            "- `sector_test_variants.csv`",
            "- `magicrdr_wsc_open/`",
            "",
            f"MagicRDR summary: `{json.dumps(magic_summary, sort_keys=True)}`",
            "",
        ]
    )
    (REPORT_ROOT / "build_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "source": str(source),
        "source_sha1": source_sha,
        "reconstructed_rpf": str(reconstructed_rpf),
        "reconstructed_sha1": sha1_file(reconstructed_rpf),
        "built_variants": [row for row in variant_rows if row["status"] == "built"],
        "blocked_variants": [row for row in variant_rows if row["status"] != "built"],
        "reports": str(REPORT_ROOT),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reconstructed SP FreeMode sector graft Pass 1 baseline/probes.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Known-boot source content RPF")
    args = parser.parse_args()
    result = build(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
