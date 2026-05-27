#!/usr/bin/env python3
"""Build the latest Code RED MP candidate content.rpf.

This is intentionally a cloned-RPF builder. It never installs over the live
game content.rpf. The candidate combines the current game archive, the full
XENON->PC WSC conversion tree, and the latest local MP unlock/UI files.
"""
from __future__ import annotations

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
GAME_ROOT = ROOT.parent / "game"
SOURCE_RPF = GAME_ROOT / "content.rpf"
CONVERTED_TREE = ROOT / "build" / "mp_xenon_full_conversion_pass2" / "all_converted_import_ready_preserve_hash_names"
MP_PASS = GAME_ROOT / "XENON MULTIPLAYER" / "mp pass"
RECOMMENDED_XML = MP_PASS / "02_freeroam_lobby_route_RECOMMENDED"
OUT_ROOT = ROOT / "build" / "mp_latest_candidate_pass1"
REPORT_ROOT = ROOT / "reports" / "mp_latest_candidate_pass1"
OUTPUT_RPF = OUT_ROOT / "content_mp_latest_unlock_all_sectors_candidate.rpf"
GAME_COPY = GAME_ROOT / "content_mp_latest_unlock_all_sectors_candidate.rpf"

OVERLAY_TOOL = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
RPF_UTILS_TOOL = ROOT / "tools" / "codered_rpf_utils.py"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def ensure_resource_node(overlay: Any, wb: Any, node: Any, payload: bytes) -> None:
    if payload[:4] != b"RSC\x85":
        raise RuntimeError(f"resource payload is not PC RSC85: {node.path}")
    node.resource_replace = True
    node.resource_flag1, node.resource_flag2 = struct.unpack_from("<2I", payload, 8)


