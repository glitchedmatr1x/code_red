#!/usr/bin/env python3
"""Build manual-entry MP candidate.

This starts from loading trace F and restores the original conditional branch
in pressstart.wsc that was previously removed to force auto net.EnterOnline.
The goal is to stop the no-input timer crash and leave MP entry to the visible
XML/menu routes.
"""
from __future__ import annotations

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
GAME_ROOT = ROOT.parent / "game"
BASE_RPF = ROOT / "build" / "mp_loading_trace_pass1" / "F_loading_trace_no_boot_patch.rpf"
SOURCE_PRESSSTART = ROOT / "build" / "mp_auth_freeroam_pass1" / "patched_wsc" / "D_auth1_execute_direct_xml_zombie_entry_freeroam_pressstart.wsc"
OUT_ROOT = ROOT / "build" / "mp_manual_entry_pass1"
REPORT_ROOT = ROOT / "reports" / "mp_manual_entry_pass1"
OUTPUT_RPF = OUT_ROOT / "G_manual_mp_entry_no_auto_online.rpf"
GAME_COPY = GAME_ROOT / "mp_manual_entry_pass1" / OUTPUT_RPF.name
RDR_EXE = ROOT.parent / "RDR.exe"
LATEST_BUILDER = ROOT / "tools" / "codered_mp_latest_candidate_builder.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


latest = load_module(LATEST_BUILDER, "codered_mp_latest_candidate_builder_for_manual_entry")


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def patch_pressstart_manual_entry() -> tuple[Path, dict[str, Any]]:
    from codered_wsc.resource import KeyOptions, open_script, repack_script

    resource = open_script(SOURCE_PRESSSTART, KeyOptions(rdr_exe=str(RDR_EXE)))
    decoded = bytearray(resource.decoded)
    offset = 0x43B
    old = bytes.fromhex("00 00 00")
    new = bytes.fromhex("63 00 53")
    actual = bytes(decoded[offset : offset + len(old)])
    if actual != old:
        raise RuntimeError(f"expected forced-online NOP bytes at 0x{offset:X}, got {actual.hex(' ').upper()}")
    decoded[offset : offset + len(old)] = new
    payload, repack = repack_script(resource, bytes(decoded), allow_growth=False)
    out = OUT_ROOT / "patched_wsc" / "pressstart_manual_mp_entry.wsc"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    return out, {
        "source": str(SOURCE_PRESSSTART),
        "output": str(out),
        "output_sha1": sha1_bytes(payload),
        "decoded_offset": f"0x{offset:X}",
        "old_hex": old.hex(" ").upper(),
        "new_hex": new.hex(" ").upper(),
        "reason": "restore original conditional jump so net.EnterOnline is not forced automatically at startup",
        "repack": repack,
    }


def main() -> int:
    for path in [BASE_RPF, SOURCE_PRESSSTART]:
        if not path.exists():
            raise FileNotFoundError(path)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    patched, patch_report = patch_pressstart_manual_entry()
    payload = patched.read_bytes()
    rows = [
        latest.make_row(
            "pressstart_manual_mp_entry_no_auto_net_enter_online",
            patched,
            "root/content/release64/pressstart.wsc",
            payload,
            True,
            "replace",
        )
    ]
    build = latest.build_overlay_rpf(BASE_RPF, OUTPUT_RPF, rows)
    validation = latest.verify_rows(OUTPUT_RPF, rows)
    GAME_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUT_RPF, GAME_COPY)
    manifest = [{k: v for k, v in row.items() if k != "payload"} for row in rows]
    failures = [row for row in validation if row.get("status") != "exact_match"]
    summary = {
        "base_rpf": str(BASE_RPF),
        "base_sha1": sha1_file(BASE_RPF),
        "output_rpf": str(OUTPUT_RPF),
        "output_sha1": sha1_file(OUTPUT_RPF),
        "game_copy": str(GAME_COPY),
        "game_copy_sha1": sha1_file(GAME_COPY),
        "patch": patch_report,
        "manifest": manifest,
        "validation": validation,
        "readback_failures": len(failures),
        "build": build,
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    (REPORT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_csv(REPORT_ROOT / "manifest.csv", manifest)
    write_csv(REPORT_ROOT / "readback_validation.csv", validation)
    write_csv(REPORT_ROOT / "wsc_changed_offsets.csv", [patch_report])
    lines = [
        "# MP Manual Entry Pass 1",
        "",
        "This candidate restores the original conditional branch at decoded `pressstart.wsc` offset `0x43B`.",
        "That disables the forced automatic `net.EnterOnline` startup path while keeping the manual XML/menu MP routes available.",
        "",
        f"- base: `{summary['base_rpf']}`",
        f"- output: `{summary['output_rpf']}`",
        f"- game copy: `{summary['game_copy']}`",
        f"- output SHA1: `{summary['output_sha1']}`",
        f"- readback failures: `{summary['readback_failures']}`",
    ]
    (REPORT_ROOT / "build_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
