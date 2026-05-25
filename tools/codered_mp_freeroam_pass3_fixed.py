"""Build the fixed Code RED MP Free Roam Pass 3 RPF.

This pass uses Pass 5 as the base, keeps the working MP menu route, installs
the generated bootstrap by replacing an existing named WSC resource, and patches
``long_update_thread.wsc`` to launch that exact named path.
"""
from __future__ import annotations

import argparse
import binascii
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

from codered_wsc.resource import KeyOptions, ResourceError, open_script, repack_script


GAME_ROOT = ROOT.parent
GAME_CONTENT = GAME_ROOT / "game" / "content.rpf"
BUILD_ROOT = ROOT / "build" / "mp_freeroam_pass3_fixed"
REPORTS_ROOT = BUILD_ROOT / "reports"
OVERLAY_TOOL = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
UTILS_TOOL = ROOT / "tools" / "codered_rpf_utils.py"
PASS5_RPF = ROOT / "build" / "mp_content_restore_pass5" / "content_mp_restore_pass5_access_trainer_sectors.rpf"
DEFAULT_BOOTSTRAP_WSC = ROOT / "build" / "wsc_authoring_pass1" / "codered_mp_bootstrap_minimal.wsc"
LONG_SOURCE_WSC = ROOT / "game" / "content_extracted" / "release64" / "scripting" / "designerdefined" / "long_update_thread.wsc"
RDR_EXE = GAME_ROOT / "RDR.exe"

SOURCE_LAUNCH_PATH = "$/content/scripting/DesignerDefined/Traffic/trafficDebugThread"
TARGET_LAUNCH_PATH = "$/content/scripting/designerdefined/socialclub/sc_aa_challenge"
LONG_ARCHIVE = "root/content/release64/scripting/designerdefined/long_update_thread.wsc"
BOOTSTRAP_ARCHIVE = "root/content/release64/scripting/designerdefined/socialclub/sc_aa_challenge.wsc"
DEFAULT_OUTPUT_RPF = BUILD_ROOT / "content_mp_freeroam_pass3_fixed_local_freeroam.rpf"


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"


