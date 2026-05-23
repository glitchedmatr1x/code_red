#!/usr/bin/env python3
"""Probe Pass 1 MP donor formats and stage isolated raw import folders.

This pass copies donor bytes only. It does not write an RPF, rename resources,
edit script bytecode, or implement format conversion.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import json
import re
import shutil
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_EXTS = {".wsc", ".sco", ".xsc", ".csc"}
HASH_RE = re.compile(r"^(?:0x)?[0-9a-fA-F]{8}$")
RSC85 = b"RSC\x85"
RSC86 = b"RSC\x86"
SWAPPED_RSC85 = b"\x85CSR"
SWAPPED_RSC86 = b"\x86CSR"
ZSTD = b"\x28\xB5\x2F\xFD"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fields or [])
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"


def ascii_preview(data: bytes) -> str:
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)


def path_family(path_text: str) -> str:
    normalized = path_text.replace("\\", "/").lower()
    if "/content/release64/" in normalized or "/content_extracted/release64/" in normalized:
        return "content/release64"
    if "/content/release/" in normalized or "/content_extracted/release/" in normalized:
        return "content/release"
    return "other"


def header_family(data: bytes) -> str:
    if data.startswith(RSC85):
        return "RSC85"
    if data.startswith(RSC86):
        return "RSC86"
    if data.startswith(SWAPPED_RSC85):
        return "XSC_SWAPPED_RSC85"
    if data.startswith(SWAPPED_RSC86):
        return "CSC_SWAPPED_RSC86"
    if data.startswith(b"#SC"):
        return "SC_SCRIPT_HEADER"
    if data.startswith(ZSTD):
        return "ZSTD_FRAME"
    return "other"


def resource_fields(data: bytes, family: str) -> dict[str, Any]:
    normalized = data
    if family in {"XSC_SWAPPED_RSC85", "CSC_SWAPPED_RSC86"}:
        full = len(data) // 4
        normalized = b"".join(data[index * 4 : index * 4 + 4][::-1] for index in range(full)) + data[full * 4 :]
    if not normalized.startswith((RSC85, RSC86)) or len(normalized) < 16:
        return {"resource_type": "", "resource_flag1_hex": "", "resource_flag2_hex": ""}
    resource_type, flag1, flag2 = struct.unpack_from("<III", normalized, 4)
    return {"resource_type": resource_type, "resource_flag1_hex": f"0x{flag1:08X}", "resource_flag2_hex": f"0x{flag2:08X}"}


def probe(path: Path, source: str, relative_path: str = "") -> dict[str, Any]:
    data = path.read_bytes()
    first_512 = data[:512]
    family = header_family(data)
    zstd_offset = first_512.find(ZSTD)
    payload_note = {
        "RSC85": "resource wrapper; payload is normally encrypted before compressed bytes are visible",
        "RSC86": "resource wrapper; version differs from the RSC85 PC WSC examples checked here",
        "XSC_SWAPPED_RSC85": "32-bit word-swapped RSC85 family; not raw-PC-proven by extracted examples",
        "CSC_SWAPPED_RSC86": "32-bit word-swapped RSC86 family; PSN CSC raw import is not proven by extracted PC examples",
        "SC_SCRIPT_HEADER": "plain SC script header candidate",
        "ZSTD_FRAME": "zstd frame at file start",
    }.get(family, "header not in the known script wrapper families")
    return {
        "source": source,
        "path": str(path),
        "relative_path": relative_path,
        "path_family": path_family(str(path)),
        "name": path.name,
        "extension": path.suffix.lower(),
        "is_hash_named": bool(HASH_RE.match(path.name) or HASH_RE.match(path.stem)),
        "size": len(data),
        "size_mod_4": len(data) % 4,
        "header_family": family,
        "magic_hex_4": data[:4].hex(" ").upper(),
        "head_hex_16": data[:16].hex(" ").upper(),
        "head_hex_32": data[:32].hex(" ").upper(),
        "head_ascii_16": ascii_preview(data[:16]),
        "zstd_marker_in_first_512": zstd_offset >= 0,
        "zstd_marker_offset_in_first_512": zstd_offset if zstd_offset >= 0 else "",
        "compression_encryption_note": payload_note,
        "sha1": sha1_bytes(data),
        "crc32": crc32_bytes(data),
        **resource_fields(data, family),
    }


def current_pc_rows(pc_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((item for item in pc_root.rglob("*") if item.is_file()), key=lambda item: item.as_posix().lower()):
        if path.suffix.lower() not in SCRIPT_EXTS and not (HASH_RE.match(path.name) or HASH_RE.match(path.stem)):
            continue
        rows.append(probe(path, "pc_current", path.relative_to(pc_root).as_posix()))
    return rows


def mp_relative(path_text: str) -> Path:
    normalized = path_text.replace("\\", "/")
    marker = "/multiplayer/"
    low = normalized.lower()
    if marker not in low:
        raise ValueError(f"Path is not under multiplayer: {path_text}")
    return Path(normalized[low.index(marker) + len(marker) :])


def xenon_xsc_rows(xenon_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(xenon_root.rglob("*.xsc"), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(xenon_root).as_posix()
        if "/multiplayer/" not in f"/{relative.lower()}":
            continue
        row = probe(path, "donor_xenon_xsc", relative)
        row["logical_key"] = mp_relative(str(path)).with_suffix("").as_posix().lower()
        row["multiplayer_relative_path"] = mp_relative(str(path)).as_posix()
        rows.append(row)
    return rows


def selected_csc_rows(selection_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in read_csv(selection_path):
        if raw["extension"].lower() != ".csc":
            continue
        source = Path(raw["source_path"])
        row = probe(source, "donor_psn_selected_csc", raw["relative_path"])
        row["logical_key"] = raw["logical_key"]
        row["multiplayer_relative_path"] = raw["multiplayer_relative_path"]
        row["pass1_selection_reason"] = raw["selection_reason"]
        rows.append(row)
    return rows


def source_format_summary(rows: list[dict[str, Any]]) -> str:
    counts = Counter(str(row["header_family"]) for row in rows)
    return " | ".join(f"{name}:{count}" for name, count in sorted(counts.items()))


def logical_comparison(csc_rows: list[dict[str, Any]], xsc_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    xsc_by_key = {str(row["logical_key"]): row for row in xsc_rows}
    output: list[dict[str, Any]] = []
    for csc in csc_rows:
        xsc = xsc_by_key.get(str(csc["logical_key"]))
        output.append(
            {
                "logical_key": csc["logical_key"],
                "csc_path": csc["path"],
                "csc_size": csc["size"],
                "csc_size_mod_4": csc["size_mod_4"],
                "csc_header_family": csc["header_family"],
                "csc_head_hex_16": csc["head_hex_16"],
                "csc_compression_encryption_note": csc["compression_encryption_note"],
                "csc_resource_type": csc["resource_type"],
                "csc_resource_flag1_hex": csc["resource_flag1_hex"],
                "csc_resource_flag2_hex": csc["resource_flag2_hex"],
                "csc_sha1": csc["sha1"],
                "csc_crc32": csc["crc32"],
                "xsc_path": xsc["path"] if xsc else "",
                "xsc_size": xsc["size"] if xsc else "",
                "xsc_size_mod_4": xsc["size_mod_4"] if xsc else "",
                "xsc_header_family": xsc["header_family"] if xsc else "",
                "xsc_head_hex_16": xsc["head_hex_16"] if xsc else "",
                "xsc_compression_encryption_note": xsc["compression_encryption_note"] if xsc else "",
                "xsc_resource_type": xsc["resource_type"] if xsc else "",
                "xsc_resource_flag1_hex": xsc["resource_flag1_hex"] if xsc else "",
                "xsc_resource_flag2_hex": xsc["resource_flag2_hex"] if xsc else "",
                "xsc_sha1": xsc["sha1"] if xsc else "",
                "xsc_crc32": xsc["crc32"] if xsc else "",
                "headers_match": bool(xsc and csc["header_family"] == xsc["header_family"]),
                "bytes_match": bool(xsc and csc["sha1"] == xsc["sha1"]),
            }
        )
    return output


def copy_checked(source: Path, target: Path, package: str, logical_key: str) -> dict[str, Any]:
    source_data = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target_data = target.read_bytes()
    return {
        "package": package,
        "logical_key": logical_key,
        "donor_path": str(source),
        "staged_path": str(target),
        "staged_content_path": target.as_posix().split("/mp_content_restore_pass2/", 1)[-1].replace("\\", "/"),
        "donor_size": len(source_data),
        "staged_size": len(target_data),
        "donor_sha1": sha1_bytes(source_data),
        "staged_sha1": sha1_bytes(target_data),
        "donor_crc32": crc32_bytes(source_data),
        "staged_crc32": crc32_bytes(target_data),
        "sha1_match": sha1_bytes(source_data) == sha1_bytes(target_data),
        "crc32_match": crc32_bytes(source_data) == crc32_bytes(target_data),
        "raw_copy_bytes_match": source_data == target_data,
    }


def stage_packages(build_root: Path, csc_rows: list[dict[str, Any]], xsc_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preservation: list[dict[str, Any]] = []
    package_roots = {
        "import_test_release_csc": build_root / "import_test_release_csc",
        "import_test_release64_csc": build_root / "import_test_release64_csc",
        "import_test_both_csc": build_root / "import_test_both_csc",
        "import_test_xsc_review": build_root / "import_test_xsc_review",
    }
    for row in csc_rows:
        source = Path(str(row["path"]))
        relative = Path(str(row["multiplayer_relative_path"]))
        destinations = (
            ("import_test_release_csc", Path("content") / "release" / "multiplayer" / relative),
            ("import_test_release64_csc", Path("content") / "release64" / "multiplayer" / relative),
            ("import_test_both_csc", Path("content") / "release" / "multiplayer" / relative),
            ("import_test_both_csc", Path("content") / "release64" / "multiplayer" / relative),
        )
        for package, relative_target in destinations:
            preservation.append(copy_checked(source, package_roots[package] / relative_target, package, str(row["logical_key"])))
    for row in xsc_rows:
        source = Path(str(row["path"]))
        relative = Path(str(row["multiplayer_relative_path"]))
        preservation.append(
            copy_checked(
                source,
                package_roots["import_test_xsc_review"] / "content" / "release64" / "multiplayer" / relative,
                "import_test_xsc_review",
                str(row["logical_key"]),
            )
        )
    for package, root in package_roots.items():
        if package == "import_test_release_csc":
            (root / "content" / "release" / "multiplayer").mkdir(parents=True, exist_ok=True)
        elif package == "import_test_release64_csc" or package == "import_test_xsc_review":
            (root / "content" / "release64" / "multiplayer").mkdir(parents=True, exist_ok=True)
        else:
            (root / "content" / "release" / "multiplayer").mkdir(parents=True, exist_ok=True)
            (root / "content" / "release64" / "multiplayer").mkdir(parents=True, exist_ok=True)
    return preservation


def compatibility_rows(
    pc_rows: list[dict[str, Any]],
    csc_rows: list[dict[str, Any]],
    xsc_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pc_extensions = Counter(str(row["extension"]) for row in pc_rows)
    pc_families = Counter(str(row["header_family"]) for row in pc_rows)
    pc_release64_only = pc_extensions.get(".csc", 0) == 0 and pc_extensions.get(".xsc", 0) == 0
    output: list[dict[str, Any]] = []
    for row in csc_rows:
        matches_pc_family = pc_families.get(str(row["header_family"]), 0) > 0
        status = "raw_import_ready" if matches_pc_family else "raw_import_candidate"
        output.append(
            {
                "candidate_kind": "pass1_psn_csc",
                "logical_key": row["logical_key"],
                "path": row["path"],
                "extension": row["extension"],
                "header_family": row["header_family"],
                "classification": status,
                "pc_family_match": matches_pc_family,
                "decision": "stage raw in isolated CSC import packages; verify Magic RDR re-export before launch",
                "format_reason": (
                    "CSC donor wrapper family appears in current extracted PC examples"
                    if matches_pc_family
                    else "CSC donor header family is not observed in current extracted PC WSC/SCO examples"
                ),
            }
        )
    for row in xsc_rows:
        has_pc_xsc = pc_extensions.get(".xsc", 0) > 0
        if has_pc_xsc and pc_families.get(str(row["header_family"]), 0) > 0:
            status = "xsc_better_candidate"
            decision = "PC XSC examples exist; keep XSC review candidate before conversion"
        elif row["header_family"] == "XSC_SWAPPED_RSC85" and pc_release64_only:
            status = "conversion_blocked"
            decision = "word-swapped XSC wrapper is review-only until PC loader/import accepts raw XSC or a validated rewrap is proven"
        else:
            status = "manual_review"
            decision = "XSC raw path is separated for format/import review"
        output.append(
            {
                "candidate_kind": "xenon_xsc_review",
                "logical_key": row["logical_key"],
                "path": row["path"],
                "extension": row["extension"],
                "header_family": row["header_family"],
                "classification": status,
                "pc_family_match": pc_families.get(str(row["header_family"]), 0) > 0,
                "decision": decision,
                "format_reason": "current extracted PC tree has XSC examples" if has_pc_xsc else "current extracted PC tree exposes WSC/SCO, not XSC",
            }
        )
    return output


def conversion_markdown(rows: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["classification"])].append(row)
    lines = [
        "# Multiplayer Restore Pass 2 Conversion Status",
        "",
        "No conversion was performed in Pass 2. Raw import/path testing is still preferred.",
        "",
    ]
    for status in ("conversion_needed", "conversion_blocked", "xsc_better_candidate", "manual_review", "raw_import_candidate", "raw_import_ready"):
        matches = grouped.get(status, [])
        lines.extend([f"## {status}", "", f"- Files: `{len(matches)}`"])
        for row in matches[:80]:
            lines.append(f"- `{row['logical_key']}` `{row['extension']}` - {row['decision']}")
        if not matches:
            lines.append("- None.")
        lines.append("")
    lines.extend(
        [
            "## Rule",
            "",
            "Do not fake `.sco`, `.csc`, or `.xsc` conversion by renaming an extension. Promote a conversion only after the target container can be reopened and the PC loader path is proven.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def checklist_markdown() -> str:
    return "\n".join(
        [
            "# Magic RDR Import Verification Checklist",
            "",
            "Use one isolated Pass 2 package per copied archive test.",
            "",
            "1. Back up the target PC `content.rpf` and work on a copy.",
            "2. Choose exactly one package: `import_test_release_csc`, `import_test_release64_csc`, or `import_test_both_csc`.",
            "3. Import raw files into the matching internal content paths. Do not mix in `import_test_xsc_review` during the first CSC test.",
            "4. Save the copied RPF and immediately reopen it in Magic RDR before launching the game.",
            "5. Verify the expected internal `content/release.../multiplayer/` paths exist after reopen.",
            "6. Export representative imports back out: `mp_idle.csc`, `multiplayer_update_thread.csc`, `freemode/freemode.csc`, and one region/action-area file.",
            "7. Compare exported SHA1 and CRC32 against `raw_byte_preservation_report.csv` or the donor file. Record whether Magic RDR changed payload bytes.",
            "8. If reopen or export comparison fails, stop. Mark that package rejected before any launch test.",
            "9. Launch only after RPF reopen and export-byte verification pass.",
            "10. Record the package name, internal paths tested, exported hashes, boot result, pause/menu result, and any loader log/crash.",
            "",
            "For the XSC review package, keep it separate until raw XSC import behavior or a validated rewrap path is proven.",
            "",
        ]
    ) + "\n"


def package_plan_markdown(build_root: Path, csc_rows: list[dict[str, Any]], xsc_rows: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "# Multiplayer Restore Pass 2 Import Package Plan",
            "",
            "Each package keeps donor bytes raw and isolates path/format variables.",
            "",
            f"- `import_test_release_csc`: `{build_root / 'import_test_release_csc'}`",
            "  - `content/release/multiplayer/`",
            f"  - PSN CSC files: `{len(csc_rows)}`",
            f"- `import_test_release64_csc`: `{build_root / 'import_test_release64_csc'}`",
            "  - `content/release64/multiplayer/`",
            f"  - PSN CSC files: `{len(csc_rows)}`",
            f"- `import_test_both_csc`: `{build_root / 'import_test_both_csc'}`",
            "  - both release path families",
            f"  - PSN CSC copies: `{len(csc_rows) * 2}`",
            f"- `import_test_xsc_review`: `{build_root / 'import_test_xsc_review'}`",
            "  - `content/release64/multiplayer/` only",
            f"  - XENON XSC review files: `{len(xsc_rows)}`",
            "",
            "Do not import the XSC review package together with the CSC packages in the first compatibility test.",
            "",
        ]
    ) + "\n"


def compatibility_markdown(
    pc_rows: list[dict[str, Any]],
    csc_rows: list[dict[str, Any]],
    xsc_rows: list[dict[str, Any]],
    compat: list[dict[str, Any]],
    preservation: list[dict[str, Any]],
) -> str:
    ext_counts = Counter(str(row["extension"]) or "(no ext)" for row in pc_rows)
    family_counts = Counter(str(row["header_family"]) for row in pc_rows)
    path_counts = Counter(str(row["path_family"]) for row in pc_rows)
    statuses = Counter(str(row["classification"]) for row in compat)
    preservation_ok = all(bool(row["raw_copy_bytes_match"]) for row in preservation)
    return "\n".join(
        [
            "# Code RED Multiplayer Content Restore Pass 2 Format Compatibility",
            "",
            "Pass 2 probes wrappers and raw import folder copies only. No RPF or compiled script logic is changed.",
            "",
            "## Current PC examples",
            "",
            f"- Current extracted script/hash rows scanned: `{len(pc_rows)}`",
            f"- Extensions: `{' | '.join(f'{key}:{value}' for key, value in sorted(ext_counts.items()))}`",
            f"- Header families: `{' | '.join(f'{key}:{value}' for key, value in sorted(family_counts.items()))}`",
            f"- Path families: `{' | '.join(f'{key}:{value}' for key, value in sorted(path_counts.items()))}`",
            "",
            "The extracted PC tree inspected here exposes comparable compiled scripts under `content/release64` as WSC/SCO resources. Pass 2 does not assume donor CSC or XSC is accepted by the PC loader until import/export verification proves it.",
            "",
            "## Donor compatibility result",
            "",
            f"- Pass 1 selected PSN CSC files probed: `{len(csc_rows)}`",
            f"- XENON XSC review files probed: `{len(xsc_rows)}`",
            f"- CSC headers: `{source_format_summary(csc_rows)}`",
            f"- XSC headers: `{source_format_summary(xsc_rows)}`",
            f"- File classifications: `{' | '.join(f'{key}:{value}' for key, value in sorted(statuses.items()))}`",
            "",
            "Current evidence keeps the Pass 1 CSC payloads as isolated raw import candidates, not proven PC-ready files: they are swapped RSC86 while current extracted PC WSC examples are RSC85. The XENON XSC donor is version-closer to PC at swapped RSC85, but raw XSC paths are not present in the extracted PC examples checked here, so it stays in the separate review lane until raw import or validated rewrap is proven.",
            "",
            "## Byte preservation",
            "",
            f"- Raw copies checked: `{len(preservation)}`",
            f"- Every staged copy byte-matches donor: `{preservation_ok}`",
            "",
            "Magic RDR post-import export verification is still required. Folder-copy hash preservation does not prove RPF import behavior.",
            "",
        ]
    ) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    reports = Path(args.reports)
    build_root = Path(args.build)
    pc_root = Path(args.pc_content)
    selection = Path(args.pass1_selection)
    xenon = Path(args.xenon)
    pc_rows = current_pc_rows(pc_root)
    csc_rows = selected_csc_rows(selection)
    xsc_rows = xenon_xsc_rows(xenon)
    comparisons = logical_comparison(csc_rows, xsc_rows)
    preservation = stage_packages(build_root, csc_rows, xsc_rows)
    compat = compatibility_rows(pc_rows, csc_rows, xsc_rows)
    write_csv(reports / "current_pc_script_format_examples.csv", pc_rows)
    write_csv(reports / "donor_csc_vs_xsc_comparison.csv", comparisons)
    write_csv(reports / "raw_byte_preservation_report.csv", preservation)
    write_csv(reports / "pass2_format_compatibility_report.csv", compat)
    write_text(reports / "pass2_format_compatibility_report.md", compatibility_markdown(pc_rows, csc_rows, xsc_rows, compat, preservation))
    write_text(reports / "import_test_package_plan.md", package_plan_markdown(build_root, csc_rows, xsc_rows))
    write_text(reports / "conversion_needed_files.md", conversion_markdown(compat))
    write_text(reports / "magic_rdr_import_verification_checklist.md", checklist_markdown())
    summary = {
        "tool": "codered_mp_content_restore_pass2",
        "current_pc_rows": len(pc_rows),
        "selected_psn_csc_rows": len(csc_rows),
        "xenon_xsc_review_rows": len(xsc_rows),
        "compatibility_rows": len(compat),
        "raw_copy_rows": len(preservation),
        "raw_copy_all_bytes_match": all(bool(row["raw_copy_bytes_match"]) for row in preservation),
        "reports": str(reports),
        "build_root": str(build_root),
        "status_counts": dict(Counter(str(row["classification"]) for row in compat)),
        "no_rpf_write": True,
        "no_bytecode_edit": True,
        "no_extension_conversion": True,
    }
    write_text(reports / "pass2_format_compatibility_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe MP donor format compatibility and stage isolated raw import packages.")
    parser.add_argument("--pc-content", default=str(ROOT / "game" / "content_extracted"))
    parser.add_argument("--xenon", default=str(ROOT / "imports" / "XENON MULTIPLAYER" / "content"))
    parser.add_argument("--pass1-selection", default=str(ROOT / "logs" / "mp_content_restore_pass1" / "restore_selection_manifest.csv"))
    parser.add_argument("--reports", default=str(ROOT / "reports"))
    parser.add_argument("--build", default=str(ROOT / "build" / "mp_content_restore_pass2"))
    args = parser.parse_args(argv)
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
