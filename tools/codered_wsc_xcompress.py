"""Code RED XCompress/LZX feasibility probe for RDR XSC/CSC resources.

This is intentionally a probe/bridge, not a blind converter.  The local
SC-CL runtime ships a 32-bit xcompress32.dll; most Code RED Python runs are
64-bit, so loading it directly usually fails with WinError 193.  The tool
records that exact state and classifies donor resources without modifying
them.
"""
from __future__ import annotations

import argparse
import ctypes
import csv
import json
import os
import platform
import struct
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports" / "wsc_authoring_pass1_xcompress_probe"
SCRIPT_SUFFIXES = {".xsc", ".csc", ".wsc", ".sco"}
EXPORT_NAMES = [
    "XMemCreateCompressionContext",
    "XMemCompress",
    "XMemDestroyCompressionContext",
    "XMemCreateDecompressionContext",
    "XMemDecompress",
    "XMemDestroyDecompressionContext",
]


def sha1_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


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


def first_hex(path: Path, count: int = 32) -> str:
    return path.read_bytes()[:count].hex(" ").upper()


def resource_family(data: bytes) -> str:
    if data.startswith(b"RSC\x85"):
        return "PC_RSC85_WSC"
    if data.startswith(b"\x85CSR"):
        return "XSC_SWAPPED_RSC85"
    if data.startswith(b"\x86CSR"):
        return "CSC_SWAPPED_RSC86"
    if data.startswith(b"SCR"):
        return "SCR_STYLE_SCO"
    return "unknown"


