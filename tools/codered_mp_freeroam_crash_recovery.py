"""Build Code RED MP Free Roam crash-recovery RPF variants.

This is a bisect pass, not another combined experiment.  It backs up the
currently installed crashing ``game/content.rpf``, restores the live game to the
last known Pass 5 boot candidate, then builds isolated test variants so each
layer can be tested independently.
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
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GAME_CONTENT = ROOT.parent / "game" / "content.rpf"
BUILD_ROOT = ROOT / "build" / "mp_freeroam_crash_recovery"
REPORTS_ROOT = BUILD_ROOT / "reports"
OVERLAY_TOOL = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
UTILS_TOOL = ROOT / "tools" / "codered_rpf_utils.py"

PASS5_RPF = ROOT / "build" / "mp_content_restore_pass5" / "content_mp_restore_pass5_access_trainer_sectors.rpf"
PASS4_TREE = ROOT / "build" / "mp_content_restore_pass4" / "import_ready_full_tree"
PASS4_BACKUPS = ROOT / "build" / "mp_content_restore_pass4" / "original_backups"
PASS2_DROPIN = ROOT / "build" / "mp_bootstrap_pass2" / "dropin"
PASS3_DROPPIN = ROOT / "build" / "mp_freeroam_pass3" / "dropin_import_ready"

XML_SOURCES = [
    (
        ROOT
        / "build"
        / "mp_content_restore_pass5"
        / "xml_candidates"
        / "combined"
        / "content__ui__pausemenu__pausemenuscene.sc.xml.decoded.xml",
        "root/content/ui/pausemenu/pausemenuscene.sc.xml",
    ),
    (
        ROOT
        / "build"
        / "mp_content_restore_pass5"
        / "xml_candidates"
        / "combined"
        / "content__ui__pausemenu__networking.sc.xml.decoded.xml",
        "root/content/ui/pausemenu/networking.sc.xml",
    ),
    (
        ROOT / "build" / "mp_content_restore_pass4" / "import_ready_full_tree" / "_ui_patch" / "lanmenu.sc.xml.decoded.xml",
        "root/content/ui/pausemenu/net/lanmenu.sc.xml",
    ),
]

BOOTSTRAP_WSC = (
    PASS2_DROPIN
    / "content"
    / "release64"
    / "scripting"
    / "designerdefined"
    / "codered_mp_bootstrap_minimal.wsc"
)
PATCHED_LONG_WSC = (
    PASS2_DROPIN
    / "content"
    / "release64"
    / "scripting"
    / "designerdefined"
    / "long_update_thread.wsc"
)
BOOTSTRAP_ARCHIVE = "root/content/release64/scripting/designerdefined/codered_mp_bootstrap_minimal.wsc"
LONG_ARCHIVE = "root/content/release64/scripting/designerdefined/long_update_thread.wsc"


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"


def file_meta(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path),
        "size": len(data),
        "sha1": sha1_bytes(data),
        "crc32": crc32_bytes(data),
    }


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


def find_clean_original() -> Path:
    candidates = sorted(PASS4_BACKUPS.glob("content_original_*.rpf"))
    if not candidates:
        raise FileNotFoundError(f"No clean original content backup under {PASS4_BACKUPS}")
    return candidates[0]


def collect_mp_tree_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    content_root = PASS4_TREE / "content"
    for path in sorted(content_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(PASS4_TREE).as_posix()
        if not (rel.startswith("content/release/multiplayer/") or rel.startswith("content/release64/multiplayer/")):
            continue
        data = path.read_bytes()
        rows.append(
            {
                "source_path": str(path),
                "archive_path": "root/" + rel,
                "payload": data,
                "size": len(data),
                "sha1": sha1_bytes(data),
                "layer": "mp_tree",
                "allow_resource_replace": False,
            }
        )
    return rows


def collect_xml_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, archive_path in XML_SOURCES:
        data = source.read_bytes()
        rows.append(
            {
                "source_path": str(source),
                "archive_path": archive_path,
                "payload": data,
                "size": len(data),
                "sha1": sha1_bytes(data),
                "layer": "xml_route",
                "allow_resource_replace": False,
            }
        )
    return rows


def collect_bootstrap_row() -> dict[str, Any]:
    data = BOOTSTRAP_WSC.read_bytes()
    return {
        "source_path": str(BOOTSTRAP_WSC),
        "archive_path": BOOTSTRAP_ARCHIVE,
        "payload": data,
        "size": len(data),
        "sha1": sha1_bytes(data),
        "layer": "bootstrap_file",
        "allow_resource_replace": True,
    }


def collect_long_patch_row() -> dict[str, Any]:
    data = PATCHED_LONG_WSC.read_bytes()
    return {
        "source_path": str(PATCHED_LONG_WSC),
        "archive_path": LONG_ARCHIVE,
        "payload": data,
        "size": len(data),
        "sha1": sha1_bytes(data),
        "layer": "long_thread_patch",
        "allow_resource_replace": True,
    }


def build_overlay_rpf(source_rpf: Path, output_rpf: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    overlay = load_module(OVERLAY_TOOL, "codered_overlay_recovery")
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
            allow_resource_replace=bool(row.get("allow_resource_replace")),
        )
        operations.append(
            {
                "archive_path": row["archive_path"],
                "source_path": row["source_path"],
                "layer": row["layer"],
                "action": action,
                "resource_replace": node.resource_replace,
                "decoded_size": len(row["payload"]),
                "stored_size": node.stored_size,
                "compressed": node.force_compressed,
                "sha1": row["sha1"],
            }
        )

    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    file_offsets = [int(entry["offset"]) for entry in info["entries"] if entry.get("type") == "file"]
    if not file_offsets:
        raise RuntimeError("Source archive has no file entries")
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


def verify_rows(output_rpf: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    utils = load_module(UTILS_TOOL, "codered_rpf_utils_recovery")
    wb = utils.load_backend()
    info = utils.parse_archive(output_rpf)
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            entry = utils.find_entry(info, row["archive_path"])
            data = utils.extract_entry_payload(wb, output_rpf, entry)
            if row["archive_path"].lower().endswith(".wsc") and row["payload"][:4] == b"RSC\x85" and data[:4] != b"RSC\x85":
                status = "resource_payload_readable"
            else:
                status = "exact_match" if sha1_bytes(data) == row["sha1"] else "mismatch"
            results.append(
                {
                    "archive_path": row["archive_path"],
                    "layer": row["layer"],
                    "status": status,
                    "entry_index": entry.get("index"),
                    "expected_size": len(row["payload"]),
                    "actual_size": len(data),
                    "expected_sha1": row["sha1"],
                    "actual_sha1": sha1_bytes(data),
                    "note": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "archive_path": row["archive_path"],
                    "layer": row["layer"],
                    "status": "error",
                    "entry_index": "",
                    "expected_size": len(row["payload"]),
                    "actual_size": "",
                    "expected_sha1": row["sha1"],
                    "actual_sha1": "",
                    "note": str(exc),
                }
            )
    return results


def copy_rpf(source: Path, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    return {"source": file_meta(source), "output": file_meta(output), "operations": []}


def backup_live() -> dict[str, Any]:
    if not GAME_CONTENT.exists():
        raise FileNotFoundError(GAME_CONTENT)
    meta = file_meta(GAME_CONTENT)
    backup = BUILD_ROOT / "original_backups" / f"live_crash_content_{meta['sha1'][:12]}.rpf"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(GAME_CONTENT, backup)
    return {"live_before": meta, "backup": file_meta(backup)}


def restore_live_from_pass5(pass5: Path) -> dict[str, Any]:
    shutil.copy2(pass5, GAME_CONTENT)
    return {"restored_from": file_meta(pass5), "live_after": file_meta(GAME_CONTENT)}


def write_reports(summary: dict[str, Any], variant_rows: list[dict[str, Any]], verification_rows: list[dict[str, Any]]) -> None:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(REPORTS_ROOT / "mp_freeroam_crash_recovery_summary.json", summary)
    write_csv(REPORTS_ROOT / "mp_freeroam_crash_recovery_variants.csv", variant_rows)
    write_csv(REPORTS_ROOT / "mp_freeroam_crash_recovery_verification.csv", verification_rows)

    report = ["# Code RED MP Free Roam Crash Recovery", ""]
    report.append("## Live Recovery")
    report.append("")
    report.append(f"- Live crash backup: `{summary['live_backup']['backup']['path']}`")
    report.append(f"- Live `game/content.rpf` restored from: `{summary['live_restore']['restored_from']['path']}`")
    report.append("")
    report.append("## Variants")
    report.append("")
    for row in variant_rows:
        report.append(f"- `{row['variant']}`: `{row['path']}`")
        report.append(f"  - layers: `{row['layers']}`")
        report.append(f"  - risk: `{row['risk']}`")
        report.append(f"  - sha1: `{row['sha1']}`")
        report.append(f"  - note: {row['note']}")
    report.append("")
    report.append("## Decision Rule")
    report.append("")
    report.append("- Test A first to confirm the known-boot base is restored.")
    report.append("- Test B and C separately before testing any WSC layer.")
    report.append("- Test D before E.  E is high risk because it redirects a script path to a missing WSC.")
    report.append("- F intentionally contains no new launcher because no safer later/manual slot is proven yet; use the trainer path after a booting RPF is confirmed.")
    write_text(REPORTS_ROOT / "mp_freeroam_crash_recovery_report.md", "\n".join(report) + "\n")

    steps = """# Code RED MP Free Roam Crash Recovery Test Matrix

