#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ZSTD_MAGIC = bytes.fromhex("28B52FFD")
RSC5_MAGIC = b"RSC\x05"
RPF_WFT_RESOURCE_TYPE = 0x8A
TOOL_VERSION = "Pass9-menu-fix"

TOOL_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TOOL_DIR.parent
LOG_DIR = PACKAGE_ROOT / "logs"
REPORT_DIR = PACKAGE_ROOT / "reports"
SAMPLE_DIR = PACKAGE_ROOT / "samples"
LOG_FILE = LOG_DIR / "wft_tool_last_run.log"


@dataclass
class Rsc5Info:
    magic_hex: str
    resource_type: int
    flag1: int
    compressed_offset: int
    compressed_size: int
    decompressed_size: int
    compressed_sha1: str
    decompressed_sha1: str


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    ensure_dirs()
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{now()}] {message}\n")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def pause(message: str = "Press Enter to continue...") -> None:
    try:
        input(message)
    except EOFError:
        pass


def _run_zstd_decompress(data: bytes) -> bytes:
    p = subprocess.run(
        ["zstd", "-d", "-q", "--single-thread", "--stdout"],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "replace")[:1000]
        raise RuntimeError(
            "zstd decompress failed. Install the zstd command-line tool or keep zstd.exe next to this tool. "
            f"Error: {err}"
        )
    return p.stdout


def _run_zstd_compress(data: bytes, level: int = 9) -> bytes:
    p = subprocess.run(
        ["zstd", "-q", "-z", f"-{level}", "--no-check", "--single-thread", "--stdout"],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "replace")[:1000]
        raise RuntimeError(
            "zstd compress failed. Install the zstd command-line tool or keep zstd.exe next to this tool. "
            f"Error: {err}"
        )
    verify = _run_zstd_decompress(p.stdout)
    if verify != data:
        raise RuntimeError("zstd recompress verification failed")
    return p.stdout