def pack_toc_with_resource_flags(overlay: Any, wb: Any, nodes: list[Any], encrypted: bool) -> bytes:
    toc = bytearray()
    for node in nodes:
        if node.kind == "dir":
            toc.extend(struct.pack(">5I", node.name_off, 0, 0x80000000 | node.start, node.count, 0))
            continue
        if node.operation in {"add", "replace"}:
            b = node.stored_size & 0x0FFFFFFF
            if getattr(node, "resource_replace", False):
                c = ((node.new_offset // 8) & 0x7FFFFF00) | 2
                d = node.resource_flag1
                e = node.resource_flag2
            else:
                c = (node.new_offset // 8) & 0x7FFFFFFF
                compression_bit = 0x40000000 if node.force_compressed else 0
                d = compression_bit | (node.decoded_size & 0x3FFFFFFF)
                e = 0
        else:
            ent = node.original or {}
            b = int(ent.get("size_in_archive") or 0) & 0x0FFFFFFF
            if ent.get("is_resource"):
                c = ((node.new_offset // 8) & 0x7FFFFF00) | (wb._rpf_resource_type(int(ent["offset_raw"])) & 0xFF)
            else:
                c = (node.new_offset // 8) & 0x7FFFFFFF
            d = int(ent.get("flag1") or 0)
            e = int(ent.get("flag2") or 0)
        toc.extend(struct.pack(">5I", node.name_off, b, c, d, e))
    padded = overlay.align(len(toc), 16)
    toc.extend(b"\x00" * (padded - len(toc)))
    return wb._codered_rpf6_encrypt(bytes(toc)) if encrypted else bytes(toc)


def collect_rows(include_release_mirror: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    mp_root = CONVERTED_TREE / "content" / "release64" / "multiplayer"
    if not mp_root.exists():
        raise FileNotFoundError(mp_root)

    for file in sorted(mp_root.rglob("*")):
        if not file.is_file():
            continue
        rel = file.relative_to(CONVERTED_TREE).as_posix()
        payload = file.read_bytes()
        rows.append(make_row("converted_xenon_release64_mp_tree", file, f"root/{rel}", payload, True, "replace"))
        if include_release_mirror:
            rel_release = rel.replace("content/release64/multiplayer/", "content/release/multiplayer/", 1)
            rows.append(make_row("converted_xenon_release_mp_mirror", file, f"root/{rel_release}", payload, True, "replace"))

    core_unlocks = [
        (MP_PASS / "pressstart_D_full_force.wsc", "root/content/release64/pressstart.wsc", "unlock_pressstart_all_mp_sectors"),
        (MP_PASS / "main_mp_save_unblock.wsc", "root/content/release64/main.wsc", "unlock_main_mp_save_unblock"),
        (MP_PASS / "main_z_mp_save_unblock.wsc", "root/content/release64/main_z.wsc", "unlock_main_z_mp_save_unblock"),
    ]
    for source, archive_path, layer in core_unlocks:
        payload = source.read_bytes()
        rows.append(make_row(layer, source, archive_path, payload, True, "replace"))

    xml_mappings = [
        (RECOMMENDED_XML / "ui" / "pausemenu" / "pausemenuscene.sc.xml", "root/content/ui/pausemenu/pausemenuscene.sc.xml", "ui_freeroam_route_variant02"),
        (RECOMMENDED_XML / "ui" / "pausemenu" / "networking.sc.xml", "root/content/ui/pausemenu/networking.sc.xml", "ui_freeroam_route_variant02"),
        (RECOMMENDED_XML / "ui" / "pausemenu" / "net" / "lanmenu.sc.xml", "root/content/ui/pausemenu/net/lanmenu.sc.xml", "ui_freeroam_route_variant02"),
        (RECOMMENDED_XML / "ui" / "pausemenu" / "net" / "plaympconf.sc.xml", "root/content/ui/pausemenu/net/plaympconf.sc.xml", "ui_freeroam_route_variant02"),
        (RECOMMENDED_XML / "ui" / "pausemenu" / "lobby" / "main.sc.xml", "root/content/ui/pausemenu/lobby/main.sc.xml", "ui_freeroam_route_variant02"),
        (MP_PASS / "boot.sc.xml", "root/content/ui/boot.sc.xml", "ui_boot_mp_support"),
        (MP_PASS / "savegame.sc.xml", "root/content/ui/savegame.sc.xml", "ui_savegame_mp_support"),
    ]
    for source, archive_path, layer in xml_mappings:
        if not source.exists():
            raise FileNotFoundError(source)
        payload = source.read_bytes()
        rows.append(make_row(layer, source, archive_path, payload, False, "replace"))

    return rows


def make_row(layer: str, source: Path, archive_path: str, payload: bytes, is_resource: bool, operation: str) -> dict[str, Any]:
    return {
        "layer": layer,
        "source_path": str(source),
        "archive_path": archive_path.replace("\\", "/"),
        "payload": payload,
        "expected_size": len(payload),
        "expected_sha1": sha1_bytes(payload),
        "resource_entry": is_resource,
        "operation": operation,
    }


def build_overlay_rpf(source_rpf: Path, output_rpf: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    overlay = load_module(OVERLAY_TOOL, "codered_overlay_latest_candidate")
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source_rpf)
    if info is None:
        raise RuntimeError(f"source RPF did not parse: {source_rpf}")
    root = overlay.build_existing_tree(info)
    operations: list[dict[str, Any]] = []
    for row in rows:
        action, node = overlay.add_or_replace_file(
            wb,
            root,
            row["archive_path"],
            row["payload"],
            row["operation"],
            allow_resource_replace=bool(row["resource_entry"]),
        )
        if row["resource_entry"]:
            ensure_resource_node(overlay, wb, node, row["payload"])
        operations.append(
            {
                "archive_path": row["archive_path"],
                "source_path": row["source_path"],
                "layer": row["layer"],
                "action": action,
                "resource_entry": row["resource_entry"],
                "expected_size": row["expected_size"],
                "expected_sha1": row["expected_sha1"],
            }
        )

    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    payload_floor = min(int(entry["offset"]) for entry in info["entries"] if entry.get("type") == "file")
    if 16 + toc_size > payload_floor:
        raise RuntimeError(f"new TOC would overlap payload: toc_end={16 + toc_size} payload_floor={payload_floor}")

    out = bytearray(source_rpf.read_bytes())
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = overlay.align(len(out), overlay.payload_alignment(node))
        if node.new_offset > len(out):
            out.extend(b"\x00" * (node.new_offset - len(out)))
        out.extend(node.source_bytes or b"")
        padded = overlay.align(len(out), 8)
        if padded > len(out):
            out.extend(b"\x00" * (padded - len(out)))

    toc = pack_toc_with_resource_flags(overlay, wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", out, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    out[16 : 16 + len(toc)] = toc
    output_rpf.parent.mkdir(parents=True, exist_ok=True)
    output_rpf.write_bytes(out)
    parsed = wb.parse_rpf6(output_rpf)
    if parsed is None:
        raise RuntimeError(f"output RPF did not parse: {output_rpf}")
    return {
        "source_rpf": str(source_rpf),
        "output_rpf": str(output_rpf),
        "entry_count_before": info.get("entry_count"),
        "entry_count_after": parsed.get("entry_count"),
        "file_count_after": parsed.get("file_count"),
        "operations": operations,
    }


def verify_rows(output_rpf: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    utils = load_module(RPF_UTILS_TOOL, "codered_rpf_utils_latest_candidate")
    wb = utils.load_backend()
    info = utils.parse_archive(output_rpf)
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            entry = utils.find_entry(info, row["archive_path"])
            data = utils.extract_entry_payload(wb, output_rpf, entry)
            actual = sha1_bytes(data)
            out.append(
                {
                    "archive_path": row["archive_path"],
                    "layer": row["layer"],
                    "entry_index": entry.get("index"),
                    "is_resource": entry.get("is_resource"),
                    "resource_type": entry.get("resource_type"),
                    "expected_size": row["expected_size"],
                    "actual_size": len(data),
                    "expected_sha1": row["expected_sha1"],
                    "actual_sha1": actual,
                    "status": "exact_match" if actual == row["expected_sha1"] else "mismatch",
                }
            )
        except Exception as exc:
            out.append(
                {
                    "archive_path": row["archive_path"],
                    "layer": row["layer"],
                    "entry_index": "",
                    "is_resource": "",
                    "resource_type": "",
                    "expected_size": row["expected_size"],
                    "actual_size": "",
                    "expected_sha1": row["expected_sha1"],
                    "actual_sha1": "",
                    "status": "error",
                    "note": str(exc),
                }
            )
    return out


def inventory_summary(archive: Path) -> dict[str, Any]:
    utils = load_module(RPF_UTILS_TOOL, f"codered_rpf_utils_inv_{archive.stem}")
    info = utils.parse_archive(archive)
    paths = [str(e.get("path") or "").replace("\\", "/").lower() for e in info.get("entries", []) if e.get("type") == "file"]
    return {
        "archive": str(archive),
        "sha1": sha1_file(archive),
        "entry_count": info.get("entry_count"),
        "file_count": info.get("file_count"),
        "release64_mp_wsc_count": sum(1 for p in paths if p.startswith("root/content/release64/multiplayer/") and p.endswith(".wsc")),
        "release_mp_wsc_count": sum(1 for p in paths if p.startswith("root/content/release/multiplayer/") and p.endswith(".wsc")),
        "release64_hash_resource_count": sum(1 for p in paths if p.startswith("root/content/release64/multiplayer/") and Path(p).suffix == ""),
        "core_present": {
            "freemode": "root/content/release64/multiplayer/freemode/freemode.wsc" in paths,
            "pr_multiplayer": "root/content/release64/multiplayer/pr_multiplayer.wsc" in paths,
            "multiplayer_system_thread": "root/content/release64/multiplayer/multiplayer_system_thread.wsc" in paths,
            "multiplayer_update_thread": "root/content/release64/multiplayer/multiplayer_update_thread.wsc" in paths,
            "mp_actorpicker": "root/content/release64/multiplayer/support/mp_actorpicker.wsc" in paths,
        },
    }


def write_reports(summary: dict[str, Any], manifest: list[dict[str, Any]], validation: list[dict[str, Any]]) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_ROOT / "summary.json", summary)
    write_csv(REPORT_ROOT / "manifest.csv", manifest)
    write_csv(REPORT_ROOT / "readback_validation.csv", validation)
    failures = [row for row in validation if row.get("status") != "exact_match"]
    lines = [
        "# MP Latest Candidate Pass 1",
        "",
        "This pass builds a cloned content.rpf candidate only. It does not overwrite the live game content.rpf.",
        "",
        f"- source RPF: `{summary['source_rpf']}`",
        f"- source SHA1: `{summary['source_sha1']}`",
        f"- output RPF: `{summary['output_rpf']}`",
        f"- game-folder copy: `{summary['game_copy']}`",
        f"- output SHA1: `{summary['output_sha1']}`",
        f"- entry count before: `{summary['build']['entry_count_before']}`",
        f"- entry count after: `{summary['build']['entry_count_after']}`",
        f"- injected/replaced rows: `{len(manifest)}`",
        f"- readback failures: `{len(failures)}`",
        "",
        "## Included Layers",
        "",
        "- Full XENON converted PC WSC multiplayer tree under `release64/multiplayer`.",
        "- Mirrored converted multiplayer tree under `release/multiplayer` as a fallback path.",
        "- `pressstart_D_full_force.wsc` as `release64/pressstart.wsc` for MP sector/access unlocking.",
        "- `main_mp_save_unblock.wsc` and `main_z_mp_save_unblock.wsc` core save/menu unblock files.",
        "- Recommended variant 02 freeroam lobby route XML.",
        "- MP support `boot.sc.xml` and `savegame.sc.xml`.",
        "",
        "## Test Notes",
        "",
        "Use this as a swap-test candidate only after backing up the current live `content.rpf`.",
        "If it fails, restore from the `content zombie mp loading.zip` backup or the known-good live backup.",
    ]
    (REPORT_ROOT / "build_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    test_steps = [
        "# MP Latest Candidate Test Steps",
        "",
        "1. Back up `D:\\Games\\Red Dead Redemption\\game\\content.rpf`.",
        "2. Copy `D:\\Games\\Red Dead Redemption\\game\\content_mp_latest_unlock_all_sectors_candidate.rpf` to `content.rpf` for testing.",
        "3. Launch the original Red Dead Redemption PC install, not the Steam/RDR remaster folder.",
        "4. If the game closes in under 2 minutes, treat this candidate as failed and restore the backup.",
        "5. If it boots, test Zombie/Multiplayer/Free Roam route and note whether it reaches loading, online HUD/menu, or a new error.",
        "6. Restore the original `content.rpf` after testing.",
    ]
    (REPORT_ROOT / "test_steps.md").write_text("\n".join(test_steps) + "\n", encoding="utf-8")


def main() -> int:
    if not SOURCE_RPF.exists():
        raise FileNotFoundError(SOURCE_RPF)
    rows = collect_rows(include_release_mirror=True)
    build = build_overlay_rpf(SOURCE_RPF, OUTPUT_RPF, rows)
    validation = verify_rows(OUTPUT_RPF, rows)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUT_RPF, GAME_COPY)
    manifest = [{k: v for k, v in row.items() if k != "payload"} for row in rows]
    summary = {
        "source_rpf": str(SOURCE_RPF),
        "source_sha1": sha1_file(SOURCE_RPF),
        "output_rpf": str(OUTPUT_RPF),
        "output_sha1": sha1_file(OUTPUT_RPF),
        "game_copy": str(GAME_COPY),
        "game_copy_sha1": sha1_file(GAME_COPY),
        "converted_tree": str(CONVERTED_TREE),
        "mp_pass": str(MP_PASS),
        "recommended_xml": str(RECOMMENDED_XML),
        "build": build,
        "inventory": inventory_summary(OUTPUT_RPF),
        "validation": {
            "row_count": len(validation),
            "exact_match_count": sum(1 for row in validation if row.get("status") == "exact_match"),
            "failure_count": sum(1 for row in validation if row.get("status") != "exact_match"),
        },
    }
    write_reports(summary, manifest, validation)
    print(json.dumps(summary, indent=2))
    return 0 if summary["validation"]["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
