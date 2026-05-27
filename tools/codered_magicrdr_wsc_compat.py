#!/usr/bin/env python3
"""Run Magic RDR's script parser against standalone WSC files.

The local MagicRDR.exe is 32-bit .NET Framework, so this wrapper invokes the
PowerShell compatibility script through SysWOW64 PowerShell and records the
actual parser result/error as CSV/JSON/Markdown.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PS1 = ROOT / "tools" / "codered_magicrdr_wsc_compat.ps1"
DEFAULT_MAGIC = ROOT.parent / "game" / "BACKUP BEFORE MODDING" / "rdr1" / "mods" / "Magic-RDR-main"
DEFAULT_OUT = ROOT / "reports" / "mp_script_conversion_probe" / "magicrdr_wsc_compat"
POWERSHELL32 = Path(__import__("os").environ.get("WINDIR", r"%LOCAL_PATH%")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def collect_wsc(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() == ".wsc" else []
    return sorted((p for p in source.rglob("*.wsc") if p.is_file()), key=lambda p: str(p).lower()) if source.exists() else []


def run_one(path: Path, ps1: Path, magic_dir: Path, platform: str, reader_endian: str, timeout: int) -> dict[str, Any]:
    path = path.resolve()
    ps1 = ps1.resolve()
    magic_dir = magic_dir.resolve()
    command = [
        str(POWERSHELL32),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-InputPath",
        str(path),
        "-MagicRdrDir",
        str(magic_dir),
        "-Platform",
        platform,
    ]
    if reader_endian != "Auto":
        command.extend(["-ReaderEndian", reader_endian])
    started = time.time()
    row: dict[str, Any] = {
        "input": str(path),
        "file_name": path.name,
        "platform": platform,
        "reader_endian_requested": reader_endian,
        "returncode": "",
        "duration_seconds": "",
        "ok": False,
        "decoded_size": 0,
        "object_start": 0,
        "function_count": 0,
        "decompiled_chars": 0,
        "error": "",
        "error_type": "",
        "stdout": "",
        "stderr": "",
    }
    try:
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, check=False)
        row["returncode"] = proc.returncode
        row["duration_seconds"] = round(time.time() - started, 3)
        row["stdout"] = proc.stdout.strip()
        row["stderr"] = proc.stderr.strip()
        payload = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
        try:
            parsed = json.loads(payload)
            row.update(parsed)
            row["returncode"] = proc.returncode
        except Exception as exc:
            row["error"] = f"Could not parse MagicRDR compat JSON: {exc}"
        return row
    except Exception as exc:
        row["duration_seconds"] = round(time.time() - started, 3)
        row["error"] = str(exc)
        row["error_type"] = type(exc).__name__
        return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_reports(out: Path, rows: list[dict[str, Any]], title: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "magicrdr_wsc_compat_report.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_csv(out / "magicrdr_wsc_compat_report.csv", rows)
    passed = sum(1 for row in rows if str(row.get("ok")).lower() == "true")
    lines = [
        f"# {title}",
        "",
        f"- Files tested: `{len(rows)}`",
        f"- Magic RDR parser passes: `{passed}`",
        f"- Magic RDR parser failures: `{len(rows) - passed}`",
        "",
        "## Results",
        "",
        "| File | OK | Functions | Decoded size | Object start | Error |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{Path(str(row.get('input', ''))).name}` | `{row.get('ok')}` | `{row.get('function_count', 0)}` | "
            f"`{row.get('decoded_size', 0)}` | `{row.get('object_start', 0)}` | `{str(row.get('error', '')).replace('|', '/')}` |"
        )
    (out / "magicrdr_wsc_compat_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Test WSC files through Magic RDR's script parser.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--magic-dir", default=str(DEFAULT_MAGIC))
    parser.add_argument("--ps1", default=str(DEFAULT_PS1))
    parser.add_argument("--platform", default="Switch", choices=["Switch", "Xbox", "PS3"])
    parser.add_argument("--reader-endian", default="Auto", choices=["Auto", "Little", "Big"])
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--title", default="Magic RDR WSC Compatibility")
    args = parser.parse_args()

    rows = [run_one(path, Path(args.ps1), Path(args.magic_dir), args.platform, args.reader_endian, args.timeout) for path in collect_wsc(Path(args.source))]
    write_reports(Path(args.out), rows, args.title)
    passed = sum(1 for row in rows if str(row.get("ok")).lower() == "true")
    print(json.dumps({"tested": len(rows), "passed": passed, "failed": len(rows) - passed, "out": args.out}, indent=2))
    return 0 if rows and passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