def candidate_dlls() -> list[Path]:
    raw = [
        os.environ.get("CODERED_XCOMPRESS_DLL", ""),
        str(ROOT / "SC-CL-master" / "bin" / "xcompress32.dll"),
        str(ROOT / "SC-CL-master" / "bin" / "Release" / "xcompress32.dll"),
        str(ROOT / "SC-CL-master" / "llvm-14.0.0.src" / "tools" / "clang" / "tools" / "extra" / "SC-CL" / "bin" / "xcompress32.dll"),
        str(ROOT / "SC-CL-master" / "llvm-14.0.0.src" / "tools" / "clang" / "tools" / "extra" / "SC-CL" / "bin" / "Release" / "xcompress32.dll"),
        str(ROOT / "SC-CL-master" / "llvm-14.0.0.src" / "lib" / "xcompress64.lib"),
        str(ROOT / "script_compiling" / "sccl" / "output" / "xcompress32.dll"),
        str(ROOT / "resources" / "SC-CL-master" / "bin" / "xcompress32.dll"),
        str(ROOT.parent / "SC-CL-master" / "bin" / "xcompress32.dll"),
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for value in raw:
        if not value:
            continue
        path = Path(value)
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def export_string_hits(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {name: False for name in EXPORT_NAMES}
    data = path.read_bytes()
    return {name: (name.encode("ascii") in data) for name in EXPORT_NAMES}


def probe_dll(path: Path) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "python_architecture": platform.architecture()[0],
        "exports_seen_as_strings": export_string_hits(path),
        "load_ok": False,
        "load_error": "",
        "entrypoints_resolved": {},
    }
    if not path.exists():
        rec["status"] = "missing"
        return rec
    if path.suffix.lower() == ".lib":
        rec["status"] = "static_or_import_library_needs_native_bridge"
        rec["load_error"] = "not a DLL; link this from a small native bridge executable or DLL"
        return rec
    try:
        dll = ctypes.WinDLL(str(path))
        rec["load_ok"] = True
        for name in EXPORT_NAMES:
            try:
                getattr(dll, name)
                rec["entrypoints_resolved"][name] = True
            except AttributeError:
                rec["entrypoints_resolved"][name] = False
        rec["status"] = "loadable_signature_not_validated"
    except OSError as exc:
        rec["load_error"] = str(exc)
        if "193" in str(exc) or "%1 is not a valid Win32 application" in str(exc):
            rec["status"] = "bitness_mismatch_32bit_dll"
        else:
            rec["status"] = "load_failed"
    return rec


def inspect_resource(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    family = resource_family(data)
    rec: dict[str, Any] = {
        "path": str(path),
        "extension": path.suffix.lower(),
        "size": len(data),
        "sha1": sha1_file(path),
        "first_32_bytes_hex": data[:32].hex(" ").upper(),
        "family": family,
        "decode_status": "not_attempted",
        "conversion_status": "manual_review",
        "note": "",
    }
    if family == "XSC_SWAPPED_RSC85":
        normalized = b"".join(data[i : i + 4][::-1] for i in range(0, len(data) - (len(data) % 4), 4)) + data[len(data) - (len(data) % 4) :]
        if len(normalized) >= 16:
            _, flag1, flag2 = struct.unpack_from("<III", normalized, 4)
            rec["normalized_flag1"] = f"0x{flag1:08X}"
            rec["normalized_flag2"] = f"0x{flag2:08X}"
        rec["decode_status"] = "xcompress_probe_required"
        rec["conversion_status"] = "still_blocked"
        rec["note"] = "Wrapper is close to PC RSC85, but payload conversion requires validated XCompress/LZX decode and PC repack."
    elif family == "CSC_SWAPPED_RSC86":
        rec["decode_status"] = "rsc86_not_supported_here"
        rec["conversion_status"] = "still_blocked"
        rec["note"] = "PSN CSC RSC86 wrapper is not a PC WSC target in this pass."
    elif family == "PC_RSC85_WSC":
        rec["decode_status"] = "use_codered_wsc_inspect"
        rec["conversion_status"] = "raw_pc_resource"
        rec["note"] = "PC RSC85 resource; use python -m codered_wsc inspect/repack for real decode validation."
    elif family == "SCR_STYLE_SCO":
        rec["decode_status"] = "plain_sco_container"
        rec["conversion_status"] = "source_required_or_wrap_probe"
        rec["note"] = "SC-CL RDR_SCO output can be wrapped into PC RSC85 for a loader probe, but runtime WSC acceptance is unproven."
    else:
        rec["decode_status"] = "unknown"
        rec["conversion_status"] = "manual_review"
    return rec


def collect_inputs(sources: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in sources:
        source = Path(raw)
        if source.is_file():
            paths.append(source)
        elif source.is_dir():
            paths.extend(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in SCRIPT_SUFFIXES)
    return sorted(dict.fromkeys(paths), key=lambda p: str(p).lower())


def write_report(out: Path, dll_rows: list[dict[str, Any]], resource_rows: list[dict[str, Any]]) -> None:
    write_json(out / "xcompress_probe.json", {"dlls": dll_rows, "resources": resource_rows})
    write_csv(out / "xcompress_resource_probe.csv", resource_rows)
    lines = [
        "# XSC/CSC XCompress Feasibility",
        "",
        "This probe does not modify donor files and does not fake conversion by extension rename.",
        "",
        "## XCompress Runtime",
        "",
    ]
    for row in dll_rows:
        lines.extend(
            [
                f"- `{row['path']}`",
                f"  - exists: `{row['exists']}`",
                f"  - status: `{row['status']}`",
                f"  - load_error: `{row.get('load_error', '')}`",
            ]
        )
    counts: dict[str, int] = {}
    for row in resource_rows:
        counts[row["conversion_status"]] = counts.get(row["conversion_status"], 0) + 1
    lines.extend(["", "## Conversion Status", ""])
    if counts:
        for status, count in sorted(counts.items()):
            lines.append(f"- `{status}`: `{count}`")
    else:
        lines.append("- No script resources were scanned.")
    lines.extend(
        [
            "",
            "## Pass 1 Decision",
            "",
            "XSC/CSC conversion remains blocked unless a loadable XCompress bridge with validated signatures is available. "
            "The safe build lane for this pass is source-required authoring through SC-CL RDR_SCO plus PC RSC85 wrapping/repack validation.",
        ]
    )
    report_text = "\n".join(lines) + "\n"
    (out / "xsc_csc_conversion_feasibility.md").write_text(report_text, encoding="utf-8")
    required_top_level = ROOT / "reports" / "xsc_csc_conversion_feasibility.md"
    if required_top_level.resolve() != (out / "xsc_csc_conversion_feasibility.md").resolve():
        required_top_level.parent.mkdir(parents=True, exist_ok=True)
        required_top_level.write_text(report_text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe XCompress/LZX feasibility for RDR XSC/CSC donor scripts.")
    parser.add_argument("--source", action="append", default=[], help="Script file or folder to classify. Can be repeated.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output report folder.")
    args = parser.parse_args(argv)

    out = Path(args.out)
    dll_rows = [probe_dll(path) for path in candidate_dlls()]
    resource_rows = [inspect_resource(path) for path in collect_inputs(args.source)]
    write_report(out, dll_rows, resource_rows)
    print(json.dumps({"status": "probed", "out": str(out), "dlls": len(dll_rows), "resources": len(resource_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
