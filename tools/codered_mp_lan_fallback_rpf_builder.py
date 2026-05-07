#!/usr/bin/env python3
"""Dry-run and verification helper for the LAN fallback content.rpf test.

Dry-run is the default and does not write or install an RPF. It maps the
candidate SCXML payloads to exact archive entries and reports what would be
replaced. Optional post-build verification can be run against a copied test RPF
after a future explicit build step.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

try:
    import zstandard as zstd
except Exception:
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"
DEFAULT_SOURCE = Path(r"D:\Games\Red Dead Redemption\game\content.rpf")
DEFAULT_CANDIDATE_DIR = ROOT / "logs" / "content_mp_lan_fallback_candidate"
DEFAULT_OUT_RPF = ROOT / "build" / "content_mp_lan_fallback_test" / "content.rpf"
DEFAULT_LOG_DIR = ROOT / "logs" / "content_mp_lan_fallback_candidate"
MP_REQUIRED = [
    "root/content/release/multiplayer/freemode/freemode.csc",
    "root/content/release64/multiplayer/freemode/freemode.csc",
]
UNTOUCHED_PROBE_ENTRIES = [
    "root/content/ui/pausemenu/networking.sc.xml",
    "root/content/release/multiplayer/mp_idle.csc",
]


def load_backend():
    spec = importlib.util.spec_from_file_location("codered_workbench_backend", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_archive(wb, path: Path) -> dict:
    info = wb.parse_rpf6(path)
    if info is None:
        raise ValueError(f"Not a readable RPF6 archive: {path}")
    return info


def entry_by_path(info: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ent in info.get("entries", []):
        if ent.get("type") == "file":
            out[str(ent.get("path") or "").replace("\\", "/").lower()] = ent
    return out


def raw_entry_payload(archive: Path, ent: dict) -> bytes:
    with archive.open("rb") as fh:
        fh.seek(int(ent.get("offset") or 0))
        return fh.read(int(ent.get("size_in_archive") or 0))


def decode_zstd_or_text(data: bytes) -> tuple[bytes, str]:
    if data.startswith(b"\x28\xB5\x2F\xFD"):
        if zstd is None:
            raise RuntimeError("Entry is Zstandard-compressed but Python zstandard is unavailable")
        return zstd.ZstdDecompressor().decompress(data), "zstd"
    return data, "plain"


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def load_candidate(candidate_dir: Path) -> dict:
    summary = candidate_dir / "candidate_summary.json"
    roundtrip = candidate_dir / "zstd_roundtrip_report.json"
    if not summary.exists():
        raise FileNotFoundError(f"Missing candidate summary: {summary}")
    if not roundtrip.exists():
        raise FileNotFoundError(f"Missing Zstd round-trip report: {roundtrip}")
    data = json.loads(summary.read_text(encoding="utf-8"))
    rt = json.loads(roundtrip.read_text(encoding="utf-8"))
    encoded_by_archive = {row["archive_path"].lower(): row for row in rt.get("rows", [])}
    return {"summary": data, "roundtrip": rt, "encoded_by_archive": encoded_by_archive}


def build_dry_run(source: Path, candidate_dir: Path, output_rpf: Path, log_dir: Path) -> dict:
    wb = load_backend()
    info = parse_archive(wb, source)
    by_path = entry_by_path(info)
    candidate = load_candidate(candidate_dir)
    replacements = []
    missing = []
    for item in candidate["summary"].get("candidate_files", []):
        archive_path = str(item["archive_path"]).replace("\\", "/")
        ent = by_path.get(archive_path.lower())
        encoded = candidate["encoded_by_archive"].get(archive_path.lower(), {})
        if ent is None:
            missing.append(archive_path)
            continue
        replacements.append(
            {
                "archive_path": archive_path,
                "entry_index": ent.get("index"),
                "name": ent.get("name"),
                "offset": ent.get("offset"),
                "stored_size": ent.get("size_in_archive"),
                "total_size": ent.get("total_size"),
                "is_compressed": ent.get("is_compressed"),
                "is_resource": ent.get("is_resource"),
                "resource_type": ent.get("resource_type"),
                "candidate_decoded": item.get("candidate_decoded"),
                "candidate_encoded": encoded.get("encoded_path"),
                "candidate_decoded_sha1": encoded.get("decoded_sha1"),
                "candidate_encoded_sha1": encoded.get("encoded_sha1"),
                "candidate_encoded_size": encoded.get("encoded_size"),
            }
        )
    mp_csc_entries = [path for path in by_path if "/multiplayer/" in path and path.endswith(".csc")]
    required_mp_presence = {path: (path.lower() in by_path) for path in MP_REQUIRED}
    untouched_probe_presence = {path: (path.lower() in by_path) for path in UNTOUCHED_PROBE_ENTRIES}
    warnings = []
    if not mp_csc_entries:
        warnings.append("source_content_rpf_has_no_multiplayer_csc_entries; post-build test archive must be based on the MP-content candidate/injected archive or this verification gate will fail")
    missing_required_mp = [path for path, present in required_mp_presence.items() if not present]
    if missing_required_mp:
        warnings.append(f"source_content_rpf_missing_required_mp_entries={missing_required_mp}")
    status = "pass" if replacements and not missing and candidate["summary"].get("status") == "pass" else "fail"
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "dry-run",
        "status": status,
        "source_archive": str(source),
        "candidate_dir": str(candidate_dir),
        "output_target_later": str(output_rpf),
        "install_target": r"D:\Games\Red Dead Redemption\game\content.rpf",
        "auto_install": False,
        "entry_count": info.get("entry_count"),
        "file_count": info.get("file_count"),
        "dir_count": info.get("dir_count"),
        "replacements": replacements,
        "missing_archive_paths": missing,
        "warnings": warnings,
        "approved_archive_paths": [item["archive_path"] for item in candidate["summary"].get("candidate_files", [])],
        "source_mp_csc_count": len(mp_csc_entries),
        "source_required_mp_presence": required_mp_presence,
        "source_untouched_probe_presence": untouched_probe_presence,
        "post_build_verification_required": [
            "RPF parses",
            "entry count stays expected",
            "MP CSC tree still exists",
            "freemode.csc still exists in release and release64",
            "patched SCXML extracts",
            "patched SCXML Zstd-decodes",
            "decoded patched XML matches candidate text",
            "untouched live entries still extract",
        ],
        "first_rpf_test_questions": [
            "Does the game boot?",
            "Does the pause menu still open?",
            "Does LAN/System Link route show or behave differently?",
            "Does it reach loading/MP transition or fail at a later runtime state?",
        ],
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "rpf_builder_dryrun_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Code RED LAN Fallback RPF Builder Dry Run",
        "",
        f"Status: `{status}`",
        "",
        r"- backup: `D:\Games\Red Dead Redemption\game\content.rpf`",
        f"- candidate: `{output_rpf}`",
        r"- install target: `D:\Games\Red Dead Redemption\game\content.rpf`",
        "- auto-copy/install: `false`",
        "",
    ]
    if warnings:
        lines.extend(["## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.extend(["", "## Would Replace", ""])
    else:
        lines.extend(["## Would Replace", ""])
    for row in replacements:
        lines.append(f"- `{row['archive_path']}` entry `{row['entry_index']}` offset `{row['offset']}` size `{row['stored_size']}`")
    if missing:
        lines.extend(["", "## Missing Archive Paths", ""])
        for path in missing:
            lines.append(f"- `{path}`")
    lines.extend(["", "## Source Archive Preflight", ""])
    lines.append(f"- MP CSC entries: `{len(mp_csc_entries)}`")
    for path, present in required_mp_presence.items():
        lines.append(f"- `{path}`: `{'present' if present else 'missing'}`")
    for path, present in untouched_probe_presence.items():
        lines.append(f"- untouched probe `{path}`: `{'present' if present else 'missing'}`")
    (log_dir / "RPF_TEST_PREP_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def verify_built_archive(source: Path, built: Path, candidate_dir: Path, log_dir: Path) -> dict:
    wb = load_backend()
    source_info = parse_archive(wb, source)
    built_info = parse_archive(wb, built)
    by_path = entry_by_path(built_info)
    candidate = load_candidate(candidate_dir)
    checks = []

    def add(ok: bool, check: str, detail: str) -> None:
        checks.append({"ok": ok, "check": check, "detail": detail})

    add(True, "rpf_parses", str(built))
    add(
        source_info.get("entry_count") == built_info.get("entry_count"),
        "entry_count_stays_expected",
        f"source={source_info.get('entry_count')} built={built_info.get('entry_count')}",
    )
    mp_entries = [path for path in by_path if "/multiplayer/" in path and path.endswith(".csc")]
    add(bool(mp_entries), "mp_csc_tree_exists", f"mp_csc_count={len(mp_entries)}")
    for path in MP_REQUIRED:
        add(path.lower() in by_path, f"required_mp_entry_exists:{path}", path)

    for item in candidate["summary"].get("candidate_files", []):
        archive_path = str(item["archive_path"]).lower()
        ent = by_path.get(archive_path)
        if ent is None:
            add(False, f"patched_scxml_entry_exists:{archive_path}", "missing")
            continue
        raw = raw_entry_payload(built, ent)
        try:
            decoded, method = decode_zstd_or_text(raw)
            expected = Path(item["candidate_decoded"]).read_bytes()
            add(True, f"patched_scxml_extracts:{archive_path}", f"bytes={len(raw)} decode={method}")
            add(method == "zstd", f"patched_scxml_zstd_decodes:{archive_path}", f"method={method}")
            add(decoded == expected, f"patched_scxml_matches_candidate:{archive_path}", f"decoded_sha1={sha1_bytes(decoded)} expected_sha1={sha1_bytes(expected)}")
        except Exception as exc:
            add(False, f"patched_scxml_verification:{archive_path}", str(exc))

    for path in UNTOUCHED_PROBE_ENTRIES:
        ent = by_path.get(path.lower())
        if ent is None:
            add(False, f"untouched_entry_exists:{path}", "missing")
            continue
        try:
            raw = raw_entry_payload(built, ent)
            add(bool(raw), f"untouched_entry_extracts:{path}", f"bytes={len(raw)}")
        except Exception as exc:
            add(False, f"untouched_entry_extracts:{path}", str(exc))

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "post-build-verify",
        "status": "pass" if all(row["ok"] for row in checks) else "fail",
        "source_archive": str(source),
        "built_archive": str(built),
        "candidate_dir": str(candidate_dir),
        "checks": checks,
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "post_build_verification_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run RPF replacement map for LAN fallback candidate.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT_RPF)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--verify-built", type=Path, default=None, help="Optional copied RPF to verify after a future explicit build.")
    args = parser.parse_args(argv)
    if args.verify_built:
        report = verify_built_archive(args.source, args.verify_built, args.candidate_dir, args.log_dir)
    else:
        report = build_dry_run(args.source, args.candidate_dir, args.output, args.log_dir)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