Test in this order, restoring the listed RPF before each test:

1. A `baseline_pass5_known_boot.rpf`
   - Expected: boots, MP/network options visible.
2. B `xml_only_route.rpf`
   - Expected: boots, XML route behavior isolated from MP tree and WSC hook.
3. C `mp_tree_only.rpf`
   - Expected: boots if raw restored MP files are not the crash source.
4. D `bootstrap_file_only_no_launcher.rpf`
   - Expected: boots if merely adding the bootstrap WSC does not crash.
5. E `long_thread_patch_only_no_bootstrap.rpf`
   - HIGH RISK.  Expected: may crash or missing-script fail if the replaced long-thread path fires.
6. F `bootstrap_launcher_delayed.rpf`
   - No delayed launcher was injected.  This is the safe placeholder for trainer/hotkey launch testing after a booting RPF is confirmed.

For each run record: boot/no boot, menu reached, selected route reached, crash stage, latest log snippets, and Windows fault module.
"""
    write_text(REPORTS_ROOT / "mp_freeroam_crash_recovery_test_matrix.md", steps)


def build() -> dict[str, Any]:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

    clean_original = find_clean_original()
    for required in [PASS5_RPF, clean_original, BOOTSTRAP_WSC, PATCHED_LONG_WSC]:
        if not required.exists():
            raise FileNotFoundError(required)

    live_backup = backup_live()

    variants_dir = BUILD_ROOT / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    variant_rows: list[dict[str, Any]] = []
    verification_rows: list[dict[str, Any]] = []

    def add_variant(name: str, path: Path, layers: str, risk: str, note: str) -> None:
        meta = file_meta(path)
        variant_rows.append(
            {
                "variant": name,
                "path": str(path),
                "size": meta["size"],
                "sha1": meta["sha1"],
                "crc32": meta["crc32"],
                "layers": layers,
                "risk": risk,
                "note": note,
            }
        )

    baseline = variants_dir / "baseline_pass5_known_boot.rpf"
    copy_rpf(PASS5_RPF, baseline)
    add_variant("A_baseline_pass5_known_boot", baseline, "pass5_mp_tree+xml_route", "low", "Known-boot candidate regenerated from Pass 4 base.")

    xml_rows = collect_xml_rows()
    xml_only = variants_dir / "xml_only_route.rpf"
    build_overlay_rpf(clean_original, xml_only, xml_rows)
    verification_rows.extend({"variant": "B_xml_only_route", **row} for row in verify_rows(xml_only, xml_rows))
    add_variant("B_xml_only_route", xml_only, "xml_route_only", "low", "Clean original plus Pass 5/variant 02 XML route files only.")

    mp_rows = collect_mp_tree_rows()
    mp_tree = variants_dir / "mp_tree_only.rpf"
    build_overlay_rpf(clean_original, mp_tree, mp_rows)
    verification_rows.extend({"variant": "C_mp_tree_only", **row} for row in verify_rows(mp_tree, mp_rows[:8]))
    add_variant("C_mp_tree_only", mp_tree, "mp_tree_only", "medium", "Clean original plus restored release/release64 MP directories; no XML or WSC hook.")

    bootstrap_rows = [collect_bootstrap_row()]
    bootstrap_only = variants_dir / "bootstrap_file_only_no_launcher.rpf"
    build_overlay_rpf(clean_original, bootstrap_only, bootstrap_rows)
    verification_rows.extend({"variant": "D_bootstrap_file_only_no_launcher", **row} for row in verify_rows(bootstrap_only, bootstrap_rows))
    add_variant("D_bootstrap_file_only_no_launcher", bootstrap_only, "bootstrap_wsc_file_only", "medium", "Adds bootstrap WSC path but does not launch it.")

    long_rows = [collect_long_patch_row()]
    long_only = variants_dir / "long_thread_patch_only_no_bootstrap.rpf"
    build_overlay_rpf(clean_original, long_only, long_rows)
    verification_rows.extend({"variant": "E_long_thread_patch_only_no_bootstrap", **row} for row in verify_rows(long_only, long_rows))
    add_variant("E_long_thread_patch_only_no_bootstrap", long_only, "long_update_thread_path_patch_only", "high", "Redirects trafficDebugThread slot but does not include target bootstrap WSC.")

    delayed = variants_dir / "bootstrap_launcher_delayed.rpf"
    shutil.copy2(bootstrap_only, delayed)
    add_variant("F_bootstrap_launcher_delayed", delayed, "bootstrap_wsc_file_only_no_launcher", "low", "No delayed launcher injected; safe placeholder until trainer/hotkey launch native is proven.")

    live_restore = restore_live_from_pass5(baseline)
    summary = {
        "clean_original": file_meta(clean_original),
        "pass5_source": file_meta(PASS5_RPF),
        "live_backup": live_backup,
        "live_restore": live_restore,
        "variants": variant_rows,
        "verification_count": len(verification_rows),
    }
    write_reports(summary, variant_rows, verification_rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
