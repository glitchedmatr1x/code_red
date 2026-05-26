#!/usr/bin/env python3
"""SP FreeMode Sector Graft Pass 2: TES sector graft.

This pass does not add bytecode calls. It reuses existing SP sector-native
callsites and changes only same-size-safe PushString operands to TES MP sector
names.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PASS1_BUILDER = ROOT / "tools" / "codered_sp_freemode_sector_graft_builder.py"
BASE_RPF = ROOT / "build" / "sp_freemode_sector_graft_pass1" / "reconstructed_A_disable_update_thread_refs_from_F1D9391F4EE5CC32634B8625F32F63302F92ABB4.rpf"
BUILD_ROOT = ROOT / "build" / "sp_freemode_sector_graft_pass2"
REPORT_ROOT = ROOT / "reports" / "sp_freemode_sector_graft_pass2"
RDR_EXE = ROOT.parent / "RDR.exe"
MAIN_WSC = "root/content/release64/main.wsc"
SP_FILES = [
    "root/content/release64/sp_idle.wsc",
    "root/content/release64/main.wsc",
    "root/content/release64/init/rdr2init.wsc",
    "root/content/release64/pressstart.wsc",
]


@dataclass(frozen=True)
class Slot:
    slot_id: str
    archive_path: str
    instruction_offset: int
    string_offset: int
    slot_size: int
    original: str
    native_offset: int
    native_bits: str
    decompile_native: str
    function: str
    risk: str
    reason: str


PRIMARY_SLOT = Slot(
    slot_id="MAIN_ENABLE_CHILD_RWF_BARN_PROPS01",
    archive_path=MAIN_WSC,
    instruction_offset=0x34151,
    string_offset=0x34153,
    slot_size=0x14,
    original="rwf_barn01xprops01x",
    native_offset=0x34167,
    native_bits="0x0E82",
    decompile_native="ENABLE_CHILD_SECTOR",
    function="Function_562/Function_714 sector state table family",
    risk="medium",
    reason="Pasted sector decompile labels this sector as ENABLE_CHILD_SECTOR; slot is long enough for mp_tes_coop01ax with NUL padding.",
)

A4_SLOTS = [
    (PRIMARY_SLOT, "mp_tes_coop01ax"),
    (
        Slot(
            "MAIN_ENABLE_CHILD_BEH_HOUSE_PROPS01",
            MAIN_WSC,
            0x34283,
            0x34285,
            0x14,
            "beh_house01props01x",
            0x34299,
            "0x0E82",
            "ENABLE_CHILD_SECTOR",
            "Function_562/Function_714 sector state table family",
            "medium",
            "Pasted sector decompile labels this sector as ENABLE_CHILD_SECTOR; slot is long enough for mp_tes_coop01bx with NUL padding.",
        ),
        "mp_tes_coop01bx",
    ),
    (
        Slot(
            "MAIN_ENABLE_CHILD_TOR_MILITARY_CAMP02",
            MAIN_WSC,
            0x342B8,
            0x342BA,
            0x14,
            "tor_militaryCamp02x",
            0x342CE,
            "0x0E82",
            "ENABLE_CHILD_SECTOR",
            "Function_562/Function_714 sector state table family",
            "medium",
            "Pasted sector decompile labels this sector as ENABLE_CHILD_SECTOR; slot is long enough for mp_tes_coop01cx with NUL padding.",
        ),
        "mp_tes_coop01cx",
    ),
    (
        Slot(
            "MAIN_ENABLE_CHILD_ESC_VILLA_WALL05",
            MAIN_WSC,
            0x342E7,
            0x342E9,
            0x11,
            "esc_villaWall05x",
            0x342FA,
            "0x0D82",
            "ENABLE_CHILD_SECTOR",
            "Function_562/Function_714 sector state table family",
            "medium",
            "Pasted sector decompile labels this sector as ENABLE_CHILD_SECTOR; slot is long enough for mp_tes_coop02x with NUL padding.",
        ),
        "mp_tes_coop02x",
    ),
]


def load_pass1():
    spec = importlib.util.spec_from_file_location("codered_sp_freemode_sector_graft_builder_pass2", PASS1_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {PASS1_BUILDER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def replacement_bytes(target: str, slot_size: int) -> bytes:
    raw = target.encode("ascii") + b"\x00"
    if len(raw) > slot_size:
        raise ValueError(f"{target} does not fit {slot_size}-byte PushString slot")
    return raw + (b"\x00" * (slot_size - len(raw)))


def patch_slots(decoded: bytes, replacements: list[tuple[Slot, str]]) -> tuple[bytes, list[dict[str, Any]]]:
    out = bytearray(decoded)
    rows: list[dict[str, Any]] = []
    for slot, target in replacements:
        current = bytes(out[slot.string_offset : slot.string_offset + slot.slot_size])
        original_raw = slot.original.encode("ascii") + b"\x00"
        if not current.startswith(original_raw):
            raise RuntimeError(
                f"slot {slot.slot_id} did not contain expected original {slot.original!r}: "
                f"got {current.hex(' ').upper()}"
            )
        new = replacement_bytes(target, slot.slot_size)
        out[slot.string_offset : slot.string_offset + slot.slot_size] = new
        rows.append(
            {
                "slot_id": slot.slot_id,
                "archive_path": slot.archive_path,
                "instruction_offset": f"0x{slot.instruction_offset:X}",
                "string_offset": f"0x{slot.string_offset:X}",
                "slot_size": slot.slot_size,
                "original": slot.original,
                "target": target,
                "old_bytes": current.hex(" ").upper(),
                "new_bytes": new.hex(" ").upper(),
                "native_offset": f"0x{slot.native_offset:X}",
                "native_bits": slot.native_bits,
                "decompile_native": slot.decompile_native,
                "function": slot.function,
                "risk": slot.risk,
                "reason": slot.reason,
                "changed": current != new,
            }
        )
    return bytes(out), rows


def repack_decoded_wsc(payload: bytes, decoded: bytes, label: str, temp_dir: Path):
    from codered_wsc.resource import KeyOptions, open_script, open_script_from_bytes, repack_script

    temp = temp_dir / f"{label}.wsc"
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(payload)
    resource = open_script(temp, KeyOptions(rdr_exe=str(RDR_EXE)))
    output, repack_report = repack_script(resource, decoded, allow_growth=True)
    reopened = open_script_from_bytes(output, temp, resource.key or b"", originally_xsc=False)
    if reopened.decoded != decoded:
        raise RuntimeError(f"repacked WSC did not reopen to expected decoded bytes: {label}")
    return output, repack_report


def extract_wsc(pass1, wb, archive: Path, info: dict[str, Any], archive_path: str) -> bytes:
    return pass1.extract_entry_payload(wb, archive, info, archive_path)


def build_variant(pass1, source: Path, name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = BUILD_ROOT / f"{name}.rpf"
    report = pass1.build_overlay_rpf(source, out, rows)
    return report


def row_for_payload(layer: str, archive_path: str, payload: bytes, note: str) -> dict[str, Any]:
    return {
        "layer": layer,
        "archive_path": archive_path,
        "payload": payload,
        "operation": "replace",
        "allow_resource_replace": archive_path.lower().endswith(".wsc"),
        "note": note,
    }


def write_reports(
    source: Path,
    source_sha1: str,
    variants: list[dict[str, Any]],
    existing_calls: list[dict[str, Any]],
    fit_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    changed_offsets: list[dict[str, Any]],
    readback_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    magic_summary: dict[str, Any],
) -> None:
    write_csv(REPORT_ROOT / "existing_sector_calls.csv", existing_calls)
    write_csv(REPORT_ROOT / "tes_sector_fit_report.csv", fit_rows)
    write_csv(REPORT_ROOT / "callsite_risk_report.csv", risk_rows)
    write_csv(REPORT_ROOT / "changed_offsets.csv", changed_offsets)
    write_csv(REPORT_ROOT / "rpf_readback_validation.csv", readback_rows)
    write_csv(REPORT_ROOT / "wsc_edit_validation.csv", validation_rows)
    write_csv(REPORT_ROOT / "pass2_variants.csv", variants)
    write_json(REPORT_ROOT / "magicrdr_summary.json", magic_summary)

    lines = [
        "# SP FreeMode Sector Graft Pass 2 - TES Sector Graft",
        "",
        f"- base: `{source}`",
        f"- base SHA1: `{source_sha1}`",
        "- multiplayer activation: `not used`",
        "- patch method: existing SP sector-native PushString slot replacement only",
        "",
        "## Built Variants",
        "",
        "| Variant | Status | Output | SHA1 | Notes |",
        "|---|---|---|---|---|",
    ]
    for row in variants:
        lines.append(
            f"| `{row['variant']}` | `{row['status']}` | `{row.get('rpf', '')}` | `{row.get('sha1', '')}` | {row.get('notes', '')} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "A2 uses one existing SP ENABLE_CHILD_SECTOR-labeled callsite and changes only its string operand to `mp_tes_coop01ax`.",
            "A3 is skipped because the sector overlap map did not identify a clear TES SP counterpart to unload.",
            "A4 uses four existing SP ENABLE_CHILD_SECTOR-labeled callsites, one per requested TES test sector.",
            "",
            "## Validation",
            "",
            f"- MagicRDR WSC open: `{json.dumps(magic_summary, sort_keys=True)}`",
            "- RPF reparsed for every built clone.",
            "- Changed WSC payloads were read back and SHA1-compared exactly.",
            "- Code RED WSC reopen passed for changed WSCs.",
            "",
        ]
    )
    (REPORT_ROOT / "pass2_build_report.md").write_text("\n".join(lines), encoding="utf-8")

    test_lines = [
        "# SP FreeMode Sector Graft Pass 2 Test Instructions",
        "",
        "Do not install all variants at once. Restore your original `game\\content.rpf` between tests.",
        "",
        "1. Test `A0_pass2_repack_control.rpf` first. Expected: normal single-player boot, no visible content change.",
        "2. Test `A1_pass2_callsite_noop_control.rpf`. Expected: normal single-player boot, no visible content change.",
        "3. Test `A2_tes_single_sector.rpf`. Expected: normal single-player boot; inspect TES/Tumbleweed area for changed streaming or sector visibility.",
        "4. Test `A4_tes_small_set.rpf` only if A2 boots. Expected: broader TES-sector streaming attempt, still no MP mode launch.",
        "",
        "Crash at A0/A1 means RPF/WSC repack is unsafe. Crash only at A2/A4 means the selected sector graft slot or TES target is the likely cause.",
        "",
    ]
    (REPORT_ROOT / "test_instructions.md").write_text("\n".join(test_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SP FreeMode Sector Graft Pass 2 TES variants.")
    parser.add_argument("--base", default=str(BASE_RPF))
    args = parser.parse_args()

    source = Path(args.base).resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = BUILD_ROOT / "_tmp_wsc"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    pass1 = load_pass1()
    overlay = pass1.load_module(pass1.OVERLAY_TOOL, "codered_overlay_sp_sector_graft_pass2_extract")
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source)
    if info is None:
        raise RuntimeError(f"base RPF did not parse: {source}")
    source_sha1 = pass1.sha1_file(source)

    main_payload = extract_wsc(pass1, wb, source, info, MAIN_WSC)
    from codered_wsc.resource import KeyOptions, open_script

    main_temp = temp_dir / "base_main.wsc"
    main_temp.write_bytes(main_payload)
    main_resource = open_script(main_temp, KeyOptions(rdr_exe=str(RDR_EXE)))

    existing_calls = [
        {
            "archive_path": slot.archive_path,
            "slot_id": slot.slot_id,
            "instruction_offset": f"0x{slot.instruction_offset:X}",
            "string_offset": f"0x{slot.string_offset:X}",
            "slot_size": slot.slot_size,
            "sector_name": slot.original,
            "native_offset": f"0x{slot.native_offset:X}",
            "native_bits": slot.native_bits,
            "decompile_native": slot.decompile_native,
            "function": slot.function,
            "risk": slot.risk,
            "reason": slot.reason,
        }
        for slot, _target in A4_SLOTS
    ]
    fit_rows: list[dict[str, Any]] = []
    for slot, target in A4_SLOTS:
        for candidate in ["mp_tes_coop01ax", "mp_tes_coop01bx", "mp_tes_coop01cx", "mp_tes_coop02x", "mp_tes_base01x"]:
            needed = len(candidate.encode("ascii")) + 1
            fit_rows.append(
                {
                    "slot_id": slot.slot_id,
                    "original": slot.original,
                    "slot_size": slot.slot_size,
                    "candidate": candidate,
                    "needed_size": needed,
                    "fits": needed <= slot.slot_size,
                    "selected_for_variant": candidate == target,
                }
            )
    risk_rows = [dict(row) for row in existing_calls]

    variants: list[dict[str, Any]] = []
    readback_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    changed_offsets: list[dict[str, Any]] = []
    magic_inputs = BUILD_ROOT / "magicrdr_validation_inputs"
    if magic_inputs.exists():
        shutil.rmtree(magic_inputs)

    # A0: replace main.wsc with exact base payload as a repack/readback control.
    a0_rows = [row_for_payload("A0_pass2_repack_control", MAIN_WSC, main_payload, "exact base payload; no decoded change")]
    a0_report = build_variant(pass1, source, "A0_pass2_repack_control", a0_rows)
    readback_rows.extend(pass1.verify_readback(BUILD_ROOT / "A0_pass2_repack_control.rpf", a0_rows, "A0_pass2_repack_control"))
    validation_rows.extend(pass1.validate_wsc_payloads(a0_rows, temp_dir, "A0_pass2_repack_control"))
    variants.append({"variant": "A0_pass2_repack_control", "status": "built", "rpf": a0_report["output_rpf"], "sha1": a0_report["output_sha1"], "notes": "Base resource replacement/readback control; no decoded change."})

    # A1: walk through the selected slot without changing it.
    a1_payload, a1_repack = repack_decoded_wsc(main_payload, main_resource.decoded, "A1_pass2_callsite_noop_control_main", temp_dir)
    a1_rows = [row_for_payload("A1_pass2_callsite_noop_control", MAIN_WSC, a1_payload, f"no-op repack validating slot {PRIMARY_SLOT.slot_id}; no decoded change")]
    a1_report = build_variant(pass1, source, "A1_pass2_callsite_noop_control", a1_rows)
    readback_rows.extend(pass1.verify_readback(BUILD_ROOT / "A1_pass2_callsite_noop_control.rpf", a1_rows, "A1_pass2_callsite_noop_control"))
    validation_rows.extend(pass1.validate_wsc_payloads(a1_rows, temp_dir, "A1_pass2_callsite_noop_control"))
    variants.append({"variant": "A1_pass2_callsite_noop_control", "status": "built", "rpf": a1_report["output_rpf"], "sha1": a1_report["output_sha1"], "notes": f"No-op repack through selected callsite lane: {PRIMARY_SLOT.slot_id}."})

    # A2: one TES sector through the primary existing SP callsite.
    a2_decoded, a2_changes = patch_slots(main_resource.decoded, [(PRIMARY_SLOT, "mp_tes_coop01ax")])
    a2_payload, a2_repack = repack_decoded_wsc(main_payload, a2_decoded, "A2_tes_single_sector_main", temp_dir)
    a2_rows = [row_for_payload("A2_tes_single_sector", MAIN_WSC, a2_payload, "one TES MP sector through existing SP ENABLE_CHILD_SECTOR-labeled callsite")]
    a2_report = build_variant(pass1, source, "A2_tes_single_sector", a2_rows)
    readback_rows.extend(pass1.verify_readback(BUILD_ROOT / "A2_tes_single_sector.rpf", a2_rows, "A2_tes_single_sector"))
    validation_rows.extend(pass1.validate_wsc_payloads(a2_rows, temp_dir, "A2_tes_single_sector"))
    changed_offsets.extend({"variant": "A2_tes_single_sector", **row} for row in a2_changes)
    variants.append({"variant": "A2_tes_single_sector", "status": "built", "rpf": a2_report["output_rpf"], "sha1": a2_report["output_sha1"], "notes": "Replaces rwf_barn01xprops01x slot with mp_tes_coop01ax."})

    variants.append({"variant": "A3_tes_single_sector_with_sp_counterpart_unload", "status": "skipped", "rpf": "", "sha1": "", "notes": "Skipped: sector_overlap_map has no clear TES SP counterpart to disable safely."})

    # A4: four TES sectors through four selected existing SP callsites.
    a4_decoded, a4_changes = patch_slots(main_resource.decoded, A4_SLOTS)
    a4_payload, a4_repack = repack_decoded_wsc(main_payload, a4_decoded, "A4_tes_small_set_main", temp_dir)
    a4_rows = [row_for_payload("A4_tes_small_set", MAIN_WSC, a4_payload, "four TES MP sectors through existing SP ENABLE_CHILD_SECTOR-labeled callsites")]
    a4_report = build_variant(pass1, source, "A4_tes_small_set", a4_rows)
    readback_rows.extend(pass1.verify_readback(BUILD_ROOT / "A4_tes_small_set.rpf", a4_rows, "A4_tes_small_set"))
    validation_rows.extend(pass1.validate_wsc_payloads(a4_rows, temp_dir, "A4_tes_small_set"))
    changed_offsets.extend({"variant": "A4_tes_small_set", **row} for row in a4_changes)
    variants.append({"variant": "A4_tes_small_set", "status": "built", "rpf": a4_report["output_rpf"], "sha1": a4_report["output_sha1"], "notes": "Replaces four SP child-sector slots with TES coop sector names."})

    for label, rows in [
        ("A0_pass2_repack_control", a0_rows),
        ("A1_pass2_callsite_noop_control", a1_rows),
        ("A2_tes_single_sector", a2_rows),
        ("A4_tes_small_set", a4_rows),
    ]:
        for row in rows:
            out = magic_inputs / label / Path(row["archive_path"]).name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(row["payload"])
    magic_summary = pass1.run_magicrdr(magic_inputs, REPORT_ROOT / "magicrdr_wsc_open", "SP FreeMode Sector Graft Pass 2 MagicRDR WSC Open")

    write_reports(source, source_sha1, variants, existing_calls, fit_rows, risk_rows, changed_offsets, readback_rows, validation_rows, magic_summary)

    print(
        json.dumps(
            {
                "base": str(source),
                "base_sha1": source_sha1,
                "built": [row for row in variants if row["status"] == "built"],
                "skipped": [row for row in variants if row["status"] != "built"],
                "reports": str(REPORT_ROOT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
