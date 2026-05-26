#!/usr/bin/env python3
"""Build controlled online HUD/profile-editor RPF probes.

This pass works from the local "content zombie mp loading.zip" donor content.rpf
and writes cloned RPF variants only. It does not install into the game folder.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import struct
import sys
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = ROOT.parent / "game"
SOURCE_ZIP = GAME_ROOT / "content zombie mp loading.zip"
BUILD_ROOT = ROOT / "build" / "online_hudscene_pass1"
REPORT_ROOT = ROOT / "reports" / "online_hudscene_pass1"
SOURCE_RPF = BUILD_ROOT / "source_zip" / "content_zombie_mp_loading.rpf"
BUILDER_PATH = ROOT / "tools" / "codered_content_convert_overlay_builder.py"


def load_overlay_builder():
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


def extract_source_rpf() -> None:
    SOURCE_RPF.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SOURCE_ZIP) as zf:
        with zf.open("content.rpf") as src, SOURCE_RPF.open("wb") as dst:
            shutil.copyfileobj(src, dst)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def validate_xml(path: Path) -> str:
    try:
        ET.parse(path)
        return "ok"
    except Exception as exc:
        return f"fail: {exc}"


def patched_networking_profile_direct(base_text: str) -> str:
    text = base_text
    include_marker = '    <include src="Net_Profile.sc.xml"></include>'
    include_patch = (
        '    <include src="Net_Profile.sc.xml"></include>\n'
        '    <!-- CodeRED online HUD/profile probe: direct profile editor include. -->\n'
        '    <include src="../net/profileeditor/main.sc.xml"></include>'
    )
    if include_marker in text and "../net/profileeditor/main.sc.xml" not in text:
        text = text.replace(include_marker, include_patch, 1)
    text = text.replace(
        '<action expr="goto(NetConf_AvatarPicker)"></action>',
        '<action expr="Enter(MP_ProfileEditor)"></action>',
        1,
    )
    text = text.replace(
        '<UIButton desc="mp_fe_avatarpicker_tab">',
        '<UIButton id="CodeRED_ProfileEditor" desc="mp_fe_avatarpicker_tab">',
        1,
    )
    return text


def patched_pause_online_hud_direct(base_text: str) -> str:
    text = base_text
    include_marker = '    <include src="Networking.sc.xml"></include>'
    include_patch = (
        '    <include src="Networking.sc.xml"></include>\n'
        '    <!-- CodeRED online HUD probe: direct HUD scene include. -->\n'
        '    <include src="../net/hudsceneonline.sc.xml"></include>'
    )
    if include_marker in text and "../net/hudsceneonline.sc.xml" not in text:
        text = text.replace(include_marker, include_patch, 1)
    marker = '<!-- CodeRED Pass5 visible LAN/System Link parent route. -->'
    direct_label = (
        '      <!-- CodeRED direct online HUD scene probe. -->\n'
        '      <UILabel id="PM_CodeRED_OnlineHUD" text="PM_Network">\n'
        '        <onfocused expr="Enter(PauseMenu_Main_Prompts)"></onfocused>\n'
        '        <onfocused expr="SetRegistryValueInt(\'skipfade\',0)"></onfocused>\n'
        '          <transition event="@UI.ACCEPT*RELEASED" consume="true">\n'
        '              <action expr="Exit(PauseMenu)"></action>\n'
        '              <action expr="Enter(HudSceneOnline)"></action>\n'
        '              <action expr="SendEvent(\'AUDIO_StartMenuItemSelected\')"></action>\n'
        '          </transition>\n'
        '      </UILabel>\n'
    )
    if "PM_CodeRED_OnlineHUD" not in text and marker in text:
        text = text.replace(marker, direct_label + marker, 1)
    return text


def build_variant(builder, name: str, replacements: list[tuple[str, Path]], notes: str) -> dict:
    out = BUILD_ROOT / "variants" / name / "content.rpf"
    if not replacements:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_RPF, out)
        info = builder.load_backend().parse_rpf6(out)
        return {
            "variant": name,
            "status": "pass" if info else "fail",
            "output": str(out),
            "sha1": sha1(out),
            "notes": notes,
            "entry_count": info.get("entry_count") if info else "",
            "operations": [],
        }

    wb = builder.load_backend()
    info = wb.parse_rpf6(SOURCE_RPF)
    if info is None:
        raise RuntimeError(f"Source RPF did not parse: {SOURCE_RPF}")
    root = builder.build_existing_tree(info)
    operations: list[dict] = []
    for archive_path, local_file in replacements:
        payload = local_file.read_bytes()
        action, node = builder.add_or_replace_file(wb, root, archive_path, payload, "replace")
        operations.append({
            "archive_path": archive_path,
            "local_file": str(local_file),
            "result": action,
            "decoded_size": node.decoded_size,
            "stored_size": node.stored_size,
            "compressed": node.force_compressed,
        })
    nodes = builder.flatten_tree(root)
    original = bytearray(SOURCE_RPF.read_bytes())
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = builder.align(len(original), builder.payload_alignment(node))
        if node.new_offset > len(original):
            original.extend(b"\x00" * (node.new_offset - len(original)))
        payload = node.source_bytes or b""
        original.extend(payload)
        padded = builder.align(len(original), 8)
        if padded > len(original):
            original.extend(b"\x00" * (padded - len(original)))
    toc = builder.pack_toc(wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", original, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    original[16:16 + len(toc)] = toc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(original)
    check = wb.parse_rpf6(out)
    return {
        "variant": name,
        "status": "pass" if check else "fail",
        "output": str(out),
        "sha1": sha1(out),
        "notes": notes,
        "entry_count": check.get("entry_count") if check else "",
        "operations": operations,
    }


def main() -> int:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    extract_source_rpf()
    builder = load_overlay_builder()

    source_ui = BUILD_ROOT / "extract_ui_zip" / "content" / "ui"
    networking_src = source_ui / "pausemenu" / "networking.sc.xml"
    pause_src = source_ui / "pausemenu" / "pausemenuscene.sc.xml"
    if not networking_src.exists() or not pause_src.exists():
        raise RuntimeError("Expected extracted UI files from the donor RPF before running this builder.")

    patch_root = BUILD_ROOT / "patched_xml"
    networking_profile = patch_root / "networking_profile_editor_direct.sc.xml"
    pause_hud = patch_root / "pausemenuscene_online_hud_direct.sc.xml"
    networking_combined = patch_root / "networking_combined.sc.xml"
    pause_combined = patch_root / "pausemenuscene_combined.sc.xml"

    write_text(networking_profile, patched_networking_profile_direct(networking_src.read_text(encoding="utf-8")))
    write_text(pause_hud, patched_pause_online_hud_direct(pause_src.read_text(encoding="utf-8")))
    write_text(networking_combined, networking_profile.read_text(encoding="utf-8"))
    write_text(pause_combined, pause_hud.read_text(encoding="utf-8"))

    xml_rows = []
    for path in [networking_profile, pause_hud, networking_combined, pause_combined]:
        xml_rows.append({"file": str(path), "xml_parse": validate_xml(path), "sha1": sha1(path), "size": path.stat().st_size})

    variants = [
        build_variant(builder, "V0_zip_as_is_control", [], "Direct copy of content zombie mp loading zip content.rpf."),
        build_variant(
            builder,
            "V1_profile_editor_direct",
            [("root/content/ui/pausemenu/networking.sc.xml", networking_profile)],
            "Avatar picker tab directly enters MP_ProfileEditor and includes ../net/profileeditor/main.sc.xml.",
        ),
        build_variant(
            builder,
            "V2_online_hudscene_direct",
            [("root/content/ui/pausemenu/pausemenuscene.sc.xml", pause_hud)],
            "Adds a pause-menu CodeRED online HUD label and includes ../net/hudsceneonline.sc.xml.",
        ),
        build_variant(
            builder,
            "V3_profile_plus_hudscene",
            [
                ("root/content/ui/pausemenu/networking.sc.xml", networking_combined),
                ("root/content/ui/pausemenu/pausemenuscene.sc.xml", pause_combined),
            ],
            "Combines direct MP_ProfileEditor route with direct HudSceneOnline route.",
        ),
    ]

    with (REPORT_ROOT / "xml_validation.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "xml_parse", "sha1", "size"])
        writer.writeheader()
        writer.writerows(xml_rows)
    with (REPORT_ROOT / "variant_manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["variant", "status", "output", "sha1", "notes", "entry_count"])
        writer.writeheader()
        for row in variants:
            writer.writerow({k: row.get(k, "") for k in ["variant", "status", "output", "sha1", "notes", "entry_count"]})
    with (REPORT_ROOT / "operations.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["variant", "archive_path", "local_file", "result", "decoded_size", "stored_size", "compressed"])
        writer.writeheader()
        for variant in variants:
            for op in variant.get("operations", []):
                writer.writerow({"variant": variant["variant"], **op})

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_zip": str(SOURCE_ZIP),
        "source_rpf": str(SOURCE_RPF),
        "source_sha1": sha1(SOURCE_RPF),
        "variants": variants,
        "xml_validation": xml_rows,
        "steamgg_used": False,
        "live_content_rpf_edited": False,
    }
    (REPORT_ROOT / "pass_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Online HudScene / Avatar Picker Probe Pass 1",
        "",
        f"- source zip: `{SOURCE_ZIP}`",
        f"- source RPF SHA1: `{report['source_sha1']}`",
        "- SteamGG path used: `false`",
        "- live content.rpf edited by builder: `false`",
        "",
        "## Variants",
    ]
    for row in variants:
        lines.append(f"- `{row['variant']}`: `{row['status']}` `{row['sha1']}` - {row['notes']}")
    lines += [
        "",
        "## Test Order",
        "",
        "1. Test `V0_zip_as_is_control` first. If it closes under 2 minutes, stop.",
        "2. Test `V1_profile_editor_direct` for avatar/profile editor reachability.",
        "3. Test `V2_online_hudscene_direct` for online HUD scene reachability.",
        "4. Test `V3_profile_plus_hudscene` only if V1 and V2 both survive.",
        "",
        "Restore the previous `game/content.rpf` between tests.",
    ]
    (REPORT_ROOT / "pass_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"variants": variants, "report": str(REPORT_ROOT / "pass_report.md")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
