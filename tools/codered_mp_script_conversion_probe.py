#!/usr/bin/env python3
"""Probe CSC/XSC -> WSC conversion lanes for restored RDR multiplayer scripts.

This tool is intentionally conservative:
- XENON .xsc files are 32-bit word-swapped RSC85 resources. The tool can write
  a PC-header .wsc wrapper candidate by swapping only the 16-byte resource
  header. The encrypted payload must stay byte-for-byte intact.
- PSN .csc files are 32-bit word-swapped RSC86 resources. The tool does not
  rename those to WSC or pretend they are PC-compatible.
- Every written XSC candidate is reopened through Code RED's WSC reader. If the
  payload cannot decode, the output is marked wrapper-only, not runtime-ready.

No RPFs or live game files are modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codered_wsc.resource import KeyOptions, ResourceError, normalize_xsc_resource, open_script, swap32
DEFAULT_XSC_SOURCE = ROOT / "imports" / "XENON MULTIPLAYER" / "content" / "release64" / "multiplayer"
DEFAULT_CSC_SOURCE = ROOT / "imports" / "PSN MULTIPLAYER" / "content" / "release64" / "multiplayer"
DEFAULT_OUT = ROOT / "build" / "mp_script_conversion_probe"
DEFAULT_REPORTS = ROOT / "reports" / "mp_script_conversion_probe"
SCRIPT_LIMIT_NAMES = {
    "freemode",
    "multiplayer_system_thread",
    "pr_multiplayer",
    "mp_idle",
    "multiplayer_update_thread",
    "deathmatch",
    "ctf_base_game",
    "mp_actorpicker",
    "gametype_lobby",
}


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def family(data: bytes) -> str:
    if data.startswith(b"RSC\x85"):
        return "PC_RSC85_WSC"
    if data.startswith(b"\x85CSR"):
        return "XSC_SWAPPED_RSC85"
    if data.startswith(b"RSC\x86"):
        return "RSC86_REVIEW"
    if data.startswith(b"\x86CSR"):
        return "CSC_SWAPPED_RSC86"
    if data.startswith(b"SCR"):
        return "SCR_STYLE_SCO"
    return "unknown"


def collect(source: Path, suffix: str) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() == suffix else []
    if not source.exists():
        return []
    return sorted((p for p in source.rglob(f"*{suffix}") if p.is_file()), key=lambda p: str(p).lower())


def relative_under(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(path.name)


def should_include(path: Path, focused: bool) -> bool:
    if not focused:
        return True
    return path.stem.lower() in SCRIPT_LIMIT_NAMES


def validate_wsc(path: Path, rdr_exe: str) -> dict[str, Any]:
    try:
        resource = open_script(path, KeyOptions(rdr_exe=rdr_exe))
        return {
            "open_status": "opened",
            "family": resource.header.family,
            "normalized_from_xsc": resource.header.normalized_from_xsc,
            "compression": resource.header.compression,
            "decode_error": resource.decode_error,
            "decoded_size": len(resource.decoded),
            "decoded_sha256": resource.header_dict()["decoded_sha256"],
            "conversion_status": "converted_decode_ok" if resource.decoded else "wrapper_converted_decode_blocked",
        }
    except ResourceError as exc:
        return {
            "open_status": "blocked",
            "family": "",
            "normalized_from_xsc": False,
            "compression": "",
            "decode_error": str(exc),
            "decoded_size": 0,
            "decoded_sha256": "",
            "conversion_status": "wrapper_converted_decode_blocked",
        }


def probe_xsc(path: Path, source_root: Path, out_root: Path, rdr_exe: str) -> dict[str, Any]:
    data = path.read_bytes()
    rel = relative_under(path, source_root)
    dst_rel = rel.with_suffix(".wsc")
    dst = out_root / "xsc_swapped_wsc_candidates" / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)

    rec: dict[str, Any] = {
        "source_kind": "xenon_xsc",
        "source": str(path),
        "relative_path": str(rel).replace("\\", "/"),
        "source_size": len(data),
        "source_sha1": sha1_file(path),
        "source_head_16": data[:16].hex(" ").upper(),
        "source_family": family(data),
        "output": str(dst),
        "output_relative_path": str(dst_rel).replace("\\", "/"),
        "output_written": False,
        "output_size": 0,
        "output_sha1": "",
        "output_head_16": "",
    }
    if not data.startswith(b"\x85CSR"):
        rec.update({"conversion_status": "not_xsc_swapped_rsc85", "decode_error": "input header was not 85 43 53 52"})
        return rec

    converted = normalize_xsc_resource(data)
    dst.write_bytes(converted)
    rec.update(
        {
            "output_written": True,
            "output_size": len(converted),
            "output_sha1": sha1_file(dst),
            "output_head_16": converted[:16].hex(" ").upper(),
            "output_family": family(converted),
        }
    )
    rec.update(validate_wsc(dst, rdr_exe))
    return rec


def probe_csc(path: Path, source_root: Path, out_root: Path, write_review: bool) -> dict[str, Any]:
    data = path.read_bytes()
    rel = relative_under(path, source_root)
    rec: dict[str, Any] = {
        "source_kind": "psn_csc",
        "source": str(path),
        "relative_path": str(rel).replace("\\", "/"),
        "source_size": len(data),
        "source_sha1": sha1_file(path),
        "source_head_16": data[:16].hex(" ").upper(),
        "source_family": family(data),
        "output": "",
        "output_relative_path": "",
        "output_written": False,
        "output_size": 0,
        "output_sha1": "",
        "output_head_16": "",
        "output_family": "",
        "open_status": "not_attempted",
        "compression": "",
        "decode_error": "PSN CSC is swapped RSC86, not a PC RSC85 WSC. Conversion is source/recompiler or dedicated RSC86 path required.",
        "decoded_size": 0,
        "decoded_sha256": "",
        "conversion_status": "rsc86_conversion_blocked",
    }
    if write_review and data.startswith(b"\x86CSR"):
        dst_rel = rel.with_suffix(".rsc86.review")
        dst = out_root / "csc_swapped_rsc86_review" / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        converted = swap32(data)
        dst.write_bytes(converted)
        rec.update(
            {
                "output": str(dst),
                "output_relative_path": str(dst_rel).replace("\\", "/"),
                "output_written": True,
                "output_size": len(converted),
                "output_sha1": sha1_file(dst),
                "output_head_16": converted[:16].hex(" ").upper(),
                "output_family": family(converted),
            }
        )
    return rec


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_reports(report_root: Path, out_root: Path, rows: list[dict[str, Any]], focused: bool) -> None:
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "conversion_probe.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_csv(report_root / "conversion_probe.csv", rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["conversion_status"]] = counts.get(row["conversion_status"], 0) + 1

    ready = [r for r in rows if r["conversion_status"] == "converted_decode_ok"]
    wrapper_only = [r for r in rows if r["conversion_status"] == "wrapper_converted_decode_blocked"]
    lines = [
        "# MP Script CSC/XSC -> WSC Conversion Probe",
        "",
        "No RPFs or live game files were modified.",
        "",
        f"- Build output: `{out_root}`",
        f"- Focused core-script mode: `{focused}`",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(
        [
            "",
            "## Result",
            "",
            f"- Decode-ready WSC conversions: `{len(ready)}`",
            f"- XSC byte-swapped WSC wrapper candidates that still failed payload decode: `{len(wrapper_only)}`",
            "",
            "The current practical path is still source/authoring via SC-CL for new WSCs. Donor XENON .xsc files can be converted to a PC-looking RSC85/WSC wrapper by 32-bit word-swap, but the payload did not become Code RED-decodable with the available PC AES/Zstd/zlib lanes. PSN .csc files are RSC86 and are not converted to WSC by this pass.",
            "",
            "## Next Technical Blockers",
            "",
            "- Identify the correct XENON script payload key/transform if it differs from the PC RDR AES key.",
            "- Build or obtain a callable XCompress/LZX bridge for the local toolchain, then validate payload decode/repack.",
            "- If source/pseudocode is available, compile with SC-CL `-target=RDR_SCO` and wrap into PC RSC85 WSC using the existing Code RED authoring lane.",
            "",
            "## Core Outputs",
            "",
        ]
    )
    for row in rows:
        if Path(row["relative_path"]).stem.lower() in SCRIPT_LIMIT_NAMES:
            lines.append(
                f"- `{row['source_kind']}` `{row['relative_path']}` -> `{row['conversion_status']}` output=`{row.get('output_relative_path', '')}` error=`{row.get('decode_error', '')}`"
            )
    (report_root / "conversion_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe safe CSC/XSC to WSC conversion candidates for RDR MP scripts.")
    parser.add_argument("--xsc-source", default=str(DEFAULT_XSC_SOURCE))
    parser.add_argument("--csc-source", default=str(DEFAULT_CSC_SOURCE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--reports", default=str(DEFAULT_REPORTS))
    parser.add_argument("--rdr-exe", default=str(ROOT.parent / "RDR.exe"))
    parser.add_argument("--focused", action="store_true", help="Only process known core MP scripts.")
    parser.add_argument("--write-csc-review", action="store_true", help="Write swapped RSC86 review files, not WSC files.")
    parser.add_argument("--clean", action="store_true", help="Remove previous build output before writing candidates.")
    args = parser.parse_args()

    xsc_source = Path(args.xsc_source)
    csc_source = Path(args.csc_source)
    out_root = Path(args.out)
    report_root = Path(args.reports)
    if args.clean and out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for path in collect(xsc_source, ".xsc"):
        if should_include(path, args.focused):
            rows.append(probe_xsc(path, xsc_source, out_root, args.rdr_exe))
    for path in collect(csc_source, ".csc"):
        if should_include(path, args.focused):
            rows.append(probe_csc(path, csc_source, out_root, args.write_csc_review))

    write_reports(report_root, out_root, rows, args.focused)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["conversion_status"]] = counts.get(row["conversion_status"], 0) + 1
    print(json.dumps({"status": "complete", "rows": len(rows), "counts": counts, "out": str(out_root), "reports": str(report_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
