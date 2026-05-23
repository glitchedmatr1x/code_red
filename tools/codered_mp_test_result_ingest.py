#!/usr/bin/env python3
"""Ingest Code RED MP restore test results and choose the next safe lane.

This tool maintains manual CSV worksheets and verifies exported-back files
against already-staged Pass 2 package bytes. It never writes content.rpf,
patches compiled scripts, or converts script wrappers.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

LANES = [
    {
        "lane_id": "A",
        "lane_name": "baseline_no_mp_restore",
        "imported_package": "",
        "package_kind": "baseline",
        "import_target": "clean backup / no MP restore",
        "purpose": "baseline UI and error path",
        "approved_for_import": "yes",
    },
    {
        "lane_id": "B",
        "lane_name": "release64_csc_only",
        "imported_package": "import_test_release64_csc",
        "package_kind": "csc",
        "import_target": "content/release64/multiplayer/",
        "purpose": "PC-comparable release64 path",
        "approved_for_import": "yes",
    },
    {
        "lane_id": "C",
        "lane_name": "release_csc_only",
        "imported_package": "import_test_release_csc",
        "package_kind": "csc",
        "import_target": "content/release/multiplayer/",
        "purpose": "legacy release path",
        "approved_for_import": "yes",
    },
    {
        "lane_id": "D",
        "lane_name": "both_release_and_release64_csc",
        "imported_package": "import_test_both_csc",
        "package_kind": "csc",
        "import_target": "both CSC path families",
        "purpose": "path ambiguity isolation",
        "approved_for_import": "yes",
    },
    {
        "lane_id": "E",
        "lane_name": "xsc_review_only",
        "imported_package": "import_test_xsc_review",
        "package_kind": "xsc_review",
        "import_target": "review only until explicitly approved",
        "purpose": "XENON wrapper review lane",
        "approved_for_import": "no",
    },
]

RESULT_FIELDS = [
    "lane_id",
    "lane_name",
    "package_kind",
    "clean_content_rpf_backup_used",
    "imported_package",
    "import_target",
    "magic_rdr_reopen_result",
    "exported_back_folder_path",
    "exported_byte_compare_result",
    "launch_result",
    "menu_option_changes",
    "networking_screen_changes",
    "error_message_changes",
    "loading_behavior",
    "crash_hang_return_to_menu_behavior",
    "screenshots_video_notes",
    "crash_report_log_notes",
    "conclusion",
    "tested",
    "approved_for_import",
    "updated_at",
]

VERIFICATION_FIELDS = [
    "lane_id",
    "lane_name",
    "package",
    "package_kind",
    "content_path",
    "staged_path",
    "exported_back_folder",
    "export_path",
    "status",
    "staged_size",
    "export_size",
    "size_match",
    "staged_sha1",
    "export_sha1",
    "sha1_match",
    "staged_crc32",
    "export_crc32",
    "crc32_match",
    "note",
]

SIGNAL_FIELDS = [
    "menu_option_changes",
    "networking_screen_changes",
    "error_message_changes",
    "loading_behavior",
    "crash_hang_return_to_menu_behavior",
    "conclusion",
]

NO_SIGNAL_TOKENS = {
    "",
    "n/a",
    "na",
    "none",
    "same",
    "unchanged",
    "no",
    "no change",
    "no changes",
    "not tested",
    "untested",
    "pending",
}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def markdown_table(rows: list[list[str]], headers: list[str]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in row) + " |")
    return lines


def digest(path: Path) -> tuple[int, str, str]:
    sha = hashlib.sha1()
    crc = 0
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            sha.update(chunk)
            crc = binascii.crc32(chunk, crc)
    return size, sha.hexdigest().upper(), f"{crc & 0xFFFFFFFF:08X}"


def lane_map() -> dict[str, dict[str, str]]:
    return {lane["lane_name"]: lane for lane in LANES}


def results_template_row(lane: dict[str, str]) -> dict[str, str]:
    row = {field: "" for field in RESULT_FIELDS}
    row.update(
        {
            "lane_id": lane["lane_id"],
            "lane_name": lane["lane_name"],
            "package_kind": lane["package_kind"],
            "imported_package": lane["imported_package"],
            "import_target": lane["import_target"],
            "approved_for_import": lane["approved_for_import"],
            "tested": "",
        }
    )
    return row


def ensure_results(path: Path) -> list[dict[str, str]]:
    existing = read_csv(path)
    by_name = {row.get("lane_name", ""): row for row in existing if row.get("lane_name")}
    rows: list[dict[str, str]] = []
    for lane in LANES:
        base = results_template_row(lane)
        current = by_name.get(lane["lane_name"], {})
        for field in RESULT_FIELDS:
            if current.get(field, "") != "":
                base[field] = current[field]
        rows.append(base)
    write_csv(path, rows, RESULT_FIELDS)
    return rows


def ensure_manual_matrix(path: Path) -> None:
    if path.exists():
        return
    rows = [[lane["lane_id"], lane["lane_name"], lane["imported_package"] or "None", lane["import_target"], lane["purpose"]] for lane in LANES]
    lines = [
        "# Code RED MP Manual Test Matrix",
        "",
        "Use `reports/mp_test_results.csv` as the editable result ledger for Pass 4.",
        "",
        *markdown_table(rows, ["Lane", "Name", "Package", "Import target", "Purpose"]),
        "",
    ]
    write_text(path, "\n".join(lines) + "\n")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def is_truthy(text: str) -> bool:
    return normalized(text) in {"1", "true", "yes", "y", "tested", "pass", "passed", "approved"}


def row_tested(row: dict[str, str]) -> bool:
    if is_truthy(row.get("tested", "")):
        return True
    return any(normalized(row.get(field, "")) not in NO_SIGNAL_TOKENS for field in ("launch_result", "conclusion", "magic_rdr_reopen_result"))


def meaningful_signal_text(text: str) -> bool:
    value = normalized(text)
    return value not in NO_SIGNAL_TOKENS and value != ""


def row_has_runtime_signal(row: dict[str, str]) -> bool:
    return any(meaningful_signal_text(row.get(field, "")) for field in SIGNAL_FIELDS)


def package_files(package_root: Path) -> list[Path]:
    if not package_root.exists():
        return []
    return sorted((path for path in package_root.rglob("*") if path.is_file()), key=lambda path: path.as_posix().lower())


def find_export_path(export_root: Path, staged_root: Path, staged: Path) -> tuple[Path | None, str]:
    content_path = staged.relative_to(staged_root)
    direct = export_root / content_path
    if direct.exists():
        return direct, "same relative content path"
    parts = list(content_path.parts)
    if "multiplayer" in [part.lower() for part in parts]:
        index = [part.lower() for part in parts].index("multiplayer")
        multiplayer_tail = Path(*parts[index + 1 :])
        candidate = export_root / multiplayer_tail
        if candidate.exists():
            return candidate, "multiplayer-relative export path"
    same_name = sorted(export_root.rglob(staged.name), key=lambda path: path.as_posix().lower())
    if len(same_name) == 1:
        return same_name[0], "unique basename fallback"
    if len(same_name) > 1:
        return None, f"ambiguous export basename candidates={len(same_name)}"
    return None, "missing export"


def default_export_root(reports: Path, lane_name: str) -> Path:
    return reports / "mp_content_restore_pass4" / "exported_back" / lane_name


def verify_exports(results: list[dict[str, str]], pass2_packages: Path, reports: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        lane = lane_map()[result["lane_name"]]
        package_name = result.get("imported_package", "") or lane["imported_package"]
        if not package_name:
            rows.append(
                {
                    "lane_id": lane["lane_id"],
                    "lane_name": lane["lane_name"],
                    "package_kind": lane["package_kind"],
                    "status": "not_applicable",
                    "note": "baseline lane has no imported package",
                }
            )
            continue
        staged_root = pass2_packages / package_name
        export_root_text = result.get("exported_back_folder_path", "").strip()
        export_root = Path(export_root_text) if export_root_text else default_export_root(reports, lane["lane_name"])
        staged_files = package_files(staged_root)
        if lane["package_kind"] == "xsc_review" and not is_truthy(result.get("approved_for_import", "")):
            rows.append(
                {
                    "lane_id": lane["lane_id"],
                    "lane_name": lane["lane_name"],
                    "package": package_name,
                    "package_kind": lane["package_kind"],
                    "exported_back_folder": str(export_root),
                    "status": "review_only_not_approved",
                    "note": "xsc_review_only stays review-only until explicitly approved",
                }
            )
            continue
        if not staged_files:
            rows.append(
                {
                    "lane_id": lane["lane_id"],
                    "lane_name": lane["lane_name"],
                    "package": package_name,
                    "package_kind": lane["package_kind"],
                    "exported_back_folder": str(export_root),
                    "status": "staged_package_missing",
                    "note": "Pass 2 staged package folder missing",
                }
            )
            continue
        if not export_root.exists():
            rows.append(
                {
                    "lane_id": lane["lane_id"],
                    "lane_name": lane["lane_name"],
                    "package": package_name,
                    "package_kind": lane["package_kind"],
                    "exported_back_folder": str(export_root),
                    "status": "export_folder_missing",
                    "note": f"expected exported-back folder for {len(staged_files)} staged files",
                }
            )
            continue
        for staged in staged_files:
            content_path = staged.relative_to(staged_root).as_posix()
            exported, note = find_export_path(export_root, staged_root, staged)
            staged_size, staged_sha1, staged_crc = digest(staged)
            row: dict[str, Any] = {
                "lane_id": lane["lane_id"],
                "lane_name": lane["lane_name"],
                "package": package_name,
                "package_kind": lane["package_kind"],
                "content_path": content_path,
                "staged_path": str(staged),
                "exported_back_folder": str(export_root),
                "staged_size": staged_size,
                "staged_sha1": staged_sha1,
                "staged_crc32": staged_crc,
                "note": note,
            }
            if exported is None:
                row["status"] = "missing_export" if note == "missing export" else "manual_review"
                rows.append(row)
                continue
            export_size, export_sha1, export_crc = digest(exported)
            row.update(
                {
                    "export_path": str(exported),
                    "export_size": export_size,
                    "size_match": staged_size == export_size,
                    "export_sha1": export_sha1,
                    "sha1_match": staged_sha1 == export_sha1,
                    "export_crc32": export_crc,
                    "crc32_match": staged_crc == export_crc,
                }
            )
            if staged_sha1 == export_sha1 and staged_crc == export_crc and staged_size == export_size:
                row["status"] = "exact_match"
            elif staged_size != export_size:
                row["status"] = "changed_size"
            else:
                row["status"] = "changed_bytes"
            rows.append(row)
    return rows


def verification_counts(rows: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(row.get("lane_name", ""))][str(row.get("status", ""))] += 1
    return grouped


def all_verified_exact(rows: list[dict[str, Any]], lane_name: str) -> bool:
    relevant = [row for row in rows if row.get("lane_name") == lane_name]
    exact_rows = [row for row in relevant if row.get("status") == "exact_match"]
    blocking = {
        "changed_bytes",
        "changed_size",
        "export_folder_missing",
        "manual_review",
        "staged_package_missing",
    }
    return bool(exact_rows) and not any(row.get("status") in blocking for row in relevant)


def first_untested_csc(results: list[dict[str, str]]) -> str | None:
    for lane_name in ("baseline_no_mp_restore", "release64_csc_only", "release_csc_only", "both_release_and_release64_csc"):
        row = next(row for row in results if row["lane_name"] == lane_name)
        if not row_tested(row):
            return lane_name
    return None


def row_blob(row: dict[str, str]) -> str:
    return " ".join(normalized(row.get(field, "")) for field in RESULT_FIELDS)


def decision(results: list[dict[str, str]], verification: list[dict[str, Any]]) -> dict[str, str]:
    by_lane = {row["lane_name"]: row for row in results}
    csc_names = ("release64_csc_only", "release_csc_only", "both_release_and_release64_csc")
    untested = first_untested_csc(results)
    signals = {name: row_has_runtime_signal(by_lane[name]) for name in csc_names}
    tested = {name: row_tested(by_lane[name]) for name in csc_names}
    csc_blobs = " ".join(row_blob(by_lane[name]) for name in csc_names if tested[name])
    exact_csc = {name: all_verified_exact(verification, name) for name in csc_names}
    verify_states = Counter(str(row.get("status", "")) for row in verification)
    if untested:
        return {
            "classification": "do_not_patch_yet",
            "next_action_choice": "keep testing CSC",
            "next_lane": untested,
            "reason": "manual evidence is incomplete; establish the next baseline/CSC lane before selecting a patch",
        }
    if "hidden" in csc_blobs or "not visible" in csc_blobs or "lan tab missing" in csc_blobs:
        return {
            "classification": "likely_ui_hidden_blocker",
            "next_action_choice": "patch a UI-hidden local LAN route",
            "next_lane": "hold matrix after confirming UI evidence",
            "reason": "manual notes describe a local LAN UI visibility blocker",
        }
    if any(token in csc_blobs for token in ("auth", "sign in", "signin", "profile", "xbox live")):
        return {
            "classification": "likely_auth_gate_blocker",
            "next_action_choice": "stop because no signal exists yet",
            "next_lane": "report-only auth review",
            "reason": "manual notes point at authentication/profile gating; external-auth bypass is out of scope",
        }
    if signals["release64_csc_only"] and not signals["release_csc_only"]:
        return {
            "classification": "release64_has_signal",
            "next_action_choice": "keep testing CSC",
            "next_lane": "both_release_and_release64_csc",
            "reason": "release64 lane changed observable behavior and should be isolated against the both-path lane",
        }
    if signals["release_csc_only"] and not signals["release64_csc_only"]:
        return {
            "classification": "release_has_signal",
            "next_action_choice": "keep testing CSC",
            "next_lane": "both_release_and_release64_csc",
            "reason": "release lane changed observable behavior and should be isolated against the both-path lane",
        }
    if signals["both_release_and_release64_csc"]:
        return {
            "classification": "both_has_signal",
            "next_action_choice": "keep testing CSC",
            "next_lane": "compare both-path result to single-path notes",
            "reason": "both-path CSC lane has an observable change that needs path isolation",
        }
    if any(status in verify_states for status in ("changed_bytes", "changed_size")):
        return {
            "classification": "likely_format_wrapper_blocker",
            "next_action_choice": "investigate SC-CL output compatibility",
            "next_lane": "no runtime lane until export-byte drift is understood",
            "reason": "exported-back bytes or sizes differ from staged donor bytes",
        }
    if all(exact_csc.values()):
        return {
            "classification": "csc_import_survives_but_ignored",
            "next_action_choice": "try XSC review lane",
            "next_lane": "xsc_review_only after explicit approval",
            "reason": "CSC imports survived byte verification and all CSC runtime lanes reported no signal",
        }
    if any(status in verify_states for status in ("export_folder_missing", "missing_export", "manual_review")):
        return {
            "classification": "no_change_observed",
            "next_action_choice": "keep testing CSC",
            "next_lane": "first CSC lane lacking exported-back byte verification",
            "reason": "runtime notes show no signal yet and import/export evidence is incomplete",
        }
    return {
        "classification": "do_not_patch_yet",
        "next_action_choice": "stop because no signal exists yet",
        "next_lane": "manual evidence review",
        "reason": "no tested lane exposes a smallest safe UI/resource blocker yet",
    }


def status_table(results: list[dict[str, str]], verification: list[dict[str, Any]]) -> list[str]:
    counts = verification_counts(verification)
    rows: list[list[str]] = []
    for row in results:
        statuses = ", ".join(f"{key}:{value}" for key, value in sorted(counts.get(row["lane_name"], Counter()).items())) or "none"
        rows.append(
            [
                row["lane_id"],
                row["lane_name"],
                "yes" if row_tested(row) else "no",
                "yes" if row_has_runtime_signal(row) else "no",
                statuses,
                row.get("conclusion", ""),
            ]
        )
    return markdown_table(rows, ["Lane", "Name", "Tested", "Runtime signal", "Export verification", "Conclusion"])


def decision_report(results: list[dict[str, str]], verification: list[dict[str, Any]], verdict: dict[str, str]) -> str:
    counts = Counter(str(row.get("status", "")) for row in verification)
    lines = [
        "# Code RED MP Test Decision Report",
        "",
        "This report ingests manual test notes and exported-back byte verification only. It does not modify archives or scripts.",
        "",
        "## Decision",
        "",
        f"- Classification: `{verdict['classification']}`",
        f"- Acceptance action: `{verdict['next_action_choice']}`",
        f"- Exact next lane: `{verdict['next_lane']}`",
        f"- Reason: {verdict['reason']}",
        "",
        "## Lane status",
        "",
        *status_table(results, verification),
        "",
        "## Export verification summary",
        "",
        *markdown_table([[status, str(count)] for status, count in sorted(counts.items())], ["Status", "Rows"]),
        "",
        "## Decision boundaries",
        "",
        "- `xsc_review_only` remains review-only unless `approved_for_import` is explicitly set truthy in `mp_test_results.csv`.",
        "- Exported-back byte drift blocks runtime conclusions until size, SHA1, and CRC32 changes are understood.",
        "- Authentication/profile/public-server blockers are report-only in this pass.",
        "",
    ]
    return "\n".join(lines) + "\n"


def next_action_report(verdict: dict[str, str]) -> str:
    action_notes = {
        "keep testing CSC": "Use the named CSC/baseline lane, restore the clean backup first, then fill `mp_test_results.csv`.",
        "try XSC review lane": "Do not import XSC until explicitly approved; use the review lane only after CSC byte-survival evidence is complete.",
        "investigate SC-CL output compatibility": "Stop runtime matrix expansion until a PC-compatible script output path is proven.",
        "patch a UI-hidden local LAN route": "Limit the next candidate to local LAN visibility/reachability and keep auth/public routes untouched.",
        "stop because no signal exists yet": "Keep reporting the blocker; no gameplay or auth patch is justified by current evidence.",
    }
    return "\n".join(
        [
            "# Code RED MP Next Action After Manual Tests",
            "",
            f"- Decision class: `{verdict['classification']}`",
            f"- Next action: `{verdict['next_action_choice']}`",
            f"- Exact next lane: `{verdict['next_lane']}`",
            f"- Why: {verdict['reason']}",
            "",
            action_notes[verdict["next_action_choice"]],
            "",
        ]
    ) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    reports = Path(args.reports)
    results_path = reports / "mp_test_results.csv"
    matrix_path = reports / "mp_manual_test_matrix.md"
    verification_path = reports / "mp_import_export_verification.csv"
    ensure_manual_matrix(matrix_path)
    results = ensure_results(results_path)
    verification = verify_exports(results, Path(args.pass2_packages), reports)
    write_csv(verification_path, verification, VERIFICATION_FIELDS)
    verdict = decision(results, verification)
    write_text(reports / "mp_test_decision_report.md", decision_report(results, verification, verdict))
    write_text(reports / "mp_next_action_after_manual_tests.md", next_action_report(verdict))
    summary = {
        "tool": "codered_mp_test_result_ingest",
        "results_rows": len(results),
        "tested_lanes": [row["lane_name"] for row in results if row_tested(row)],
        "verification_rows": len(verification),
        "verification_status_counts": dict(Counter(str(row.get("status", "")) for row in verification)),
        "classification": verdict["classification"],
        "next_action_choice": verdict["next_action_choice"],
        "next_lane": verdict["next_lane"],
        "reports": str(reports),
        "no_content_rpf_write": True,
        "no_script_bytecode_patch": True,
        "no_conversion": True,
        "no_public_server_spoofing": True,
    }
    write_text(reports / "mp_test_result_ingest_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest Code RED MP restore test notes and exported-back verification.")
    parser.add_argument("--reports", default=str(ROOT / "reports"))
    parser.add_argument("--pass2-packages", default=str(ROOT / "build" / "mp_content_restore_pass2"))
    args = parser.parse_args(argv)
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
