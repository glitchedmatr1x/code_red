"""Build Code RED MP bootstrap Pass 2 drop-in WSC patch.

This pass keeps the original game files untouched.  It patches a decoded copy
of long_update_thread.wsc by replacing one same-length script path operand with
the new CodeRED MP bootstrap path, then repacks/reopens both WSC resources.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from codered_wsc.resource import KeyOptions, ResourceError, open_script, repack_script

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LONG = ROOT / "game" / "content_extracted" / "release64" / "scripting" / "designerdefined" / "long_update_thread.wsc"
DEFAULT_BOOTSTRAP = ROOT / "build" / "wsc_authoring_pass1" / "codered_mp_bootstrap_minimal.wsc"
DEFAULT_BUILD = ROOT / "build" / "mp_bootstrap_pass2"
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_RDR_EXE = ROOT.parent / "RDR.exe"

SOURCE_PATH = "$/content/scripting/DesignerDefined/Traffic/trafficDebugThread"
BOOTSTRAP_PATH = "content/scripting/DesignerDefined/codered_mp_bootstrap_minimal"
DROPIN_LONG = Path("content/release64/scripting/designerdefined/long_update_thread.wsc")
DROPIN_BOOTSTRAP = Path("content/release64/scripting/designerdefined/codered_mp_bootstrap_minimal.wsc")


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def sha1_file(path: Path) -> str:
    return sha1_bytes(path.read_bytes())


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
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_repack(path: Path, rdr_exe: Path) -> dict[str, Any]:
    resource = open_script(path, KeyOptions(rdr_exe=str(rdr_exe)))
    if resource.decode_error:
        raise ResourceError(resource.decode_error)
    _, repack_report = repack_script(resource, resource.decoded, allow_growth=True)
    return {
        "path": str(path),
        "sha1": sha1_file(path),
        "decoded_size": len(resource.decoded),
        "inspect_reopen_ok": True,
        "repack_reopen_ok": bool(repack_report.get("validate_ok")),
        "repack_fit_mode": repack_report.get("fit_mode", ""),
        "repack_codec": repack_report.get("codec", ""),
    }


def patch_long_update_thread(source: Path, output: Path, rdr_exe: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if len(SOURCE_PATH) != len(BOOTSTRAP_PATH):
        raise ValueError("Pass 2 path replacement must remain same length.")
    resource = open_script(source, KeyOptions(rdr_exe=str(rdr_exe)))
    if resource.decode_error:
        raise ResourceError(resource.decode_error)

    original = SOURCE_PATH.encode("ascii")
    replacement = BOOTSTRAP_PATH.encode("ascii")
    decoded = bytearray(resource.decoded)
    offsets: list[int] = []
    start = 0
    while True:
        found = decoded.find(original, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + len(original)
    if len(offsets) != 1:
        raise ValueError(f"Expected exactly one bootstrap source path hit, found {len(offsets)}")

    offset = offsets[0]
    before = bytes(decoded[offset : offset + len(original)])
    decoded[offset : offset + len(original)] = replacement
    output_bytes, repack_report = repack_script(resource, bytes(decoded), allow_growth=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(output_bytes)
    reopened = open_script(output, KeyOptions(rdr_exe=str(rdr_exe)))
    validate_ok = reopened.decoded == bytes(decoded) and not reopened.decode_error
    if not validate_ok:
        raise ResourceError("Patched long_update_thread.wsc did not reopen to the patched decoded bytes.")

    row = {
        "archive_path": str(DROPIN_LONG).replace("\\", "/"),
        "decoded_offset": offset,
        "decoded_offset_hex": f"0x{offset:X}",
        "original": SOURCE_PATH,
        "replacement": BOOTSTRAP_PATH,
        "length": len(original),
        "before_sha1": sha1_bytes(before),
        "after_sha1": sha1_bytes(replacement),
        "patch_type": "same_length_pushstring_path_replace",
        "reason": "route long_update_thread script launch path to CodeRED MP bootstrap WSC",
    }
    report = {
        "input": str(source),
        "output": str(output),
        "input_sha1": sha1_file(source),
        "output_sha1": sha1_file(output),
        "decoded_original_sha1": sha1_bytes(resource.decoded),
        "decoded_patched_sha1": sha1_bytes(bytes(decoded)),
        "same_decoded_size": len(resource.decoded) == len(decoded),
        "same_output_size": source.stat().st_size == output.stat().st_size,
        "repack_report": repack_report,
        "reopen_validate_ok": validate_ok,
    }
    return report, [row]


def write_reports(reports: Path, build: Path, patch_report: dict[str, Any], validations: list[dict[str, Any]], offsets: list[dict[str, Any]]) -> None:
    write_csv(reports / "mp_bootstrap_pass2_changed_offsets.csv", offsets)
    write_json(reports / "mp_bootstrap_pass2_manifest.json", {"patch": patch_report, "validations": validations, "offsets": offsets})
    validation_lines = [
        "# MP Bootstrap Pass 2 Validation",
        "",
    ]
    for item in validations:
        validation_lines.extend(
            [
                f"## {Path(item['path']).name}",
                f"- inspect reopen ok: `{item['inspect_reopen_ok']}`",
                f"- repack reopen ok: `{item['repack_reopen_ok']}`",
                f"- decoded size: `{item['decoded_size']}`",
                f"- sha1: `{item['sha1']}`",
                "",
            ]
        )
    (reports / "mp_bootstrap_pass2_validation.md").write_text("\n".join(validation_lines), encoding="utf-8")

    patch_lines = [
        "# MP Bootstrap Pass 2 Patch Report",
        "",
        "Goal: route a normal PC update-thread script launch path to the CodeRED MP bootstrap WSC without bytecode growth.",
        "",
        "## Strategy",
        "",
        "- Strategy A, add a new launch block: blocked in this pass because general WSC bytecode growth/rebuild is not proven.",
        "- Strategy B, same-length script path replacement: used.",
        "- Strategy C, direct MP backend path replacement: not used in the default output.",
        "",
        "## Patch",
        "",
        f"- Source update thread: `{patch_report['input']}`",
        f"- Patched update thread: `{patch_report['output']}`",
        f"- Original path: `{SOURCE_PATH}`",
        f"- Replacement path: `{BOOTSTRAP_PATH}`",
        f"- Replacement length: `{len(SOURCE_PATH)}` bytes",
        f"- Reopen validation: `{patch_report['reopen_validate_ok']}`",
        f"- Same decoded size: `{patch_report['same_decoded_size']}`",
        f"- Same output size: `{patch_report['same_output_size']}`",
        "",
        "## Drop-In Folder",
        "",
        f"- `{build / 'dropin'}`",
        "",
        "## Runtime Boundary",
        "",
        "The patch redirects the existing `trafficDebugThread` script path slot. It proves a same-size WSC route to the bootstrap; runtime execution still depends on the original update-thread branch that launches that slot.",
    ]
    (reports / "mp_bootstrap_pass2_patch_report.md").write_text("\n".join(patch_lines) + "\n", encoding="utf-8")

    test_lines = [
        "# MP Bootstrap Pass 2 Test Steps",
        "",
        "1. Back up the current test content.rpf.",
        "2. Import the drop-in folder with Magic RDR, preserving paths:",
        f"   - `{DROPIN_LONG.as_posix()}`",
        f"   - `{DROPIN_BOOTSTRAP.as_posix()}`",
        "3. Reopen the RPF after import.",
        "4. Export both imported WSC files back out.",
        "5. Compare exported bytes against the drop-in files before launching.",
        "6. Launch the game with the Pass 5/6 XML route active.",
        "7. Enter the MP/Free Roam route and watch for a change from menu-only behavior to backend script activity.",
        "8. If nothing changes, the next pass should patch a more frequently executed launch slot or add a real launch block once WSC growth/rebuild is proven.",
    ]
    (reports / "mp_bootstrap_pass2_test_steps.md").write_text("\n".join(test_lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build MP bootstrap Pass 2 WSC drop-in folder.")
    parser.add_argument("--long-update-thread", default=str(DEFAULT_LONG))
    parser.add_argument("--bootstrap-wsc", default=str(DEFAULT_BOOTSTRAP))
    parser.add_argument("--build-dir", default=str(DEFAULT_BUILD))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS))
    parser.add_argument("--rdr-exe", default=str(DEFAULT_RDR_EXE))
    args = parser.parse_args(argv)

    build = Path(args.build_dir)
    reports = Path(args.reports_dir)
    rdr_exe = Path(args.rdr_exe)
    long_src = Path(args.long_update_thread)
    bootstrap_src = Path(args.bootstrap_wsc)
    if not long_src.exists():
        raise FileNotFoundError(f"Missing long_update_thread: {long_src}")
    if not bootstrap_src.exists():
        raise FileNotFoundError(f"Missing bootstrap WSC: {bootstrap_src}")
    if not rdr_exe.exists():
        raise FileNotFoundError(f"Missing RDR.exe for AES key extraction: {rdr_exe}")

    dropin = build / "dropin"
    patched_long = dropin / DROPIN_LONG
    staged_bootstrap = dropin / DROPIN_BOOTSTRAP
    if dropin.exists():
        shutil.rmtree(dropin)

    patch_report, offsets = patch_long_update_thread(long_src, patched_long, rdr_exe)
    staged_bootstrap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bootstrap_src, staged_bootstrap)

    validations = [validate_repack(patched_long, rdr_exe), validate_repack(staged_bootstrap, rdr_exe)]
    write_reports(reports, build, patch_report, validations, offsets)
    status = "pass" if all(item["inspect_reopen_ok"] and item["repack_reopen_ok"] for item in validations) else "validation_failed"
    print(
        json.dumps(
            {
                "status": status,
                "dropin": str(dropin),
                "patched_long_update_thread": str(patched_long),
                "staged_bootstrap": str(staged_bootstrap),
                "changed_offsets": str(reports / "mp_bootstrap_pass2_changed_offsets.csv"),
            },
            indent=2,
        )
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
