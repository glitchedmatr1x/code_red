#!/usr/bin/env python3
"""Build smaller online/avatar route probes from the clean stock content.rpf."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import struct
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = ROOT.parent / "game"
CLEAN_RPF = GAME_ROOT / "clean" / "content.rpf"
BUILD_ROOT = ROOT / "build" / "online_hudscene_pass1"
REPORT_ROOT = ROOT / "reports" / "online_hudscene_pass1"
BUILDER_PATH = ROOT / "tools" / "codered_content_convert_overlay_builder.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("codered_overlay_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BUILDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def xml_ok(path: Path) -> str:
    try:
        ET.parse(path)
        return "ok"
    except Exception as exc:
        return f"fail: {exc}"


def visible_pause_network(base: str) -> str:
    text = base
    text = text.replace(
        "      <!-- <UILabel id=\"PM_Network\" text=\"PM_Network\">",
        "      <!-- CodeRED clean route: visible network/avatar parent. -->\n      <UILabel id=\"PM_CodeRED_Network\" text=\"PM_Network\">",
        1,
    )
    text = text.replace(
        "      </UILabel>\n      <UILabel id=\"PM_SocialClub\"",
        "      </UILabel>\n      <!--\n      <UILabel id=\"PM_SocialClub\"",
        1,
    )
    return text


def add_offline_avatar_send_event(base: str) -> str:
    marker = '      <UILabel desc="mp_fe_play_lan_tab"     target="NetConf_PlayLAN" consume="false">'
    button = (
        '      <!-- CodeRED clean route: avatar picker event from offline networking menu. -->\n'
        '      <UIButton id="NetOffTab_CodeREDAvatar" desc="mp_fe_avatarpicker_tab" consume="false">\n'
        '        <transition event="@UI.ACCEPT*RELEASED">\n'
        '          <action expr="PlaySound(\'HUD_MENU_SELECT_MASTER\')"></action>\n'
        '          <action expr="SendEvent(\'LaunchAvatarPicker\')"></action>\n'
        '        </transition>\n'
        '      </UIButton>\n\n'
    )
    if "NetOffTab_CodeREDAvatar" in base:
        return base
    return base.replace(marker, button + marker, 1)


def add_offline_avatar_goto(base: str) -> str:
    marker = '      <UILabel desc="mp_fe_play_lan_tab"     target="NetConf_PlayLAN" consume="false">'
    button = (
        '      <!-- CodeRED clean route: avatar picker goto from offline networking menu. -->\n'
        '      <UIButton id="NetOffTab_CodeREDAvatarGoto" desc="mp_fe_avatarpicker_tab" consume="false">\n'
        '        <transition event="@UI.ACCEPT*RELEASED">\n'
        '          <action expr="PlaySound(\'HUD_MENU_SELECT_MASTER\')"></action>\n'
        '          <action expr="goto(NetConf_AvatarPicker)"></action>\n'
        '        </transition>\n'
        '      </UIButton>\n\n'
    )
    if "NetOffTab_CodeREDAvatarGoto" in base:
        return base
    return base.replace(marker, button + marker, 1)


def build_variant(builder, name: str, replacements: list[tuple[str, Path]], notes: str) -> dict:
    out = BUILD_ROOT / "clean_base_variants" / name / "content.rpf"
    if not replacements:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CLEAN_RPF, out)
        info = builder.load_backend().parse_rpf6(out)
        return {"variant": name, "status": "pass" if info else "fail", "output": str(out), "sha1": sha1(out), "notes": notes, "entry_count": info.get("entry_count") if info else "", "operations": []}

    wb = builder.load_backend()
    info = wb.parse_rpf6(CLEAN_RPF)
    if info is None:
        raise RuntimeError(f"Clean RPF did not parse: {CLEAN_RPF}")
    root = builder.build_existing_tree(info)
    operations = []
    for archive_path, local_file in replacements:
        action, node = builder.add_or_replace_file(wb, root, archive_path, local_file.read_bytes(), "replace")
        operations.append({"archive_path": archive_path, "local_file": str(local_file), "result": action, "decoded_size": node.decoded_size, "stored_size": node.stored_size, "compressed": node.force_compressed})
    nodes = builder.flatten_tree(root)
    original = bytearray(CLEAN_RPF.read_bytes())
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = builder.align(len(original), builder.payload_alignment(node))
        if node.new_offset > len(original):
            original.extend(b"\x00" * (node.new_offset - len(original)))
        original.extend(node.source_bytes or b"")
        padded = builder.align(len(original), 8)
        if padded > len(original):
            original.extend(b"\x00" * (padded - len(original)))
    toc = builder.pack_toc(wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", original, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    original[16:16 + len(toc)] = toc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(original)
    check = wb.parse_rpf6(out)
    return {"variant": name, "status": "pass" if check else "fail", "output": str(out), "sha1": sha1(out), "notes": notes, "entry_count": check.get("entry_count") if check else "", "operations": operations}


def main() -> int:
    builder = load_builder()
    clean_ui = BUILD_ROOT / "extract_ui_clean" / "content" / "ui"
    pause = clean_ui / "pausemenu" / "pausemenuscene.sc.xml"
    networking = clean_ui / "pausemenu" / "networking.sc.xml"
    if not pause.exists() or not networking.exists():
        raise RuntimeError("Extract clean UI files first.")
    patch_root = BUILD_ROOT / "clean_patched_xml"
    pause_visible = patch_root / "pausemenuscene_visible_network.sc.xml"
    net_event = patch_root / "networking_offline_avatar_send_event.sc.xml"
    net_goto = patch_root / "networking_offline_avatar_goto.sc.xml"
    write_text(pause_visible, visible_pause_network(pause.read_text(encoding="utf-8")))
    write_text(net_event, add_offline_avatar_send_event(networking.read_text(encoding="utf-8")))
    write_text(net_goto, add_offline_avatar_goto(networking.read_text(encoding="utf-8")))

    xml_rows = [{"file": str(p), "xml_parse": xml_ok(p), "sha1": sha1(p), "size": p.stat().st_size} for p in [pause_visible, net_event, net_goto]]
    variants = [
        build_variant(builder, "C0_clean_copy_control", [], "Direct copy of clean stock content.rpf."),
        build_variant(builder, "C1_visible_network_only", [("root/content/ui/pausemenu/pausemenuscene.sc.xml", pause_visible)], "Only exposes the existing NetworkingLayerOffline parent route from the pause menu."),
        build_variant(builder, "C2_avatar_send_event", [("root/content/ui/pausemenu/pausemenuscene.sc.xml", pause_visible), ("root/content/ui/pausemenu/networking.sc.xml", net_event)], "Adds an offline networking avatar button that sends LaunchAvatarPicker; no new includes."),
        build_variant(builder, "C3_avatar_goto", [("root/content/ui/pausemenu/pausemenuscene.sc.xml", pause_visible), ("root/content/ui/pausemenu/networking.sc.xml", net_goto)], "Adds an offline networking avatar button that goto(NetConf_AvatarPicker); no new includes."),
    ]

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    with (REPORT_ROOT / "clean_xml_validation.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "xml_parse", "sha1", "size"])
        writer.writeheader()
        writer.writerows(xml_rows)
    with (REPORT_ROOT / "clean_variant_manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["variant", "status", "output", "sha1", "notes", "entry_count"])
        writer.writeheader()
        for row in variants:
            writer.writerow({k: row.get(k, "") for k in ["variant", "status", "output", "sha1", "notes", "entry_count"]})
    with (REPORT_ROOT / "clean_operations.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["variant", "archive_path", "local_file", "result", "decoded_size", "stored_size", "compressed"])
        writer.writeheader()
        for variant in variants:
            for op in variant.get("operations", []):
                writer.writerow({"variant": variant["variant"], **op})
    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "clean_rpf": str(CLEAN_RPF), "clean_sha1": sha1(CLEAN_RPF), "variants": variants, "xml_validation": xml_rows, "live_content_rpf_edited": False}
    (REPORT_ROOT / "clean_route_pass_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Clean Base Online/Avatar Route Probe", "", f"- clean source: `{CLEAN_RPF}`", f"- clean SHA1: `{report['clean_sha1']}`", "- live content.rpf edited by builder: `false`", "", "## Variants"]
    for row in variants:
        lines.append(f"- `{row['variant']}`: `{row['status']}` `{row['sha1']}` - {row['notes']}")
    (REPORT_ROOT / "clean_route_pass_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"variants": variants, "report": str(REPORT_ROOT / "clean_route_pass_report.md")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
