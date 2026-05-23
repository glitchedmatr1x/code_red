#!/usr/bin/env python3
"""Build Code RED Pass 5 MP access RPF variants from the Pass 4 clone.

Pass 5 keeps the full donor multiplayer tree already added by Pass 4. It only
replaces decoded SCXML on cloned RPF outputs, records the local LAN route
evidence, scans update-thread WSCs for sector anchors, and stages the optional
dev trainer package if its ASI build is present.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import difflib
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PASS4_PRIMARY_RPF = ROOT / "build" / "mp_content_restore_pass4" / "content_mp_restore_pass4_full_mp.rpf"
PASS4_LOCAL_ALIAS_RPF = ROOT / "build" / "mp_content_restore_pass4" / "content.rpf"
PASS4_RPF = PASS4_PRIMARY_RPF if PASS4_PRIMARY_RPF.exists() else PASS4_LOCAL_ALIAS_RPF
PASS4_AUTH = ROOT / "build" / "mp_content_restore_pass4" / "optional_local_auth_experiment"
BUILD_ROOT = ROOT / "build" / "mp_content_restore_pass5"
OVERLAY_TOOL = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
RPF_UTILS_TOOL = ROOT / "tools" / "codered_rpf_utils.py"
TRAINER_APP = ROOT / "related_apps" / "Code_RED_MP_DevTrainer"
RDR_EXE = ROOT.parent / "RDR.exe"
PAUSE_ARCHIVE = "root/content/ui/pausemenu/pausemenuscene.sc.xml"
NETWORK_ARCHIVE = "root/content/ui/pausemenu/networking.sc.xml"
LAN_ARCHIVE = "root/content/ui/pausemenu/net/lanmenu.sc.xml"
PLAYMP_ARCHIVE = "root/content/ui/pausemenu/net/plaympconf.sc.xml"
LOBBY_ARCHIVE = "root/content/ui/pausemenu/lobby/main.sc.xml"
GENERAL_ARCHIVE = "root/content/ui/generalmenus.sc.xml"
SECTOR_TERMS = (
    "ENABLE_WORLD_SECTOR,DISABLE_WORLD_SECTOR,ENABLE_CHILD_SECTOR,"
    "DISABLE_CHILD_SECTOR,catacombs,dlc_beh_catacombs01x,"
    "dlc_beh_catacombs01props01x,blackwater,multiplayer,freeroam,dlc"
)
XML_REPORT_FIELDS = [
    "variant",
    "archive_path",
    "change_kind",
    "source_sha1",
    "candidate_sha1",
    "source_size",
    "candidate_size",
    "verification",
    "marker",
    "note",
]
VERIFY_FIELDS = [
    "variant",
    "archive_path",
    "entry_index",
    "status",
    "decoded_size",
    "decoded_sha1",
    "required_markers",
    "note",
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"


def file_meta(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha1": sha1_bytes(data), "crc32": crc32_bytes(data)}


def reset_dir(path: Path, build_root: Path) -> None:
    if path.exists():
        if build_root.resolve() not in path.resolve().parents:
            raise RuntimeError(f"Refusing to clear path outside Pass 5 build root: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def backup_source(source: Path, build_root: Path) -> tuple[Path, dict[str, Any]]:
    meta = file_meta(source)
    backup = build_root / "original_backups" / f"{source.stem}_{meta['sha1'][:12]}{source.suffix}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(source, backup)
    return backup, meta


def extract_entry_text(utils, archive: Path, archive_path: str) -> tuple[str, dict[str, Any]]:
    wb = utils.load_backend()
    info = utils.parse_archive(archive)
    entry = utils.find_entry(info, archive_path)
    data = utils.extract_entry_payload(wb, archive, entry)
    return data.decode("utf-8"), entry


def write_diff(original: str, candidate: str, path: Path, left: str, right: str) -> None:
    diff = "\n".join(
        difflib.unified_diff(original.splitlines(), candidate.splitlines(), fromfile=left, tofile=right, lineterm="")
    )
    write_text(path, diff + ("\n" if diff else ""))


def patch_pause_parent(text: str) -> str:
    text = text.replace("\r\n", "\n")
    old = """      <!-- <UILabel id="PM_Network" text="PM_Network">
        <onfocused expr="Enter(PauseMenu_Main_Prompts)"></onfocused>
        <onfocused expr="SetRegistryValueInt('skipfade',0)"></onfocused>
          <transition event="@UI.ACCEPT*RELEASED" consume="true">
              <action expr="Exit(PauseMenu_Main_Prompts)"></action>
              <action expr="unfocus(PauseMenu)"></action>
              <action expr="Enter(NetworkingLayerOffline)"></action>
              <action expr="SendEvent('AUDIO_StartMenuItemSelected')"></action>
          </transition>
      </UILabel>"""
    new = """      <!-- CodeRED Pass5 visible LAN/System Link parent route. -->
      <UILabel id="PM_CodeRED_LAN" text="PM_Network">
        <onfocused expr="Enter(PauseMenu_Main_Prompts)"></onfocused>
        <onfocused expr="SetRegistryValueInt('skipfade',0)"></onfocused>
          <transition event="@UI.ACCEPT*RELEASED" consume="true">
              <action expr="Exit(PauseMenu_Main_Prompts)"></action>
              <action expr="unfocus(PauseMenu)"></action>
              <action expr="Enter(NetworkingLayerOffline)"></action>
              <action expr="SendEvent('AUDIO_StartMenuItemSelected')"></action>
          </transition>
      </UILabel>
      <!--"""
    if "PM_CodeRED_LAN" in text:
        return text
    if old not in text:
        raise RuntimeError("Pause menu commented PM_Network parent block was not found")
    return text.replace(old, new, 1)


def patch_networking_parent(text: str) -> str:
    text = text.replace("\r\n", "\n")
    marker = """      <UILabel desc="mp_fe_play_lan_tab"     target="NetConf_PlayLAN" consume="false">
        <onfocused expr="Select(NetContent_LAN)"></onfocused>
      </UILabel>"""
    insertion = """      <!-- CodeRED Pass5 explicit offline LAN parent route. -->
      <UILabel id="NetOffTab_CodeREDLAN" desc="mp_fe_play_lan_tab" target="NetConf_PlayLAN" consume="false">
        <onfocused expr="Select(NetContent_LAN)"></onfocused>
      </UILabel>

