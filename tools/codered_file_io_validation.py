#!/usr/bin/env python3
"""Validate full-file and RPF entry read/decode readiness for Code RED."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from codered_rpf_utils import extract_entries, parse_archive, write_inventory


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def discover_rpfs(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for folder in (root / "imports", root / "game", root, root.parent / "game"):
        if folder.exists():
            candidates.extend(sorted(folder.glob("*.rpf")))
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()).lower()
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def validate(root: Path, sample_limit: int) -> dict:
    logs = root / "logs"
    out_root = logs / "file_io_validation"
    out_root.mkdir(parents=True, exist_ok=True)
    archives = []
    for archive in discover_rpfs(root):
        archive_out = out_root / archive.stem
        try:
            inv = write_inventory(archive, archive_out)
            info = parse_archive(archive)
            first_file = next((ent for ent in info.get("entries", []) if ent.get("type") == "file"), None)
            if first_file is None:
                raise RuntimeError("No file entries found")
            extract = extract_entries(archive, archive_out / "sample_extract", all_entries=False, entry_ref=str(first_file.get("index")))
            archives.append({"archive": str(archive), "inventory": inv, "sample_extract": extract, "ok": extract.get("fail_count") == 0})
        except Exception as exc:
            archives.append({"archive": str(archive), "ok": False, "error": str(exc)})
        if len(archives) >= sample_limit:
            break
    report = {
        "generated_utc": utc_now(),
        "root": str(root),
        "archives_checked": len(archives),
        "ok_count": sum(1 for item in archives if item.get("ok")),
        "fail_count": sum(1 for item in archives if not item.get("ok")),
        "archives": archives,
        "status": "PASS" if archives and all(item.get("ok") for item in archives) else "WARN",
    }
    (logs / "CodeRED_File_IO_Validation_Report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (logs / "CodeRED_File_IO_Validation_Report.md").write_text(
        "# Code RED File IO / Full Decode Validation\n\n"
        f"Generated UTC: `{report['generated_utc']}`\n\n"
        f"Status: **{report['status']}**\n\n"
        f"- Archives checked: `{report['archives_checked']}`\n"
        f"- OK: `{report['ok_count']}`\n"
        f"- Failed: `{report['fail_count']}`\n\n"
        "Detailed data: `CodeRED_File_IO_Validation_Report.json`\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED file IO validation")
    parser.add_argument("--root", default=".")
    parser.add_argument("--sample-limit", type=int, default=4)
    args = parser.parse_args(argv)
    print(json.dumps(validate(Path(args.root).resolve(), args.sample_limit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