def zstd_available() -> bool:
    try:
        p = subprocess.run(["zstd", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return p.returncode == 0
    except Exception:
        return False


def parse_rsc5_blob(blob: bytes) -> tuple[Rsc5Info, bytes, bytes]:
    """Return (info, header, decompressed_payload) for a RDR/GTA IV style RSC5 blob."""
    if len(blob) < 16:
        raise ValueError("blob too small for RSC5")
    if blob[:4] != RSC5_MAGIC:
        raise ValueError(f"not RSC5: first four bytes are {blob[:4].hex(' ')}")
    zoff = blob.find(ZSTD_MAGIC)
    if zoff < 0:
        raise ValueError("RSC5 blob does not contain zstd payload magic")
    resource_type, flag1 = struct.unpack_from("<II", blob, 4)
    header = blob[:zoff]
    compressed = blob[zoff:]
    decompressed = _run_zstd_decompress(compressed)
    info = Rsc5Info(
        magic_hex=blob[:4].hex(" "),
        resource_type=resource_type,
        flag1=flag1,
        compressed_offset=zoff,
        compressed_size=len(compressed),
        decompressed_size=len(decompressed),
        compressed_sha1=hashlib.sha1(compressed).hexdigest(),
        decompressed_sha1=hashlib.sha1(decompressed).hexdigest(),
    )
    return info, header, decompressed


def rebuild_rsc5_blob(original_blob: bytes, new_decompressed_payload: bytes, *, require_same_size: bool = True, level: int = 9) -> bytes:
    info, header, old_payload = parse_rsc5_blob(original_blob)
    if require_same_size and len(new_decompressed_payload) != len(old_payload):
        raise ValueError(
            f"payload size changed from {len(old_payload)} to {len(new_decompressed_payload)}; "
            "resource-page metadata is not decoded yet, so same-size edits are required"
        )
    compressed = _run_zstd_compress(new_decompressed_payload, level=level)
    rebuilt = header + compressed
    _, _, verify_payload = parse_rsc5_blob(rebuilt)
    if verify_payload != new_decompressed_payload:
        raise RuntimeError("rebuilt RSC5 verification failed")
    return rebuilt


def import_rpf_helper():
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    sys.path.insert(0, str(PACKAGE_ROOT))
    sys.path.insert(0, "/mnt/data")
    try:
        import codered_rpf_utils_patch as rpf  # type: ignore
    except Exception:
        import codered_rpf_utils_local as rpf  # type: ignore
    return rpf


def rpf_wft_entries(rpf_path: Path) -> list[dict[str, Any]]:
    rpf = import_rpf_helper()
    info = rpf.parse(rpf_path, with_debug=True)
    rows: list[dict[str, Any]] = []
    for ent in info["entries"]:
        if ent.get("type") != "file" or ent.get("extension") != ".wft":
            continue
        slot = rpf.read_slot(rpf_path, ent)
        row: dict[str, Any] = {
            "path": ent.get("path"),
            "size_in_archive": ent.get("size_in_archive"),
            "offset": ent.get("offset"),
            "is_resource": ent.get("is_resource"),
            "is_compressed": ent.get("is_compressed"),
            "resource_type": ent.get("resource_type"),
            "slot_sha1": hashlib.sha1(slot).hexdigest(),
        }
        try:
            rinfo, _, _ = parse_rsc5_blob(slot)
            row.update({"rsc5": asdict(rinfo), "status": "ok"})
        except Exception as exc:
            row.update({"status": "parse_error", "error": str(exc)})
        rows.append(row)
    return rows


def cmd_scan(args: argparse.Namespace) -> int:
    rows = rpf_wft_entries(args.rpf)
    out = {
        "tool": f"codered_wft_rsc5_tool.py {TOOL_VERSION}",
        "mode": "scan-rpf",
        "generated_utc": now(),
        "rpf": str(args.rpf),
        "wft_count": len(rows),
        "rsc5_ok_count": sum(1 for r in rows if r.get("status") == "ok"),
        "entries": rows,
    }
    write_json(args.out, out)
    print(json.dumps({"out": str(args.out), "wft_count": out["wft_count"], "rsc5_ok_count": out["rsc5_ok_count"]}, indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    rpf = import_rpf_helper()
    info = rpf.parse(args.rpf, with_debug=True)
    ent = rpf.find_entry(info, args.entry)
    if not ent:
        raise SystemExit(f"entry not found: {args.entry}")
    if ent.get("extension") != ".wft":
        raise SystemExit(f"entry is not .wft: {args.entry}")
    blob = rpf.read_slot(args.rpf, ent)
    rinfo, header, payload = parse_rsc5_blob(blob)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.entry).name
    raw_path = args.out_dir / stem
    payload_path = args.out_dir / f"{stem}.rsc5_payload.bin"
    header_path = args.out_dir / f"{stem}.rsc5_header.bin"
    meta_path = args.out_dir / f"{stem}.rsc5_meta.json"
    raw_path.write_bytes(blob)
    payload_path.write_bytes(payload)
    header_path.write_bytes(header)
    write_json(meta_path, {"entry": args.entry, "rsc5": asdict(rinfo)})
    print(json.dumps({"raw_wft": str(raw_path), "payload": str(payload_path), "meta": str(meta_path)}, indent=2))
    return 0


def cmd_unpack(args: argparse.Namespace) -> int:
    blob = args.wft.read_bytes()
    rinfo, header, payload = parse_rsc5_blob(blob)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.wft.name
    (args.out_dir / f"{stem}.rsc5_header.bin").write_bytes(header)
    (args.out_dir / f"{stem}.rsc5_payload.bin").write_bytes(payload)
    write_json(args.out_dir / f"{stem}.rsc5_meta.json", {"file": str(args.wft), "rsc5": asdict(rinfo)})
    print(json.dumps({"payload_size": len(payload), "out_dir": str(args.out_dir)}, indent=2))
    return 0


def cmd_repack(args: argparse.Namespace) -> int:
    original = args.original_wft.read_bytes()
    payload = args.payload.read_bytes()
    rebuilt = rebuild_rsc5_blob(original, payload, require_same_size=not args.allow_size_change, level=args.level)
    args.out_wft.parent.mkdir(parents=True, exist_ok=True)
    args.out_wft.write_bytes(rebuilt)
    old_info, _, old_payload = parse_rsc5_blob(original)
    new_info, _, new_payload = parse_rsc5_blob(rebuilt)
    report = {
        "tool": f"codered_wft_rsc5_tool.py {TOOL_VERSION}",
        "mode": "repack",
        "generated_utc": now(),
        "original_wft": str(args.original_wft),
        "payload": str(args.payload),
        "out_wft": str(args.out_wft),
        "old": asdict(old_info),
        "new": asdict(new_info),
        "payload_sha1_match_input": hashlib.sha1(payload).hexdigest() == hashlib.sha1(new_payload).hexdigest(),
        "same_decompressed_size": len(old_payload) == len(new_payload),
    }
    if args.report:
        write_json(args.report, report)
    print(json.dumps({"out_wft": str(args.out_wft), "compressed_size": new_info.compressed_size}, indent=2))
    return 0


def append_resource_payload_2048(archive_copy_path: Path, payload: bytes) -> int:
    """Append a resource payload on a 2048-byte boundary.

    RPF6 resource offsets store the low byte of the offset word as the resource
    type, so the byte offset must stay aligned to 0x800 (2048).
    """
    cur = archive_copy_path.stat().st_size
    aligned = (cur + 2047) & ~2047
    with archive_copy_path.open("ab") as f:
        if aligned > cur:
            f.write(b"\x00" * (aligned - cur))
        f.write(payload)
    return aligned


def patch_resource_entry(archive_copy_path: Path, internal_path: str, rebuilt_blob: bytes) -> dict[str, Any]:
    rpf = import_rpf_helper()
    info = rpf.parse(archive_copy_path, with_debug=True)
    ent = rpf.find_entry(info, internal_path)
    if not ent:
        raise KeyError(internal_path)
    if not ent.get("is_resource"):
        raise ValueError("target is not a resource entry")
    original_slot = rpf.read_slot(archive_copy_path, ent)
    old_info, _, old_payload = parse_rsc5_blob(original_slot)
    new_info, _, new_payload = parse_rsc5_blob(rebuilt_blob)
    if len(old_payload) != len(new_payload):
        raise ValueError("decoded payload size changed; refusing resource metadata-unsafe patch")
    relocated = len(rebuilt_blob) > ent["size_in_archive"]
    if relocated:
        new_off = append_resource_payload_2048(archive_copy_path, rebuilt_blob)
        rpf.update_metadata(archive_copy_path, info, ent, new_size_in_archive=len(rebuilt_blob), new_offset=new_off)
    else:
        with archive_copy_path.open("r+b") as f:
            f.seek(ent["offset"])
            f.write(rebuilt_blob)
            if len(rebuilt_blob) < ent["size_in_archive"]:
                f.write(b"\x00" * (ent["size_in_archive"] - len(rebuilt_blob)))
        rpf.update_metadata(archive_copy_path, info, ent, new_size_in_archive=len(rebuilt_blob))
    info2 = rpf.parse(archive_copy_path, with_debug=True)
    ent2 = rpf.find_entry(info2, internal_path)
    reread = rpf.read_slot(archive_copy_path, ent2)
    reread_info, _, reread_payload = parse_rsc5_blob(reread)
    if reread_payload != new_payload:
        raise AssertionError("RPF resource patch reread mismatch")
    return {
        "path": internal_path,
        "original_slot_size": len(original_slot),
        "new_slot_size": len(rebuilt_blob),
        "relocated": relocated,
        "old_offset": ent["offset"],
        "new_offset": ent2["offset"],
        "old_rsc5": asdict(old_info),
        "new_rsc5": asdict(reread_info),
    }


def cmd_patch_rpf(args: argparse.Namespace) -> int:
    if args.rpf_out.exists() and not args.overwrite:
        raise SystemExit(f"output exists; pass --overwrite: {args.rpf_out}")
    args.rpf_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.rpf_in, args.rpf_out)
    rpf = import_rpf_helper()
    info = rpf.parse(args.rpf_out, with_debug=True)
    ent = rpf.find_entry(info, args.entry)
    if not ent:
        raise SystemExit(f"entry not found: {args.entry}")
    original_slot = rpf.read_slot(args.rpf_out, ent)
    new_payload = args.payload.read_bytes()
    rebuilt = rebuild_rsc5_blob(original_slot, new_payload, require_same_size=not args.allow_size_change, level=args.level)
    report = patch_resource_entry(args.rpf_out, args.entry, rebuilt)
    report["tool"] = f"codered_wft_rsc5_tool.py {TOOL_VERSION}"
    report["generated_utc"] = now()
    if args.report:
        write_json(args.report, report)
    print(json.dumps({"rpf_out": str(args.rpf_out), "report": report}, indent=2))
    return 0


def cmd_patch_rpf_wft(args: argparse.Namespace) -> int:
    """Patch an RPF resource entry from a replacement standalone RSC5 WFT blob."""
    if args.rpf_out.exists() and not args.overwrite:
        raise SystemExit(f"output exists; pass --overwrite: {args.rpf_out}")
    args.rpf_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.rpf_in, args.rpf_out)
    rpf = import_rpf_helper()
    info = rpf.parse(args.rpf_out, with_debug=True)
    ent = rpf.find_entry(info, args.entry)
    if not ent:
        raise SystemExit(f"entry not found: {args.entry}")
    original_slot = rpf.read_slot(args.rpf_out, ent)
    old_info, _, old_payload = parse_rsc5_blob(original_slot)
    replacement_blob = args.replacement_wft.read_bytes()
    new_info, _, new_payload = parse_rsc5_blob(replacement_blob)
    if old_info.resource_type != new_info.resource_type:
        raise SystemExit(f"resource type changed: {old_info.resource_type} -> {new_info.resource_type}")
    if old_info.flag1 != new_info.flag1 and not args.allow_size_change:
        raise SystemExit(
            f"RSC5 flag1/page metadata changed: 0x{old_info.flag1:08X} -> 0x{new_info.flag1:08X}; "
            "refusing until page metadata updating is decoded"
        )
    if len(old_payload) != len(new_payload) and not args.allow_size_change:
        raise SystemExit(
            f"decoded payload size changed: {len(old_payload)} -> {len(new_payload)}; "
            "refusing until page metadata updating is decoded"
        )
    report = patch_resource_entry(args.rpf_out, args.entry, replacement_blob)
    report["replacement_wft"] = str(args.replacement_wft)
    report["tool"] = f"codered_wft_rsc5_tool.py {TOOL_VERSION}"
    report["generated_utc"] = now()
    if args.report:
        write_json(args.report, report)
    print(json.dumps({"rpf_out": str(args.rpf_out), "report": report}, indent=2))
    return 0


def clean_path(raw: str) -> Path:
    return Path(raw.strip().strip('"').strip("'"))


def ask_path(prompt: str, *, must_exist: bool = True, default: Path | None = None) -> Path:
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            p = default
        else:
            p = clean_path(raw)
        if not must_exist or p.exists():
            return p
        print(f"Not found: {p}")


def ask_text(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or (default or "")


def default_export_dir(name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:80]
    return PACKAGE_ROOT / "exports" / safe


def run_cli_func(func: Callable[[argparse.Namespace], int], ns: argparse.Namespace) -> None:
    try:
        log(f"START {func.__name__} {vars(ns)}")
        result = func(ns)
        log(f"OK {func.__name__} result={result}")
        print("\nDone.")
    except SystemExit as exc:
        log(f"SYSTEMEXIT {func.__name__}: {exc}")
        print(f"\nStopped: {exc}")
    except Exception as exc:
        tb = traceback.format_exc()
        log(f"ERROR {func.__name__}: {exc}\n{tb}")
        print("\nERROR:")
        print(str(exc))
        print(f"\nFull details written to: {LOG_FILE}")
    pause()


def menu_scan() -> None:
    rpf_path = ask_path("RPF to scan for .wft files")
    out = ask_path("Output scan JSON", must_exist=False, default=REPORT_DIR / f"wft_scan_{rpf_path.stem}.json")
    run_cli_func(cmd_scan, argparse.Namespace(rpf=rpf_path, out=out))


def menu_export() -> None:
    rpf_path = ask_path("RPF containing the .wft")
    entry = ask_text("Internal WFT entry path, e.g. root/.../file.wft")
    out_dir = ask_path("Output folder", must_exist=False, default=default_export_dir(Path(entry).name or "wft_export"))
    run_cli_func(cmd_export, argparse.Namespace(rpf=rpf_path, entry=entry, out_dir=out_dir))


def menu_unpack() -> None:
    wft = ask_path("Standalone .wft file to unpack")
    out_dir = ask_path("Output folder", must_exist=False, default=default_export_dir(wft.stem))
    run_cli_func(cmd_unpack, argparse.Namespace(wft=wft, out_dir=out_dir))


def menu_repack() -> None:
    original = ask_path("Original standalone .wft")
    payload = ask_path("Edited same-size .rsc5_payload.bin")
    out_wft = ask_path("Output rebuilt .wft", must_exist=False, default=PACKAGE_ROOT / "rebuilt" / original.name)
    report = ask_path("Output report JSON", must_exist=False, default=REPORT_DIR / f"repack_{original.stem}.json")
    run_cli_func(cmd_repack, argparse.Namespace(original_wft=original, payload=payload, out_wft=out_wft, report=report, level=9, allow_size_change=False))


def menu_patch_payload() -> None:
    rpf_in = ask_path("Input RPF to copy and patch")
    entry = ask_text("Internal WFT entry path")
    payload = ask_path("Edited same-size .rsc5_payload.bin")
    rpf_out = ask_path("Output copied/patched RPF", must_exist=False, default=PACKAGE_ROOT / "patched_rpfs" / f"{rpf_in.stem}_patched.rpf")
    report = ask_path("Output report JSON", must_exist=False, default=REPORT_DIR / f"patch_payload_{rpf_in.stem}.json")
    run_cli_func(cmd_patch_rpf, argparse.Namespace(rpf_in=rpf_in, entry=entry, payload=payload, rpf_out=rpf_out, report=report, level=9, allow_size_change=False, overwrite=True))


def menu_patch_wft() -> None:
    rpf_in = ask_path("Input RPF to copy and patch")
    entry = ask_text("Internal WFT entry path")
    replacement = ask_path("Replacement standalone .wft")
    rpf_out = ask_path("Output copied/patched RPF", must_exist=False, default=PACKAGE_ROOT / "patched_rpfs" / f"{rpf_in.stem}_patched.rpf")
    report = ask_path("Output report JSON", must_exist=False, default=REPORT_DIR / f"patch_wft_{rpf_in.stem}.json")
    run_cli_func(cmd_patch_rpf_wft, argparse.Namespace(rpf_in=rpf_in, entry=entry, replacement_wft=replacement, rpf_out=rpf_out, report=report, allow_size_change=False, overwrite=True))


def menu_self_test() -> None:
    sample = SAMPLE_DIR / "zombie_mexicanrebel_01.wft"
    if not sample.exists():
        print(f"Sample missing: {sample}")
        pause()
        return
    out_dir = PACKAGE_ROOT / "self_test" / "unpacked"
    rebuilt = PACKAGE_ROOT / "self_test" / "zombie_mexicanrebel_01_roundtrip.wft"
    report = REPORT_DIR / "pass9_self_test_repack_report.json"
    try:
        log("START menu_self_test")
        cmd_unpack(argparse.Namespace(wft=sample, out_dir=out_dir))
        payload = out_dir / f"{sample.name}.rsc5_payload.bin"
        cmd_repack(argparse.Namespace(original_wft=sample, payload=payload, out_wft=rebuilt, report=report, level=9, allow_size_change=False))
        old_info, _, old_payload = parse_rsc5_blob(sample.read_bytes())
        new_info, _, new_payload = parse_rsc5_blob(rebuilt.read_bytes())
        result = {
            "tool": f"codered_wft_rsc5_tool.py {TOOL_VERSION}",
            "generated_utc": now(),
            "sample": str(sample),
            "rebuilt": str(rebuilt),
            "payload_sha1_same": hashlib.sha1(old_payload).hexdigest() == hashlib.sha1(new_payload).hexdigest(),
            "old": asdict(old_info),
            "new": asdict(new_info),
            "report": str(report),
        }
        write_json(REPORT_DIR / "pass9_self_test_result.json", result)
        print("\nSelf-test passed.")
        print(json.dumps({"rebuilt": str(rebuilt), "payload_sha1_same": result["payload_sha1_same"], "report": str(report)}, indent=2))
        log("OK menu_self_test")
    except Exception as exc:
        tb = traceback.format_exc()
        log(f"ERROR menu_self_test: {exc}\n{tb}")
        print("\nSelf-test failed:")
        print(str(exc))
        print(f"Full details written to: {LOG_FILE}")
    pause()


def print_help() -> None:
    print("""
WFT/RSC5 Edit Bridge - menu help
--------------------------------
This tool does not fully decode WFT meshes yet. It bridges safe resource editing:

1. Scan an RPF for .wft files.
2. Export a .wft and its decompressed RSC5 payload.
3. Edit the payload only when you can preserve its decompressed size.
4. Repack the standalone .wft or patch a copied RPF.
5. Verify by rereading the rebuilt resource.

Important limits:
- Same-size payload edits only by default.
- No production RPF is edited in place; patch commands copy the RPF first.
- If zstd is missing, install zstd or place zstd.exe where Windows can find it.
- WSC/gringo/script files are not touched by this tool.
""")
    pause()


def interactive_menu() -> int:
    ensure_dirs()
    log(f"OPEN interactive menu {TOOL_VERSION}")
    while True:
        if os.name == "nt" or os.environ.get("TERM"):
            os.system("cls" if os.name == "nt" else "clear")
        print("Code RED WFT/RSC5 Edit Bridge")
        print(f"Version: {TOOL_VERSION}")
        print(f"Package: {PACKAGE_ROOT}")
        print(f"zstd available: {zstd_available()}")
        print(f"Last-run log: {LOG_FILE}")
        print("\nChoose an action:")
        print(" 1) Scan an RPF for .wft files")
        print(" 2) Export one WFT from an RPF")
        print(" 3) Unpack standalone WFT")
        print(" 4) Repack standalone WFT from same-size payload")
        print(" 5) Patch copied RPF from edited payload")
        print(" 6) Patch copied RPF from replacement WFT")
        print(" 7) Run sample self-test")
        print(" 8) Help / limits")
        print(" 9) Exit")
        choice = input("\nSelection: ").strip().lower()
        if choice == "1":
            menu_scan()
        elif choice == "2":
            menu_export()
        elif choice == "3":
            menu_unpack()
        elif choice == "4":
            menu_repack()
        elif choice == "5":
            menu_patch_payload()
        elif choice == "6":
            menu_patch_wft()
        elif choice == "7":
            menu_self_test()
        elif choice == "8":
            print_help()
        elif choice in {"9", "q", "quit", "exit"}:
            log("EXIT interactive menu")
            return 0
        else:
            print("Unknown selection.")
            pause()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Code RED RSC5/WFT extraction and same-size edit bridge")
    ap.add_argument("--menu", action="store_true", help="Open the persistent menu")
    sub = ap.add_subparsers(required=False)

    scan = sub.add_parser("scan-rpf", help="List .wft entries in an RPF and verify RSC5/zstd payloads")
    scan.add_argument("--rpf", type=Path, required=True)
    scan.add_argument("--out", type=Path, required=True)
    scan.set_defaults(func=cmd_scan)

    exp = sub.add_parser("export", help="Export one .wft entry plus decompressed RSC5 payload")
    exp.add_argument("--rpf", type=Path, required=True)
    exp.add_argument("--entry", required=True)
    exp.add_argument("--out-dir", type=Path, required=True)
    exp.set_defaults(func=cmd_export)

    unpack = sub.add_parser("unpack", help="Unpack a standalone RSC5 .wft file")
    unpack.add_argument("--wft", type=Path, required=True)
    unpack.add_argument("--out-dir", type=Path, required=True)
    unpack.set_defaults(func=cmd_unpack)

    repack = sub.add_parser("repack", help="Repack a standalone .wft from an edited decompressed payload")
    repack.add_argument("--original-wft", type=Path, required=True)
    repack.add_argument("--payload", type=Path, required=True)
    repack.add_argument("--out-wft", type=Path, required=True)
    repack.add_argument("--report", type=Path)
    repack.add_argument("--level", type=int, default=9)
    repack.add_argument("--allow-size-change", action="store_true")
    repack.set_defaults(func=cmd_repack)

    patch = sub.add_parser("patch-rpf", help="Patch an RPF .wft resource entry from an edited decompressed payload")
    patch.add_argument("--rpf-in", type=Path, required=True)
    patch.add_argument("--entry", required=True)
    patch.add_argument("--payload", type=Path, required=True)
    patch.add_argument("--rpf-out", type=Path, required=True)
    patch.add_argument("--report", type=Path)
    patch.add_argument("--level", type=int, default=9)
    patch.add_argument("--allow-size-change", action="store_true")
    patch.add_argument("--overwrite", action="store_true")
    patch.set_defaults(func=cmd_patch_rpf)

    patch_wft = sub.add_parser("patch-rpf-wft", help="Patch an RPF .wft resource entry from a replacement standalone RSC5 .wft")
    patch_wft.add_argument("--rpf-in", type=Path, required=True)
    patch_wft.add_argument("--entry", required=True)
    patch_wft.add_argument("--replacement-wft", type=Path, required=True)
    patch_wft.add_argument("--rpf-out", type=Path, required=True)
    patch_wft.add_argument("--report", type=Path)
    patch_wft.add_argument("--allow-size-change", action="store_true")
    patch_wft.add_argument("--overwrite", action="store_true")
    patch_wft.set_defaults(func=cmd_patch_rpf_wft)
    return ap


def main() -> int:
    ensure_dirs()
    if len(sys.argv) == 1:
        return interactive_menu()
    ap = build_parser()
    args = ap.parse_args()
    if getattr(args, "menu", False):
        return interactive_menu()
    if not hasattr(args, "func"):
        ap.print_help()
        pause()
        return 0
    try:
        log(f"START cli {sys.argv[1:]}")
        result = args.func(args)
        log(f"OK cli result={result}")
        return result
    except Exception as exc:
        tb = traceback.format_exc()
        log(f"ERROR cli: {exc}\n{tb}")
        print(f"ERROR: {exc}")
        print(f"Full details written to: {LOG_FILE}")
        if os.name == "nt":
            pause()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