"""
    if "NetOffTab_CodeREDLAN" in text:
        return text
    if marker not in text:
        raise RuntimeError("Networking offline LAN label marker was not found")
    return text.replace(marker, insertion + marker, 1)


def copy_optional_auth(build_root: Path) -> None:
    target = build_root / "optional_local_auth_experiment"
    if PASS4_AUTH.exists():
        shutil.copytree(PASS4_AUTH, target, dirs_exist_ok=True)
    write_text(
        target / "README.md",
        "# Pass 5 Optional Local Auth Experiment\n\n"
        "This folder is copied from the Pass 4 PlayMpConf candidate lane. It is not included in any default Pass 5 RPF. "
        "Use it only for local/offline experiments after the visible XML route is observed.\n",
    )


def prepare_xml_candidates(utils, source: Path, build_root: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]], str]:
    candidate_root = build_root / "xml_candidates"
    candidate_root.mkdir(parents=True, exist_ok=True)
    sources: dict[str, str] = {}
    inspected: list[str] = []
    notes: list[str] = []
    for archive_path in (PAUSE_ARCHIVE, NETWORK_ARCHIVE, LAN_ARCHIVE, PLAYMP_ARCHIVE, LOBBY_ARCHIVE, GENERAL_ARCHIVE):
        try:
            text, entry = extract_entry_text(utils, source, archive_path)
            sources[archive_path] = text
            inspected.append(f"- `{archive_path}` entry `{entry.get('index')}` decoded bytes `{len(text.encode('utf-8'))}`")
        except Exception as exc:
            notes.append(f"- `{archive_path}` was not decoded from the Pass 4 base: `{exc}`")

    pause = patch_pause_parent(sources[PAUSE_ARCHIVE])
    networking = patch_networking_parent(sources[NETWORK_ARCHIVE])
    payloads = {
        "pause_parent": {PAUSE_ARCHIVE: pause},
        "networking_parent": {NETWORK_ARCHIVE: networking},
        "combined": {PAUSE_ARCHIVE: pause, NETWORK_ARCHIVE: networking},
        # No decoded active main menu scene is known. Keep an isolated RPF
        # that proves the active pause parent route instead of editing a guess.
        "mainmenu_review_fallback": {PAUSE_ARCHIVE: pause},
    }
    changes: list[dict[str, Any]] = []
    for variant, variant_payloads in payloads.items():
        for archive_path, candidate in variant_payloads.items():
            original = sources[archive_path]
            basename = archive_path.replace("root/", "").replace("/", "__")
            stage = candidate_root / variant / f"{basename}.decoded.xml"
            write_text(stage, candidate)
            write_text(candidate_root / variant / f"{basename}.original.decoded.xml", original)
            write_diff(
                original,
                candidate,
                candidate_root / variant / f"{basename}.diff",
                f"pass4:{archive_path}",
                f"pass5:{variant}:{archive_path}",
            )
            marker = "PM_CodeRED_LAN" if archive_path == PAUSE_ARCHIVE else "NetOffTab_CodeREDLAN"
            changes.append(
                {
                    "variant": variant,
                    "archive_path": archive_path,
                    "change_kind": "activate_pause_parent" if archive_path == PAUSE_ARCHIVE else "add_networking_parent",
                    "source_sha1": sha1_bytes(original.encode("utf-8")),
                    "candidate_sha1": sha1_bytes(candidate.encode("utf-8")),
                    "source_size": len(original.encode("utf-8")),
                    "candidate_size": len(candidate.encode("utf-8")),
                    "verification": "candidate_contains_marker" if marker in candidate else "marker_missing",
                    "marker": marker,
                    "note": "decoded XML staged before Zstandard RPF replacement",
                }
            )
    report = "\n".join(
        [
            "# Code RED Pass 5 XML Route Report",
            "",
            "## Pass 4 RPF XML inspection",
            "",
            *inspected,
            *notes,
            "",
            "## Route decision",
            "",
            "- Pass 4 patched `lanmenu.sc.xml`, but the decoded pause parent still had the `PM_Network` label commented out.",
            "- Pass 5 activates that pause parent label as `PM_CodeRED_LAN` and routes it to the existing `NetworkingLayerOffline` chain.",
            "- `networking.sc.xml` already had offline LAN tabs and `NetConf_PlayLAN`; a separate variant adds `NetOffTab_CodeREDLAN` for visible isolation.",
            "- The recommended combined RPF includes the pause parent and networking parent edits. It does not edit `PlayMpConf` auth logic.",
            "- No decoded active main-menu scene was identified in the Pass 4 SCXML set, so the `pass5_mainmenu_route.rpf` output is a labeled review fallback that uses the known pause parent edit rather than patching an unknown menu.",
            "",
            "## Known chain kept intact",
            "",
            "`NetworkingLayerOffline -> NetConf_PlayLAN -> net/PlayMpConf.sc -> NetMachine.Authenticate(arg1) -> auth.success -> NetMachine.TriggerMultiplayerLoad(arg2)`",
            "",
        ]
    )
    return payloads, changes, report + "\n"


def write_archive_variant(overlay, source: Path, output: Path, xml_payloads: dict[str, str]) -> dict[str, Any]:
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source)
    if info is None:
        raise RuntimeError(f"Pass 4 source does not parse: {source}")
    root = overlay.build_existing_tree(info)
    ops: list[dict[str, Any]] = []
    for archive_path, text in xml_payloads.items():
        raw = text.encode("utf-8")
        action, node = overlay.add_or_replace_file(wb, root, archive_path, raw, "replace")
        ops.append(
            {
                "archive_path": archive_path,
                "action": action,
                "decoded_sha1": sha1_bytes(raw),
                "decoded_size": len(raw),
                "stored_size": node.stored_size,
                "compressed": node.force_compressed,
            }
        )
    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    payload_floor = min(int(entry["offset"]) for entry in info["entries"] if entry.get("type") == "file")
    if 16 + toc_size > payload_floor:
        raise RuntimeError(f"Pass 5 TOC would overlap first payload: toc_end={16 + toc_size} payload_floor={payload_floor}")
    output_bytes = bytearray(source.read_bytes())
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
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(output_bytes)
    parsed = wb.parse_rpf6(output)
    if parsed is None:
        raise RuntimeError(f"Pass 5 output does not parse: {output}")
    return {"source_info": info, "output_info": parsed, "ops": ops, "output": str(output), "toc_size": toc_size}


def verify_variant(utils, archive: Path, variant: str, xml_payloads: dict[str, str]) -> list[dict[str, Any]]:
    info = utils.parse_archive(archive)
    rows: list[dict[str, Any]] = []
    for archive_path, expected in xml_payloads.items():
        text, entry = extract_entry_text(utils, archive, archive_path)
        if archive_path == PAUSE_ARCHIVE:
            markers = ["PM_CodeRED_LAN", "NetworkingLayerOffline", "CodeRED Pass5"]
        else:
            markers = ["NetOffTab_CodeREDLAN", "NetConf_PlayLAN", "CodeRED Pass5"]
        rows.append(
            {
                "variant": variant,
                "archive_path": archive_path,
                "entry_index": entry.get("index"),
                "status": "exact_match" if text == expected and all(marker in text for marker in markers) else "mismatch",
                "decoded_size": len(text.encode("utf-8")),
                "decoded_sha1": sha1_bytes(text.encode("utf-8")),
                "required_markers": ";".join(markers),
                "note": f"RPF entry_count={info.get('entry_count')}",
            }
        )
    return rows


def entry_paths(info: dict[str, Any]) -> list[str]:
    return [str(entry.get("path") or "").replace("\\", "/").lower() for entry in info.get("entries", []) if entry.get("type") == "file"]


def mp_counts(info: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in entry_paths(info):
        if "/multiplayer/" not in path:
            continue
        branch = "release64" if "/content/release64/" in path else "release" if "/content/release/" in path else "other"
        suffix = Path(path).suffix.lower() or "(no_ext)"
        counts[f"{branch}:{suffix}"] += 1
    return dict(counts)


def scan_sector_threads(build_root: Path) -> list[dict[str, Any]]:
    scan_root = build_root / "optional_sector_variants" / "scans"
    scan_root.mkdir(parents=True, exist_ok=True)
    base = ROOT / "game" / "content_extracted" / "release64"
    candidates = [
        base / "scripting" / "designerdefined" / "medium_update_thread.wsc",
        base / "scripting" / "designerdefined" / "long_update_thread.wsc",
        base / "scripting" / "designerdefined" / "short_update_thread.wsc",
        base / "dlc" / "zombiepack" / "system" / "medium_update_thread_z.wsc",
        base / "dlc" / "zombiepack" / "system" / "long_update_thread_z.wsc",
        base / "dlc" / "zombiepack" / "system" / "short_update_thread_z.wsc",
    ]
    rows: list[dict[str, Any]] = []
    for script in candidates:
        out = scan_root / script.stem
        if not script.exists():
            rows.append({"script": str(script), "status": "missing", "out": str(out), "term_hits": 0, "note": ""})
            continue
        cmd = [
            sys.executable,
            "-m",
            "codered_wsc",
            "scan",
            str(script),
            "--terms",
            SECTOR_TERMS,
            "--out",
            str(out),
        ]
        if RDR_EXE.exists():
            cmd.extend(["--rdr-exe", str(RDR_EXE)])
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        term_hits = 0
        hits = out / "term_hits.csv"
        if hits.exists():
            with hits.open(newline="", encoding="utf-8") as handle:
                term_hits = sum(1 for _ in csv.DictReader(handle))
        rows.append(
            {
                "script": str(script),
                "status": "scanned" if proc.returncode == 0 else "scan_failed",
                "out": str(out),
                "term_hits": term_hits,
                "note": (proc.stderr or proc.stdout).strip()[-500:],
            }
        )
    write_csv(
        build_root / "reports" / "mp_pass5_sector_scan_rows.csv",
        rows,
        ["script", "status", "out", "term_hits", "note"],
    )
    write_text(
        build_root / "optional_sector_variants" / "README.md",
        "# Pass 5 Optional Sector Variants\n\n"
        "The WSC scan outputs in `scans/` are evidence for later same-size sector work. "
        "No sector WSC is injected into the default Pass 5 RPF until Code RED WSC tools map a validated same-family patch target.\n",
    )
    return rows


def sector_scan_md(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Code RED Pass 5 Sector Scan Report",
        "",
        f"- Terms: `{SECTOR_TERMS}`",
        f"- RDR key source: `{RDR_EXE}` exists `{RDR_EXE.exists()}`",
        "",
        "| Script | Status | Term hits | Scan output |",
        "| --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(f"| `{Path(str(row['script'])).name}` | `{row['status']}` | `{row['term_hits']}` | `{row['out']}` |")
    lines.extend(
        [
            "",
            "The scan includes normal and zombie update threads. It is evidence-only for this pass; sector natives and same-size ownership must be proven before WSC replacement.",
            "",
        ]
    )
    return "\n".join(lines)


def sector_patch_md() -> str:
    return "\n".join(
        [
            "# Code RED Pass 5 Sector Patch Report",
            "",
            "## Default RPF decision",
            "",
            "- No update-thread WSC sector patch is included in the recommended Pass 5 RPF.",
            "- The current WSC lane can scan sector strings and control-flow evidence, but the requested safe route still requires an owned same-size enable/disable target for `ENABLE_WORLD_SECTOR` or its child-sector family.",
            "- Broad branch rewrites are explicitly out of scope here.",
            "- `optional_sector_variants/scans/` holds the targeted scan evidence for the next Morning Star-style recipe pass.",
            "",
            "## Optional targets retained for review",
            "",
            "- `dlc_beh_catacombs01x`",
            "- `dlc_beh_catacombs01props01x`",
            "- medium update thread first, long update thread second, short update thread only if it owns the target.",
            "",
        ]
    )


def wsc_validation_md() -> str:
    return "\n".join(
        [
            "# Code RED Pass 5 WSC Validation",
            "",
            "- Validation status: `no_wsc_write_in_default_rpf`",
            "- Pass 5 output RPFs are built from the Pass 4 full-MP clone and replace SCXML only.",
            "- Update-thread WSC entries remain inherited from the Pass 4 base because no conservative same-size sector patch passed ownership review in this pass.",
            "- A future WSC write should produce a Code RED patch manifest, resource reopen validation, decoded diff, and output-entry re-extract check before inclusion.",
            "",
        ]
    )


def stage_trainer(build_root: Path) -> dict[str, Any]:
    package = build_root / "CodeRED_MP_DevTrainer"
    package.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for source, rel in (
        (TRAINER_APP / "README.md", Path("README.md")),
        (TRAINER_APP / "data" / "codered" / "mp_dev_trainer.ini", Path("data/codered/mp_dev_trainer.ini")),
        (TRAINER_APP / "build" / "CodeRED_MP_DevTrainer.asi", Path("CodeRED_MP_DevTrainer.asi")),
    ):
        if source.exists():
            target = package / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(str(target))
    return {
        "package": str(package),
        "asi_present": (package / "CodeRED_MP_DevTrainer.asi").exists(),
        "copied": copied,
    }


def trainer_report_md(stage: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Code RED Pass 5 Dev Trainer Report",
            "",
            f"- Package: `{stage['package']}`",
            f"- ASI staged: `{stage['asi_present']}`",
            "- Trainer purpose: local/offline ScriptHook diagnostics only.",
            "- The hotkey framework logs F5-F12 and NUM1-NUM3 attempts. Route/load/start/sector/teleport operations stay skipped when no safe runtime native bridge is mapped.",
            "- Optional auth experiments are not part of the default trainer.",
            "",
            "Packaged files:",
            "",
            *[f"- `{path}`" for path in stage["copied"]],
            "",
        ]
    )


def test_steps_md(output: Path, trainer: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Code RED Pass 5 Test Steps",
            "",
            f"Recommended RPF: `{output}`",
            f"Dev trainer package: `{trainer['package']}`",
            "",
            "1. Back up the current active `game\\content.rpf`.",
            "2. Temporarily replace it with `content_mp_restore_pass5_access_trainer_sectors.rpf`.",
            "3. Launch the game and confirm boot.",
            "4. Open the pause menu and check for the activated LAN/System Link network entry.",
            "5. Select it and record whether it reaches PlayMpConf, Authenticate, loading, crash, hang, or return-to-menu.",
            "6. Install `CodeRED_MP_DevTrainer.asi` beside `RDR.exe` if the package contains the ASI.",
            "7. Press `F6` to dump MP trainer state.",
            "8. Press `F11` and `F12` only as sector toggle probes; the current trainer logs skipped actions until safe natives are mapped.",
            "9. Use NUM teleport probes only after boot is stable.",
            "10. Restore the original `content.rpf` after testing if needed.",
            "",
            "No Pass 5 tool installs into the game folder automatically.",
            "",
        ]
    )


def build_report_md(source_meta: dict[str, Any], backup: Path, outputs: dict[str, dict[str, Any]], verify_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Code RED Multiplayer Restore Pass 5 Build Report",
        "",
        "## Safety",
        "",
        f"- Pass 4 base: `{source_meta['path']}`",
        f"- Pass 4 base SHA1 before/after: `{source_meta['sha1']}`",
        f"- Pass 4 base backup: `{backup}`",
        "- Live `game\\content.rpf` is not used as the write target.",
        "- Default outputs do not include an auth bypass or public-server spoofing.",
        "",
        "## Outputs",
        "",
    ]
    for name, built in outputs.items():
        lines.append(f"- `{name}`: `{built['output']}` entries `{built['output_info'].get('entry_count')}` MP counts `{mp_counts(built['output_info'])}`")
    lines.extend(
        [
            "",
            "## Verification",
            "",
            f"- XML verify statuses: `{dict(Counter(row['status'] for row in verify_rows))}`",
            "- The recommended combined RPF preserves the Pass 4 MP tree and adds only decoded XML route replacements.",
            "- WSC sector edits stay out of the default archive until an owned same-size update-thread patch validates.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    build_root = Path(args.build_root)
    build_root.mkdir(parents=True, exist_ok=True)
    reset_dir(build_root / "reports", build_root)
    reset_dir(build_root / "xml_candidates", build_root)
    reset_dir(build_root / "optional_sector_variants", build_root)
    copy_optional_auth(build_root)
    source = Path(args.source)
    backup, source_before = backup_source(source, build_root)
    overlay = load_module(OVERLAY_TOOL, "codered_pass5_overlay")
    utils = load_module(RPF_UTILS_TOOL, "codered_pass5_rpf_utils")
    payloads, xml_rows, xml_report = prepare_xml_candidates(utils, source, build_root)
    variant_targets = {
        "pause_parent": build_root / "pass5_pause_parent_route.rpf",
        "networking_parent": build_root / "pass5_networking_parent_route.rpf",
        "mainmenu_review_fallback": build_root / "pass5_mainmenu_route.rpf",
        "combined": build_root / "content_mp_restore_pass5_access_trainer_sectors.rpf",
    }
    outputs: dict[str, dict[str, Any]] = {}
    verify_rows: list[dict[str, Any]] = []
    for variant, output in variant_targets.items():
        outputs[variant] = write_archive_variant(overlay, source, output, payloads[variant])
        verify_rows.extend(verify_variant(utils, output, variant, payloads[variant]))
    sector_rows = scan_sector_threads(build_root)
    trainer = stage_trainer(build_root)
    source_after = file_meta(source)
    if source_after["sha1"] != source_before["sha1"]:
        raise RuntimeError("Pass 4 base RPF changed during Pass 5 build")
    reports = build_root / "reports"
    write_csv(reports / "mp_pass5_changed_xml_files.csv", xml_rows, XML_REPORT_FIELDS)
    write_csv(reports / "mp_pass5_xml_verification.csv", verify_rows, VERIFY_FIELDS)
    write_text(reports / "mp_pass5_xml_route_report.md", xml_report)
    write_text(reports / "mp_pass5_sector_scan_report.md", sector_scan_md(sector_rows))
    write_text(reports / "mp_pass5_sector_patch_report.md", sector_patch_md())
    write_text(reports / "mp_pass5_wsc_validation.md", wsc_validation_md())
    write_text(reports / "mp_pass5_dev_trainer_report.md", trainer_report_md(trainer))
    write_text(reports / "mp_pass5_test_steps.md", test_steps_md(variant_targets["combined"], trainer))
    write_text(reports / "mp_pass5_build_report.md", build_report_md(source_before, backup, outputs, verify_rows))
    summary = {
        "tool": "codered_mp_restore_pass5_builder",
        "source": source_before,
        "source_unchanged": True,
        "backup": str(backup),
        "recommended_output": str(variant_targets["combined"]),
        "outputs": {name: {"path": built["output"], "entry_count": built["output_info"].get("entry_count"), "mp_counts": mp_counts(built["output_info"])} for name, built in outputs.items()},
        "xml_verification": dict(Counter(row["status"] for row in verify_rows)),
        "sector_scans": dict(Counter(row["status"] for row in sector_rows)),
        "trainer": trainer,
        "default_auth_bypass": False,
        "default_wsc_sector_patch": False,
        "no_live_content_write": True,
    }
    write_json(reports / "mp_pass5_build_summary.json", summary)
    return summary


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Build Pass 5 full-MP access RPF variants from the Pass 4 clone.")
    ap.add_argument("--source", default=str(PASS4_RPF))
    ap.add_argument("--build-root", default=str(BUILD_ROOT))
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
