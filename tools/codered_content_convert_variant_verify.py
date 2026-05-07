#!/usr/bin/env python3
"""Verify copied content.rpf multiplayer restoration candidates."""
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
DEFAULT_REPORT = ROOT / "logs" / "content_convert_overlay" / "variant_verification_report.json"
DEFAULT_VARIANTS = {
    "lan_fallback": ROOT / "build" / "content_mp_lan_fallback_test" / "content.rpf",
    "support_aliases": ROOT / "build" / "content_convert_variants" / "support_aliases" / "content.rpf",
    "convert_ui": ROOT / "build" / "content_convert_variants" / "convert_ui" / "content.rpf",
}
REQUIRED_MP = [
    "root/content/release/multiplayer/freemode/freemode.csc",
    "root/content/release64/multiplayer/freemode/freemode.csc",
    "root/content/release/multiplayer/mp_idle.csc",
    "root/content/release64/multiplayer/mp_idle.csc",
]
UI_PROBES = [
    "root/content/ui/pausemenu/net/offlinemenu.sc.xml",
    "root/content/ui/pausemenu/net/plaympconf.sc.xml",
    "root/content/ui/pausemenu/net/lanmenu.sc.xml",
    "root/content/ui/pausemenu/networking.sc.xml",
]


def load_backend():
    spec = importlib.util.spec_from_file_location("codered_workbench_backend", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_variant(wb, name: str, path: Path) -> dict:
    info = wb.parse_rpf6(path)
    if info is None:
        return {"variant": name, "path": str(path), "status": "fail", "error": "RPF did not parse"}

    file_entries = [entry for entry in info["entries"] if entry.get("type") == "file"]
    paths = {str(entry.get("path") or "").replace("\\", "/").lower(): entry for entry in file_entries}
    seen: dict[str, int] = {}
    for entry in file_entries:
        entry_path = str(entry.get("path") or "").replace("\\", "/").lower()
        seen[entry_path] = seen.get(entry_path, 0) + 1

    item = {
        "variant": name,
        "path": str(path),
        "status": "pass",
        "size": path.stat().st_size,
        "entry_count": info["entry_count"],
        "file_count": info["file_count"],
        "dir_count": info["dir_count"],
        "mp_csc_count": sum(1 for entry_path in paths if "/multiplayer/" in entry_path and entry_path.endswith(".csc")),
        "duplicate_path_count": sum(1 for count in seen.values() if count > 1),
        "required": [],
        "ui_probe": [],
    }
    for required in REQUIRED_MP:
        item["required"].append({"check": required, "ok": required.lower() in paths})

    blob = path.read_bytes()
    dctx = zstd.ZstdDecompressor() if zstd is not None else None
    for probe_path in UI_PROBES:
        entry = paths.get(probe_path.lower())
        probe = {"path": probe_path, "present": entry is not None}
        if entry is not None:
            offset = int(entry["offset"])
            size = int(entry["size_in_archive"])
            payload = blob[offset:offset + size]
            probe.update(
                {
                    "entry_index": int(entry["index"]),
                    "stored_size": size,
                    "offset": offset,
                    "name_off": f"0x{int(entry['name_off']):08X}",
                    "zstd_magic": payload[:4].hex() == "28b52ffd",
                }
            )
            if dctx is None:
                probe["decode_ok"] = False
                probe["error"] = "Python zstandard is not installed"
            else:
                try:
                    decoded = dctx.decompress(payload)
                    probe.update(
                        {
                            "decode_ok": True,
                            "decoded_size": len(decoded),
                            "decoded_sha1": hashlib.sha1(decoded).hexdigest(),
                            "xml_like": decoded.lstrip().startswith((b"<", b"<?xml")),
                        }
                    )
                except Exception as exc:
                    probe.update({"decode_ok": False, "error": str(exc)})
        item["ui_probe"].append(probe)

    if item["duplicate_path_count"] or not all(row["ok"] for row in item["required"]):
        item["status"] = "fail"
    if not all((not row["present"]) or row.get("decode_ok") for row in item["ui_probe"]):
        item["status"] = "fail"
    return item


def parse_variant(values: list[str]) -> dict[str, Path]:
    if not values:
        return DEFAULT_VARIANTS
    variants: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Variant must be NAME=PATH: {value}")
        name, path = value.split("=", 1)
        variants[name] = Path(path)
    return variants


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify copied content.rpf multiplayer restoration candidates.")
    parser.add_argument("--variant", action="append", default=[], help="Variant in NAME=PATH form. Defaults to the three current candidates.")
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    wb = load_backend()
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "RPF parser maps hashed UI aliases 0x118473D0 and 0x1374443B to offlinemenu.sc.xml and plaympconf.sc.xml by name hash.",
        "variants": [verify_variant(wb, name, path) for name, path in parse_variant(args.variant).items()],
    }
    report["status"] = "pass" if all(item.get("status") == "pass" for item in report["variants"]) else "fail"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
