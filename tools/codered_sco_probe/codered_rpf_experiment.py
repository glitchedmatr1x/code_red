#!/usr/bin/env python3
"""Repeatable Code RED RPF/SCO/WSC experiment runner."""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import codered_sco_probe as probe


DEFAULT_FIND_TERMS = ["playercar", "player_car", "SimpleGringo", "gringo"]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def append_error(errors: list[dict[str, Any]], stage: str, exc: BaseException) -> None:
    errors.append({"stage": stage, "error": str(exc), "traceback": traceback.format_exc()})


def build_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# Code RED RPF Experiment Report",
        "",
        f"- Source RPF: `{manifest.get('source_rpf')}`",
        f"- Source RPF SHA256: `{manifest.get('source_rpf_sha256', '')}`",
        f"- Target entry: `{manifest.get('target_entry')}`",
        f"- Output folder: `{manifest.get('out_dir')}`",
        f"- Status: `{manifest.get('status')}`",
        "",
        "## Extracted Entry",
        "",
        f"- Path: `{manifest.get('extracted_file', '')}`",
        f"- Size: `{manifest.get('extracted_file_size', '')}`",
        f"- SHA256: `{manifest.get('extracted_file_sha256', '')}`",
        f"- Header: `{manifest.get('extracted_header_bytes', '')}`",
        "",
        "## No-Change RPF",
        "",
        f"- Output: `{manifest.get('nochange_rpf', '')}`",
        f"- SHA256: `{manifest.get('nochange_rpf_sha256', '')}`",
        f"- Validation failures: `{manifest.get('nochange_validation_failures', '')}`",
        "",
        "## Patch",
        "",
        f"- Patch file: `{manifest.get('patch_file', '')}`",
        f"- Patched file: `{manifest.get('patched_file', '')}`",
        f"- Patched file SHA256: `{manifest.get('patched_file_sha256', '')}`",
        f"- Patched RPF: `{manifest.get('patched_rpf', '')}`",
        f"- Patched RPF SHA256: `{manifest.get('patched_rpf_sha256', '')}`",
        f"- Patch same-size: `{manifest.get('patch_same_size', '')}`",
        f"- File length changed: `{manifest.get('patched_file_length_changed', '')}`",
        "",
        "## Changed Offsets",
        "",
    ]
    changes = manifest.get("changed_offsets") or []
    if not changes:
        lines.append("- None")
    else:
        for change in changes[:200]:
            lines.append(
                f"- `{change.get('offset_hex')}` old=`{change.get('old_hex')}` "
                f"new=`{change.get('new_hex')}` old_text=`{change.get('old_text', '')}` "
                f"new_text=`{change.get('new_text', '')}`"
            )
    warnings = manifest.get("warnings") or []
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None")
    errors = manifest.get("errors") or []
    lines.extend(["", "## Errors", ""])
    if errors:
        for error in errors:
            lines.append(f"- stage=`{error.get('stage')}` error=`{error.get('error')}`")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- No-change replacement must pass before patched replacement is trusted.",
            "- Same-size string changes preserve offsets but do not prove behavior.",
            "- Test WSC-only, SCO-only, and WSC+SCO matched patches separately.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    rpf = Path(args.rpf)
    entry = args.entry
    out_dir = Path(args.out)
    patch_file = Path(args.patch) if args.patch else None
    find_terms = list(args.find_entry_substring or []) or DEFAULT_FIND_TERMS

    out_dir.mkdir(parents=True, exist_ok=True)
    scan_dir = out_dir / "scan"
    extract_dir = out_dir / "extracted"
    nochange_dir = out_dir / "nochange"
    patched_dir = out_dir / "patched"
    reports_dir = out_dir / "reports"
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    manifest: dict[str, Any] = {
        "source_rpf": str(rpf),
        "source_rpf_sha256": probe.sha256_file(rpf) if rpf.exists() else "",
        "target_entry": entry,
        "out_dir": str(out_dir),
        "patch_file": str(patch_file) if patch_file else "",
        "warnings": warnings,
        "errors": errors,
        "status": "started",
        "changed_offsets": [],
    }

    try:
        source_scan = probe.scan_rpf(rpf, find_terms)
        write_json(scan_dir / "source_rpf_scan.json", source_scan)
        manifest["source_rpf_entry_count"] = source_scan.get("entry_count")
        manifest["source_rpf_file_count"] = source_scan.get("file_count")
        if not source_scan.get("ok"):
            warnings.append(f"source RPF scan failed: {source_scan.get('error')}")
    except Exception as exc:
        append_error(errors, "scan_source_rpf", exc)
        manifest["status"] = "failed"
        return manifest

    entry_base = Path(entry.replace("\\", "/")).name or "entry.bin"
    extracted = extract_dir / entry_base
    try:
        extract_report = probe.extract_rpf_entry(rpf, entry, extracted)
        write_json(reports_dir / "extract_entry_report.json", extract_report)
        manifest["extracted_file"] = str(extracted)
        manifest["extracted_file_sha256"] = extract_report.get("sha256")
        manifest["extracted_file_size"] = extract_report.get("size")
    except Exception as exc:
        append_error(errors, "extract_target_entry", exc)
        warnings.append(f"target entry not found or not extractable: {entry}")
        try:
            finder = probe.scan_rpf(rpf, find_terms)
            write_json(reports_dir / "entry_find_substring_report.json", finder.get("find_entry_substring", {}))
        except Exception as find_exc:
            append_error(errors, "find_entry_substring_after_extract_failure", find_exc)
        manifest["status"] = "failed"
        return manifest

    try:
        extracted_scan = probe.scan_sco(extracted)
        write_json(scan_dir / "extracted_file_scan.json", extracted_scan)
        manifest["extracted_header_bytes"] = (extracted_scan.get("header") or {}).get("first_16_bytes")
        write_text(scan_dir / "extracted_strings.txt", probe.strings_sco(extracted))
    except Exception as exc:
        append_error(errors, "scan_extracted_file", exc)

    try:
        replacement_source = nochange_dir / entry_base
        replacement_source.parent.mkdir(parents=True, exist_ok=True)
        replacement_source.write_bytes(extracted.read_bytes())
        write_json(reports_dir / "nochange_compare.json", probe.compare_sco(extracted, replacement_source))
        nochange_rpf = nochange_dir / "content_nochange_rebuild.rpf"
        if nochange_rpf.resolve() == rpf.resolve():
            raise RuntimeError("refusing to overwrite source RPF")
        nochange_report = probe.replace_rpf_entry(rpf, entry, replacement_source, nochange_rpf)
        write_json(reports_dir / "nochange_rpf_replace_manifest.json", nochange_report)
        manifest["nochange_replacement_source"] = str(replacement_source)
        manifest["nochange_rpf"] = str(nochange_rpf)
        manifest["nochange_rpf_sha256"] = nochange_report.get("output_sha256")
        manifest["nochange_validation_failures"] = nochange_report.get("validation_failures")
        if int(nochange_report.get("validation_failures") or 0) != 0:
            warnings.append("no-change replacement reported validation failures")
    except Exception as exc:
        append_error(errors, "nochange_rpf_replace", exc)
        manifest["status"] = "failed"
        return manifest

    if patch_file:
        try:
            patched_file = patched_dir / entry_base
            patch_report = probe.apply_sco_string_patches(
                extracted, patch_file, patched_file, bool(args.allow_padding)
            )
            write_json(patched_dir / "patch_sco_strings_manifest.json", patch_report)
            if int(patch_report.get("change_count") or 0) == 0:
                warnings.append("patch JSON matched zero strings")
            write_json(reports_dir / "patched_compare.json", probe.compare_sco(extracted, patched_file))
            patched_rpf = patched_dir / "content_patched_rebuild.rpf"
            patched_rpf_report = probe.replace_rpf_entry(rpf, entry, patched_file, patched_rpf)
            write_json(reports_dir / "patched_rpf_replace_manifest.json", patched_rpf_report)
            changes = []
            for change in patch_report.get("changes", []):
                changes.append(
                    {
                        "offset": change.get("offset"),
                        "offset_hex": change.get("offset_hex"),
                        "old_hex": change.get("old_hex"),
                        "new_hex": change.get("new_hex"),
                        "old_text": change.get("old_text"),
                        "new_text": change.get("new_text"),
                        "old_byte_length": change.get("old_byte_length"),
                        "new_byte_length": change.get("new_byte_length"),
                    }
                )
            manifest.update(
                {
                    "patched_file": str(patched_file),
                    "patched_file_sha256": patch_report.get("output_sha256"),
                    "patched_file_size": patch_report.get("output_size"),
                    "patched_rpf": str(patched_rpf),
                    "patched_rpf_sha256": patched_rpf_report.get("output_sha256"),
                    "patched_validation_failures": patched_rpf_report.get("validation_failures"),
                    "changed_offsets": changes,
                    "patched_file_length_changed": not bool(patch_report.get("size_unchanged")),
                    "patch_same_size": bool(patch_report.get("size_unchanged")),
                }
            )
            if int(patched_rpf_report.get("validation_failures") or 0) != 0:
                warnings.append("patched replacement reported validation failures")
        except Exception as exc:
            append_error(errors, "patched_pipeline", exc)
            warnings.append("patch pipeline did not complete")
    else:
        manifest["patched_file_length_changed"] = ""
        manifest["patch_same_size"] = ""

    manifest["status"] = "completed_with_errors" if errors else "completed"
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a safe Code RED RPF entry experiment")
    parser.add_argument("--rpf", required=True, help="Source content.rpf. Never overwritten.")
    parser.add_argument("--entry", required=True, help="Internal RPF entry path to extract/replace.")
    parser.add_argument("--out", required=True, help="Experiment output folder under build.")
    parser.add_argument("--patch", default="", help="Optional same-size string patch JSON.")
    parser.add_argument("--allow-padding", action="store_true", help="Pass through to patch-sco-strings behavior.")
    parser.add_argument("--find-entry-substring", action="append", default=[], help="Entry substring to report if lookup fails. May repeat.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = run_experiment(args)
    out_dir = Path(args.out)
    write_json(out_dir / "experiment_manifest.json", manifest)
    write_text(out_dir / "experiment_report.md", build_report(manifest))
    print(json.dumps({"status": manifest.get("status"), "manifest": str(out_dir / "experiment_manifest.json"), "report": str(out_dir / "experiment_report.md")}, indent=2))
    return 0 if not manifest.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