def file_meta(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha1": sha1_bytes(data), "crc32": crc32_bytes(data)}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_long_update_thread(output: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if len(SOURCE_LAUNCH_PATH) != len(TARGET_LAUNCH_PATH):
        raise ValueError("Launch path replacement must stay same-length.")
    resource = open_script(LONG_SOURCE_WSC, KeyOptions(rdr_exe=str(RDR_EXE)))
    if resource.decode_error:
        raise ResourceError(resource.decode_error)
    decoded = bytearray(resource.decoded)
    source = SOURCE_LAUNCH_PATH.encode("ascii")
    target = TARGET_LAUNCH_PATH.encode("ascii")
    hits: list[int] = []
    start = 0
    while True:
        idx = decoded.find(source, start)
        if idx < 0:
            break
        hits.append(idx)
        decoded[idx : idx + len(source)] = target
        start = idx + len(source)
    if len(hits) != 1:
        raise RuntimeError(f"Expected exactly one launch-path hit, found {len(hits)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    packed, repack = repack_script(resource, bytes(decoded), allow_growth=True)
    output.write_bytes(packed)
    validate = open_script(output, KeyOptions(rdr_exe=str(RDR_EXE)))
    if validate.decode_error:
        raise ResourceError(validate.decode_error)
    if TARGET_LAUNCH_PATH.encode("ascii") not in validate.decoded:
        raise RuntimeError("Patched long_update_thread does not contain target launch path after reopen.")
    if SOURCE_LAUNCH_PATH.encode("ascii") in validate.decoded:
        raise RuntimeError("Patched long_update_thread still contains original launch path after reopen.")
    rows = [
        {
            "decoded_offset": f"0x{idx:X}",
            "original": SOURCE_LAUNCH_PATH,
            "replacement": TARGET_LAUNCH_PATH,
            "length": len(source),
            "same_length": True,
        }
        for idx in hits
    ]
    return (
        {
            "source": str(LONG_SOURCE_WSC),
            "output": str(output),
            "source_sha1": file_meta(LONG_SOURCE_WSC)["sha1"],
            "output_sha1": file_meta(output)["sha1"],
            "decoded_size": len(validate.decoded),
            "repack_validate_ok": bool(repack.get("validate_ok")),
            "fit_mode": repack.get("fit_mode", ""),
            "codec": repack.get("codec", ""),
        },
        rows,
    )


def build_overlay_rpf(source_rpf: Path, output_rpf: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    overlay = load_module(OVERLAY_TOOL, "codered_overlay_pass3_fixed")
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source_rpf)
    if info is None:
        raise RuntimeError(f"Source does not parse as RPF6: {source_rpf}")
    root = overlay.build_existing_tree(info)
    operations: list[dict[str, Any]] = []
    for row in rows:
        action, node = overlay.add_or_replace_file(
            wb,
            root,
            row["archive_path"],
            row["payload"],
            "replace",
            allow_resource_replace=True,
        )
        operations.append(
            {
                "archive_path": row["archive_path"],
                "source_path": row["source_path"],
                "action": action,
                "resource_replace": node.resource_replace,
                "resource_flag1": f"0x{node.resource_flag1:08X}" if node.resource_replace else "",
                "resource_flag2": f"0x{node.resource_flag2:08X}" if node.resource_replace else "",
                "decoded_size": len(row["payload"]),
                "stored_size": node.stored_size,
                "sha1": row["sha1"],
            }
        )

    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    file_offsets = [int(entry["offset"]) for entry in info["entries"] if entry.get("type") == "file"]
    payload_floor = min(file_offsets)
    if 16 + toc_size > payload_floor:
        raise RuntimeError(f"TOC would overlap first payload: toc_end={16 + toc_size} payload_floor={payload_floor}")
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
    toc = overlay.pack_toc(wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", output_bytes, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    output_bytes[16 : 16 + len(toc)] = toc
    output_rpf.parent.mkdir(parents=True, exist_ok=True)
    output_rpf.write_bytes(output_bytes)
    parsed = wb.parse_rpf6(output_rpf)
    if parsed is None:
        raise RuntimeError(f"Output does not parse as RPF6: {output_rpf}")
    return {
        "source": file_meta(source_rpf),
        "output": file_meta(output_rpf),
        "entry_count_before": info.get("entry_count"),
        "entry_count_after": parsed.get("entry_count"),
        "operations": operations,
    }


def verify_output(output_rpf: Path, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    utils = load_module(UTILS_TOOL, "codered_rpf_utils_pass3_fixed")
    wb = utils.load_backend()
    info = utils.parse_archive(output_rpf)
    checks: list[dict[str, Any]] = []
    for row in rows:
        entry = utils.find_entry(info, row["archive_path"])
        data = utils.extract_entry_payload(wb, output_rpf, entry)
        status = "exact_match" if sha1_bytes(data) == row["sha1"] else "mismatch"
        checks.append(
            {
                "archive_path": row["archive_path"],
                "entry_index": entry.get("index"),
                "name": entry.get("name"),
                "is_resource": entry.get("is_resource"),
                "resource_type": entry.get("resource_type"),
                "status": status,
                "expected_sha1": row["sha1"],
                "actual_sha1": sha1_bytes(data),
                "expected_size": len(row["payload"]),
                "actual_size": len(data),
            }
        )
    bootstrap_entry = utils.find_entry(info, BOOTSTRAP_ARCHIVE)
    long_entry = utils.find_entry(info, LONG_ARCHIVE)
    summary = {
        "bootstrap_path_resolves": True,
        "bootstrap_name": bootstrap_entry.get("name"),
        "bootstrap_is_resource": bool(bootstrap_entry.get("is_resource")),
        "bootstrap_resource_type": bootstrap_entry.get("resource_type"),
        "bootstrap_is_hash_only": str(bootstrap_entry.get("name") or "").startswith("0x"),
        "long_path_resolves": True,
        "long_is_resource": bool(long_entry.get("is_resource")),
        "all_exact_match": all(row["status"] == "exact_match" for row in checks),
    }
    if summary["bootstrap_is_hash_only"]:
        raise RuntimeError(f"Bootstrap is still hash-only: {bootstrap_entry}")
    if not summary["bootstrap_is_resource"] or summary["bootstrap_resource_type"] != 2:
        raise RuntimeError(f"Bootstrap is not a type-2 WSC resource: {bootstrap_entry}")
    return summary, checks


def backup_live() -> Path:
    meta = file_meta(GAME_CONTENT)
    backup = BUILD_ROOT / "live_backups" / f"content_before_fixed_pass3_{meta['sha1'][:12]}.rpf"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(GAME_CONTENT, backup)
    return backup


def install_live(output_rpf: Path, label: str) -> dict[str, Any]:
    backup = backup_live()
    shutil.copy2(output_rpf, GAME_CONTENT)
    live = file_meta(GAME_CONTENT)
    expected = file_meta(output_rpf)
    if live["sha1"] != expected["sha1"]:
        shutil.copy2(backup, GAME_CONTENT)
        raise RuntimeError("Live install SHA1 mismatch; restored backup.")
    return {"backup": file_meta(backup), "live_after": live}


def collect_recent_events(start_time_iso: str) -> str:
    script = (
        "$start=[datetime]::Parse('%s'); "
        "Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=$start} -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Message -match 'RDR\\\\.exe|PlayRDR\\\\.exe|RDRMessage\\\\.exe|crashpad_handler\\\\.exe|Red Dead Redemption' } | "
        "Select-Object TimeCreated,Id,ProviderName,LevelDisplayName,Message | Format-List"
    ) % start_time_iso
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], cwd=str(ROOT), capture_output=True, text=True, timeout=20)
    return (result.stdout or "") + (("\nSTDERR:\n" + result.stderr) if result.stderr else "")


def run_boot_test(timeout_seconds: int, label: str) -> dict[str, Any]:
    start_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    ps = f"""
$p = Start-Process -FilePath '{RDR_EXE}' -WorkingDirectory '{GAME_ROOT}' -PassThru
Start-Sleep -Seconds {timeout_seconds}
$alive = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
if ($alive) {{
  Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
  'STATUS=still_running_killed'
}} else {{
  'STATUS=exited_before_timeout'
}}
'PID=' + $p.Id
"""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", ps], cwd=str(GAME_ROOT), capture_output=True, text=True, timeout=timeout_seconds + 20)
    status = "unknown"
    for line in result.stdout.splitlines():
        if line.startswith("STATUS="):
            status = line.split("=", 1)[1].strip()
    events = collect_recent_events(start_iso)
    diag_dir = REPORTS_ROOT / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    write_text(diag_dir / f"{label}_boot_test_stdout.txt", result.stdout)
    write_text(diag_dir / f"{label}_boot_test_stderr.txt", result.stderr)
    write_text(diag_dir / f"{label}_boot_test_windows_events.txt", events)
    for source in [GAME_ROOT / "asiloader.log", GAME_ROOT / "ScriptHookRDR.log", GAME_ROOT / "logs" / "codered_mp_dev_trainer.log"]:
        if source.exists():
            shutil.copy2(source, diag_dir / f"{label}_{source.name}")
    return {
        "start_time": start_iso,
        "timeout_seconds": timeout_seconds,
        "status": status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "windows_events_file": str(diag_dir / f"{label}_boot_test_windows_events.txt"),
    }


def build_fixed(install: bool, boot_test: bool, timeout_seconds: int, bootstrap_wsc: Path, output_rpf: Path, label: str) -> dict[str, Any]:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    patched_long = BUILD_ROOT / "working" / "long_update_thread.wsc"
    patch_summary, patch_rows = patch_long_update_thread(patched_long)
    write_csv(REPORTS_ROOT / "mp_pass3_fixed_long_thread_offsets.csv", patch_rows)

    rows = []
    for source, archive_path, layer in [
        (patched_long, LONG_ARCHIVE, "long_update_thread_hook"),
        (bootstrap_wsc, BOOTSTRAP_ARCHIVE, "named_bootstrap_resource"),
    ]:
        data = source.read_bytes()
        rows.append(
            {
                "source_path": str(source),
                "archive_path": archive_path,
                "layer": layer,
                "payload": data,
                "sha1": sha1_bytes(data),
                "size": len(data),
            }
        )

    build_summary = build_overlay_rpf(PASS5_RPF, output_rpf, rows)
    verify_summary, verify_rows = verify_output(output_rpf, rows)
    write_csv(REPORTS_ROOT / f"mp_pass3_fixed_{label}_manifest.csv", [{k: v for k, v in row.items() if k != "payload"} for row in rows])
    write_csv(REPORTS_ROOT / f"mp_pass3_fixed_{label}_readback_verification.csv", verify_rows)

    install_summary = install_live(output_rpf, label) if install else None
    boot_summary = run_boot_test(timeout_seconds, label) if boot_test else None

    summary = {
        "pass": f"mp_freeroam_pass3_fixed_{label}",
        "goal": "start local MP Free Roam through named WSC bootstrap and long_update_thread hook",
        "source_base": file_meta(PASS5_RPF),
        "bootstrap_wsc": file_meta(bootstrap_wsc),
        "output_rpf": file_meta(output_rpf),
        "patch_summary": patch_summary,
        "build_summary": build_summary,
        "verify_summary": verify_summary,
        "installed_live": bool(install_summary),
        "install_summary": install_summary,
        "boot_test": boot_summary,
        "crash_interpretation": "If this crashes at boot, run a hook-control build that launches a WAIT-only WSC at the same named resource path. If the control boots, the MP backend script calls are the crash source; if the control also crashes, the hook timing/resource launch path is the crash source.",
    }
    write_json(REPORTS_ROOT / f"mp_pass3_fixed_{label}_summary.json", summary)
    write_text(
        REPORTS_ROOT / f"mp_pass3_fixed_{label}_report.md",
        "# Code RED MP Free Roam Fixed Pass 3\n\n"
        f"- Base: `{PASS5_RPF}`\n"
        f"- Output: `{output_rpf}`\n"
        f"- Bootstrap payload: `{bootstrap_wsc}`\n"
        f"- Bootstrap installed at named WSC resource: `{BOOTSTRAP_ARCHIVE}`\n"
        f"- Launch hook target: `{TARGET_LAUNCH_PATH}`\n"
        f"- Live installed: `{bool(install_summary)}`\n"
        f"- Boot test: `{boot_summary['status'] if boot_summary else 'not_run'}`\n\n"
        "The bootstrap replaces an existing named Social Club WSC resource, so it resolves by path and remains resource type 2.\n",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-live", action="store_true")
    parser.add_argument("--boot-test", action="store_true")
    parser.add_argument("--boot-timeout", type=int, default=45)
    parser.add_argument("--bootstrap-wsc", type=Path, default=DEFAULT_BOOTSTRAP_WSC)
    parser.add_argument("--output-rpf", type=Path, default=DEFAULT_OUTPUT_RPF)
    parser.add_argument("--label", default="local_freeroam")
    args = parser.parse_args()
    print(json.dumps(build_fixed(args.install_live, args.boot_test, args.boot_timeout, args.bootstrap_wsc, args.output_rpf, args.label), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
