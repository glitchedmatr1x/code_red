#!/usr/bin/env python3
"""Create a generic SCXML replacement candidate folder for copied-RPF builds.

Use this when you have decoded or encoded UI `.sc.xml` replacement files from a
convert/inject folder and want to feed them into the existing copied RPF builder
without hand-writing candidate_summary.json / zstd_roundtrip_report.json.

The output schema is intentionally compatible with:

    tools/codered_mp_lan_fallback_rpf_builder.py --candidate-dir <out>

This helper does not modify RPF archives. It only prepares candidate payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Iterable

try:
    import zstandard as zstd
except Exception:
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "logs" / "content_mp_menu_exposure_candidate"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

DEFAULT_APPROVED = {
    "root/content/ui/pausemenu/networking.sc.xml",
    "root/content/ui/pausemenu/options.sc.xml",
    "root/content/ui/pausemenu/pausemenuscene.sc.xml",
    "root/content/ui/generalmenus.sc.xml",
    "root/content/ui/pausemenu/net/offlinemenu.sc.xml",
    "root/content/ui/pausemenu/net/lanmenu.sc.xml",
    "root/content/ui/pausemenu/net/plaympconf.sc.xml",
}


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def clean_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:220]


def is_zstd(data: bytes) -> bool:
    return data.startswith(ZSTD_MAGIC)


def zstd_decode(data: bytes) -> bytes:
    if zstd is None:
        raise RuntimeError("Python zstandard is required: py -3 -m pip install zstandard")
    return zstd.ZstdDecompressor().decompress(data)


def zstd_encode(data: bytes) -> bytes:
    if zstd is None:
        raise RuntimeError("Python zstandard is required: py -3 -m pip install zstandard")
    return zstd.ZstdCompressor(level=3).compress(data)


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if path.is_file():
            yield path


def infer_archive_path(path: Path, source_root: Path) -> str | None:
    name = path.name
    low = name.lower()

    # Common decoded output naming:
    # root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml
    # root_content_ui_pausemenu_networking.sc.xml.decoded.xml
    stem = name
    for suffix in (".decoded.xml", ".decoded.txt", ".zstd", ".zst"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem.lower().endswith(".sc.xml"):
        tokens = stem.split("_")
        if tokens and tokens[0].lower() == "root":
            return "/".join(tokens)

    # Relative folder shape from an extracted replacement root:
    # root/content/ui/pausemenu/networking.sc.xml
    try:
        rel = path.relative_to(source_root).as_posix()
    except Exception:
        rel = name
    rel_low = rel.lower()
    if rel_low.startswith("root/content/") and ".sc.xml" in rel_low:
        archive = rel
        for suffix in (".decoded.xml", ".decoded.txt", ".zstd", ".zst"):
            if archive.lower().endswith(suffix):
                archive = archive[: -len(suffix)]
                break
        return archive

    # Flat known names.
    flat = low
    for suffix in (".decoded.xml", ".decoded.txt", ".zstd", ".zst"):
        if flat.endswith(suffix):
            flat = flat[: -len(suffix)]
            break
    flat_map = {
        "networking.sc.xml": "root/content/ui/pausemenu/networking.sc.xml",
        "options.sc.xml": "root/content/ui/pausemenu/options.sc.xml",
        "pausemenuscene.sc.xml": "root/content/ui/pausemenu/pausemenuscene.sc.xml",
        "generalmenus.sc.xml": "root/content/ui/generalmenus.sc.xml",
        "offlinemenu.sc.xml": "root/content/ui/pausemenu/net/offlinemenu.sc.xml",
        "lanmenu.sc.xml": "root/content/ui/pausemenu/net/lanmenu.sc.xml",
        "plaympconf.sc.xml": "root/content/ui/pausemenu/net/plaympconf.sc.xml",
    }
    return flat_map.get(flat)


def load_mapping(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        if isinstance(data, list):
            out = {}
            for row in data:
                out[str(row["source"])] = str(row["archive_path"])
            return out
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            src, dst = line.split(",", 1)
        elif "=>" in line:
            src, dst = line.split("=>", 1)
        elif "=" in line:
            src, dst = line.split("=", 1)
        else:
            continue
        out[src.strip()] = dst.strip()
    return out


def resolve_mapped_archive_path(path: Path, source_root: Path, mapping: dict[str, str]) -> str | None:
    keys = [path.name, str(path), path.as_posix()]
    try:
        keys.append(path.relative_to(source_root).as_posix())
    except Exception:
        pass
    for key in keys:
        if key in mapping:
            return mapping[key].replace("\\", "/")
    return infer_archive_path(path, source_root)


def prepare_candidate(replacements: Path, out_dir: Path, mapping_file: Path | None, allow_unapproved: bool) -> dict:
    if not replacements.exists():
        raise FileNotFoundError(f"Replacement folder/file not found: {replacements}")
    out_dir.mkdir(parents=True, exist_ok=True)
    decoded_dir = out_dir / "decoded_candidates"
    encoded_dir = out_dir / "zstd_encoded"
    decoded_dir.mkdir(parents=True, exist_ok=True)
    encoded_dir.mkdir(parents=True, exist_ok=True)

    mapping = load_mapping(mapping_file)
    candidate_files = []
    rows = []
    skipped = []
    seen_archive_paths = set()

    for path in iter_files(replacements):
        archive_path = resolve_mapped_archive_path(path, replacements if replacements.is_dir() else path.parent, mapping)
        if not archive_path:
            skipped.append({"path": str(path), "reason": "could_not_infer_archive_path"})
            continue
        archive_path = archive_path.replace("\\", "/")
        if not archive_path.lower().endswith(".sc.xml"):
            skipped.append({"path": str(path), "archive_path": archive_path, "reason": "not_scxml"})
            continue
        if not allow_unapproved and archive_path.lower() not in DEFAULT_APPROVED:
            skipped.append({"path": str(path), "archive_path": archive_path, "reason": "not_in_default_approved_menu_exposure_set"})
            continue
        if archive_path.lower() in seen_archive_paths:
            skipped.append({"path": str(path), "archive_path": archive_path, "reason": "duplicate_archive_path"})
            continue
        raw = path.read_bytes()
        if is_zstd(raw):
            decoded = zstd_decode(raw)
            encoded = raw
        else:
            decoded = raw
            encoded = zstd_encode(decoded)
        safe = clean_name(archive_path.replace("/", "_"))
        decoded_path = decoded_dir / f"{safe}.decoded.xml"
        encoded_path = encoded_dir / f"{safe}.zstd"
        decoded_path.write_bytes(decoded)
        encoded_path.write_bytes(encoded)
        decoded2 = zstd_decode(encoded)
        ok = decoded2 == decoded
        row = {
            "archive_path": archive_path,
            "source_path": str(path),
            "decoded_path": str(decoded_path),
            "encoded_path": str(encoded_path),
            "decoded_sha1": sha1_bytes(decoded),
            "encoded_sha1": sha1_bytes(encoded),
            "encoded_size": len(encoded),
            "decoded_size": len(decoded),
            "roundtrip_ok": ok,
        }
        rows.append(row)
        candidate_files.append(
            {
                "archive_path": archive_path,
                "source_path": str(path),
                "candidate_decoded": str(decoded_path),
                "candidate_encoded": str(encoded_path),
                "decoded_sha1": row["decoded_sha1"],
                "encoded_sha1": row["encoded_sha1"],
                "decoded_size": row["decoded_size"],
                "encoded_size": row["encoded_size"],
            }
        )
        seen_archive_paths.add(archive_path.lower())

    status = "pass" if candidate_files and all(row["roundtrip_ok"] for row in rows) else "fail"
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "source_replacements": str(replacements),
        "candidate_file_count": len(candidate_files),
        "candidate_files": candidate_files,
        "skipped": skipped,
        "approved_archive_paths": sorted(DEFAULT_APPROVED),
        "notes": [
            "This prepares candidate payloads only; it does not modify an RPF.",
            "Feed this folder to tools/codered_mp_lan_fallback_rpf_builder.py --candidate-dir.",
        ],
    }
    roundtrip = {
        "generated_at": summary["generated_at"],
        "status": status,
        "candidate_count": len(rows),
        "ok_count": sum(1 for row in rows if row["roundtrip_ok"]),
        "failed_count": sum(1 for row in rows if not row["roundtrip_ok"]),
        "rows": rows,
    }
    (out_dir / "candidate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "zstd_roundtrip_report.json").write_text(json.dumps(roundtrip, indent=2), encoding="utf-8")
    lines = [
        "# Code RED SCXML Replacement Candidate",
        "",
        f"Status: `{status}`",
        f"Source replacements: `{replacements}`",
        f"Candidate files: `{len(candidate_files)}`",
        "",
        "## Candidate archive paths",
    ]
    for item in candidate_files:
        lines.append(f"- `{item['archive_path']}` <- `{item['source_path']}`")
    if skipped:
        lines.extend(["", "## Skipped", ""])
        for row in skipped[:100]:
            lines.append(f"- `{row.get('path')}` :: {row.get('reason')} {row.get('archive_path', '')}")
    (out_dir / "SCXML_REPLACEMENT_CANDIDATE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare generic SCXML replacement candidate payloads for copied-RPF builds.")
    parser.add_argument("--replacements", type=Path, required=True, help="Folder or file containing decoded XML or encoded Zstd .sc.xml replacements.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--map", type=Path, default=None, help="Optional JSON/CSV/TXT mapping of source file name/path to archive path.")
    parser.add_argument("--allow-unapproved", action="store_true", help="Allow archive paths outside the default MP menu exposure allow-list.")
    args = parser.parse_args(argv)
    summary = prepare_candidate(args.replacements, args.out, args.map, args.allow_unapproved)
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
