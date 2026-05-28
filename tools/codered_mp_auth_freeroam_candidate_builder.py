#!/usr/bin/env python3
"""Build auth/free-roam RPF candidates from the latest Code RED MP base.

This script never overwrites the live game content.rpf. It creates cloned RPFs
that isolate the current auth hypothesis:

* control: change the skipped auth argument only.
* execute: unskip NET_AUTHENTICATE_GAMER and change the bool-like arg 0 -> 1.
* direct XML: execute auth1 plus the direct Free Roam XML route.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = ROOT.parent / "game"
BASE_RPF = ROOT / "build" / "mp_latest_candidate_pass1" / "content.rpf"
MP_PASS = GAME_ROOT / "XENON MULTIPLAYER" / "mp pass"
SOURCE_PRESSSTART = MP_PASS / "pressstart_D_full_force.wsc"
DIRECT_XML = MP_PASS / "03_direct_start_experimental"
OUT_ROOT = ROOT / "build" / "mp_auth_freeroam_pass1"
REPORT_ROOT = ROOT / "reports" / "mp_auth_freeroam_pass1"
GAME_COPY_ROOT = GAME_ROOT / "mp_auth_freeroam_pass1"
RDR_EXE = ROOT.parent / "RDR.exe"

LATEST_BUILDER = ROOT / "tools" / "codered_mp_latest_candidate_builder.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


latest = load_module(LATEST_BUILDER, "codered_mp_latest_candidate_builder_for_auth_pass")


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def patch_pressstart(name: str, execute_auth: bool, auth_arg_one: bool) -> tuple[Path, dict[str, Any]]:
    from codered_wsc.resource import KeyOptions, open_script, repack_script

    resource = open_script(SOURCE_PRESSSTART, KeyOptions(rdr_exe=str(RDR_EXE)))
    decoded = bytearray(resource.decoded)
    edits: list[dict[str, Any]] = []

    def replace(offset: int, old: bytes, new: bytes, reason: str) -> None:
        actual = bytes(decoded[offset : offset + len(old)])
        if actual != old:
            raise RuntimeError(f"{name}: expected {old.hex()} at decoded 0x{offset:X}, got {actual.hex()}")
        decoded[offset : offset + len(old)] = new
        edits.append(
            {
                "decoded_offset": f"0x{offset:X}",
                "old_hex": old.hex(" ").upper(),
                "new_hex": new.hex(" ").upper(),
                "reason": reason,
            }
        )

    if execute_auth:
        replace(
            0x25,
            bytes.fromhex("62 00 1B"),
            bytes.fromhex("00 00 00"),
            "remove existing unconditional jump that skips NET_AUTHENTICATE_GAMER block",
        )
    if auth_arg_one:
        replace(
            0x28,
            bytes.fromhex("8B"),
            bytes.fromhex("8C"),
            "change bool-like auth argument immediately before 'Multiplayer Online' from 0 to 1",
        )

    payload, repack_report = repack_script(resource, bytes(decoded), allow_growth=False)
    out = OUT_ROOT / "patched_wsc" / f"{name}_pressstart.wsc"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    report = {
        "variant": name,
        "source": str(SOURCE_PRESSSTART),
        "output": str(out),
        "source_decoded_sha256": resource.header_dict().get("decoded_sha256"),
        "output_sha1": sha1_bytes(payload),
        "execute_auth": execute_auth,
        "auth_arg_one": auth_arg_one,
        "edits": edits,
        "repack": repack_report,
    }
    return out, report


def direct_xml_rows() -> list[dict[str, Any]]:
    mappings = [
        (DIRECT_XML / "ui" / "pausemenu" / "pausemenuscene.sc.xml", "root/content/ui/pausemenu/pausemenuscene.sc.xml"),
        (DIRECT_XML / "ui" / "pausemenu" / "networking.sc.xml", "root/content/ui/pausemenu/networking.sc.xml"),
        (DIRECT_XML / "ui" / "pausemenu" / "net" / "lanmenu.sc.xml", "root/content/ui/pausemenu/net/lanmenu.sc.xml"),
        (DIRECT_XML / "ui" / "pausemenu" / "net" / "plaympconf.sc.xml", "root/content/ui/pausemenu/net/plaympconf.sc.xml"),
        (DIRECT_XML / "ui" / "pausemenu" / "lobby" / "main.sc.xml", "root/content/ui/pausemenu/lobby/main.sc.xml"),
    ]
    rows = []
    for source, archive_path in mappings:
        payload = source.read_bytes()
        rows.append(latest.make_row("ui_direct_freeroam_route_variant03", source, archive_path, payload, False, "replace"))
    return rows


def patch_boot_zombie_to_freeroam(name: str) -> tuple[Path, dict[str, Any]]:
    source = MP_PASS / "boot.sc.xml"
    text = source.read_text(encoding="utf-8")
    text_old = '<UILabel id="StartScreen_Zombie" text="StartScreen_Zombie" icon="{@UI.CANCEL}" value="5592405">'
    text_new = '<UILabel id="StartScreen_Zombie" text="StartScreen_MPNormal" icon="{@UI.CANCEL}" value="5592405">'
    block_old = """              <action expr="NetMachine.SetMultiplayerModeToLaunch('Offline')"></action>
              <action expr="RemoveDelayedEvent('net.signedOffline')"></action>
              <action expr="RemoveDelayedEvent('net.lostConnection')"></action>
              <action expr="Exit(SinglePlayerList)"></action>
              <action expr="UIGame.ValidateZombieMode()"></action>
              <action expr="PlaySound('HUD_MENU_SELECT_MASTER')"></action>
\t\t\t  <action expr="Exit(StartScreen2PromptStrip)"></action>"""
    block_new = """              <action expr="NetMachine.SetMultiplayerModeToLaunch('Offline')"></action>
              <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
              <action expr="RemoveDelayedEvent('net.signedOffline')"></action>
              <action expr="RemoveDelayedEvent('net.lostConnection')"></action>
              <action expr="Exit(SinglePlayerList)"></action>
              <action expr="UIGame.ValidateNormalMode()"></action>
              <action expr="PlaySound('HUD_MENU_SELECT_MASTER')"></action>
              <action expr="SendEvent('mainMenuExit')"></action>
              <action expr="SendEvent('net.EnterOnline')"></action>
              <action expr="Enter(LoadingScreen)"></action>
              <action expr="Enter(waitforInTransition)"></action>
\t\t\t  <action expr="Exit(StartScreen2PromptStrip)"></action>"""
    if text_old not in text:
        raise RuntimeError("Zombie label text pattern was not found in boot.sc.xml")
    if block_old not in text:
        raise RuntimeError("Zombie action block pattern was not found in boot.sc.xml")
    patched = text.replace(text_old, text_new, 1).replace(block_old, block_new, 1)
    ET.fromstring(patched)
    out = OUT_ROOT / "patched_xml" / f"{name}_boot.sc.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(patched, encoding="utf-8")
    return out, {
        "variant": name,
        "source": str(source),
        "output": str(out),
        "source_sha1": sha1_bytes(text.encode("utf-8")),
        "output_sha1": sha1_bytes(patched.encode("utf-8")),
        "edits": [
            {
                "target": "StartScreen_Zombie label",
                "old": "StartScreen_Zombie",
                "new": "StartScreen_MPNormal",
            },
            {
                "target": "StartScreen_Zombie accept route",
                "old": "ValidateZombieMode without net.EnterOnline",
                "new": "SetGameWish MULTI_FREE_ROAM + ValidateNormalMode + net.EnterOnline + loading screen",
            },
        ],
        "xml_parse_ok": True,
    }


def build_variant(
    name: str,
    execute_auth: bool,
    auth_arg_one: bool,
    include_direct_xml: bool,
    include_zombie_boot_route: bool = False,
) -> dict[str, Any]:
    patched_pressstart, wsc_report = patch_pressstart(name, execute_auth=execute_auth, auth_arg_one=auth_arg_one)
    rows = [
        latest.make_row(
            f"{name}_pressstart_auth_patch",
            patched_pressstart,
            "root/content/release64/pressstart.wsc",
            patched_pressstart.read_bytes(),
            True,
            "replace",
        )
    ]
    if include_direct_xml:
        rows.extend(direct_xml_rows())
    boot_report: dict[str, Any] | None = None
    if include_zombie_boot_route:
        patched_boot, boot_report = patch_boot_zombie_to_freeroam(name)
        rows.append(
            latest.make_row(
                "ui_boot_zombie_entry_to_freeroam_route",
                patched_boot,
                "root/content/ui/boot.sc.xml",
                patched_boot.read_bytes(),
                False,
                "replace",
            )
        )

    output_rpf = OUT_ROOT / f"{name}.rpf"
    build = latest.build_overlay_rpf(BASE_RPF, output_rpf, rows)
    validation = latest.verify_rows(output_rpf, rows)
    failures = [row for row in validation if row.get("status") != "exact_match"]
    game_copy = GAME_COPY_ROOT / output_rpf.name
    game_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_rpf, game_copy)
    manifest = [{k: v for k, v in row.items() if k != "payload"} for row in rows]

    return {
        "variant": name,
        "execute_auth": execute_auth,
        "auth_arg_one": auth_arg_one,
        "include_direct_xml": include_direct_xml,
        "include_zombie_boot_route": include_zombie_boot_route,
        "base_rpf": str(BASE_RPF),
        "base_sha1": sha1_file(BASE_RPF),
        "output_rpf": str(output_rpf),
        "output_sha1": sha1_file(output_rpf),
        "game_copy": str(game_copy),
        "game_copy_sha1": sha1_file(game_copy),
        "row_count": len(rows),
        "readback_exact": len(validation) - len(failures),
        "readback_failures": len(failures),
        "wsc_report": wsc_report,
        "boot_report": boot_report,
        "build": build,
        "manifest": manifest,
        "validation": validation,
    }


def write_reports(results: list[dict[str, Any]]) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_ROOT / "summary.json", {"variants": results})
    write_csv(
        REPORT_ROOT / "variants.csv",
        [
            {
                "variant": item["variant"],
                "execute_auth": item["execute_auth"],
                "auth_arg_one": item["auth_arg_one"],
        "include_direct_xml": item["include_direct_xml"],
                "include_zombie_boot_route": item["include_zombie_boot_route"],
                "base_sha1": item["base_sha1"],
                "output_rpf": item["output_rpf"],
                "output_sha1": item["output_sha1"],
                "game_copy": item["game_copy"],
                "row_count": item["row_count"],
                "readback_failures": item["readback_failures"],
            }
            for item in results
        ],
    )
    all_manifest: list[dict[str, Any]] = []
    all_validation: list[dict[str, Any]] = []
    all_wsc: list[dict[str, Any]] = []
    for item in results:
        for row in item["manifest"]:
            row = dict(row)
            row["variant"] = item["variant"]
            all_manifest.append(row)
        for row in item["validation"]:
            row = dict(row)
            row["variant"] = item["variant"]
            all_validation.append(row)
        for edit in item["wsc_report"]["edits"]:
            edit = dict(edit)
            edit["variant"] = item["variant"]
            edit["patched_wsc"] = item["wsc_report"]["output"]
            all_wsc.append(edit)
    write_csv(REPORT_ROOT / "manifest.csv", all_manifest)
    write_csv(REPORT_ROOT / "readback_validation.csv", all_validation)
    write_csv(REPORT_ROOT / "wsc_changed_offsets.csv", all_wsc)

    lines = [
        "# MP Auth Free Roam Candidate Pass 1",
        "",
        "This pass builds cloned RPF candidates only. It does not overwrite the live `game/content.rpf`.",
        "",
        f"- base RPF: `{BASE_RPF}`",
        f"- base SHA1: `{sha1_file(BASE_RPF)}`",
        f"- source WSC: `{SOURCE_PRESSSTART}`",
        "",
        "## Key Finding",
        "",
        "The existing `pressstart_D_full_force.wsc` skipped the `NET_AUTHENTICATE_GAMER(0, \"Multiplayer Online\")` block with a decoded jump at `0x25`.",
        "Therefore a real 0-to-1 authentication experiment needs both the argument edit and a variant that removes that skip.",
        "",
        "## Variants",
        "",
    ]
    for item in results:
        lines.extend(
            [
                f"### {item['variant']}",
                "",
                f"- output: `{item['output_rpf']}`",
                f"- game-folder copy: `{item['game_copy']}`",
                f"- SHA1: `{item['output_sha1']}`",
                f"- execute auth block: `{item['execute_auth']}`",
                f"- auth arg one: `{item['auth_arg_one']}`",
        f"- direct Free Roam XML: `{item['include_direct_xml']}`",
                f"- Zombie/Ultimate-style boot entry route: `{item['include_zombie_boot_route']}`",
                f"- readback failures: `{item['readback_failures']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Intended Test Order",
            "",
            "1. `A_auth1_keep_skip_control.rpf` should behave like the previous candidate because the auth block remains skipped.",
            "2. `B_auth1_execute.rpf` tests the actual `NET_AUTHENTICATE_GAMER(1, \"Multiplayer Online\")` path.",
            "3. `C_auth1_execute_direct_freeroam_xml.rpf` combines the auth test with the stronger direct Free Roam XML route.",
            "4. `D_auth1_execute_direct_xml_zombie_entry_freeroam.rpf` additionally repoints the Zombie start-screen entry to the Free Roam/MP-load route.",
            "",
            "If any candidate closes in under two minutes, restore the known backup before testing the next one.",
        ]
    )
    (REPORT_ROOT / "build_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    test_steps = [
        "# MP Auth Free Roam Candidate Test Steps",
        "",
        "1. Back up `%RDR_GAME_DIR%\\game\\content.rpf`.",
        "2. Test only one candidate at a time by copying it over `content.rpf`.",
        "3. Start with `%RDR_GAME_DIR%\\game\\mp_auth_freeroam_pass1\\A_auth1_keep_skip_control.rpf`.",
        "4. Then test `B_auth1_execute.rpf`.",
        "5. Then test `C_auth1_execute_direct_freeroam_xml.rpf`.",
        "6. Finally test `D_auth1_execute_direct_xml_zombie_entry_freeroam.rpf` if C still does not reach a later MP state.",
        "7. For each one, launch the original Red Dead Redemption PC install and wait at least two minutes.",
        "8. Record whether it reaches menu, Zombie/MP option, Free Roam option, loading, online HUD, unable-to-join, hang, or crash.",
        "9. Restore the original `content.rpf` after testing.",
    ]
    (REPORT_ROOT / "test_steps.md").write_text("\n".join(test_steps) + "\n", encoding="utf-8")


def main() -> int:
    for required in [BASE_RPF, SOURCE_PRESSSTART, DIRECT_XML]:
        if not required.exists():
            raise FileNotFoundError(required)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = [
        build_variant("A_auth1_keep_skip_control", execute_auth=False, auth_arg_one=True, include_direct_xml=False),
        build_variant("B_auth1_execute", execute_auth=True, auth_arg_one=True, include_direct_xml=False),
        build_variant("C_auth1_execute_direct_freeroam_xml", execute_auth=True, auth_arg_one=True, include_direct_xml=True),
        build_variant(
            "D_auth1_execute_direct_xml_zombie_entry_freeroam",
            execute_auth=True,
            auth_arg_one=True,
            include_direct_xml=True,
            include_zombie_boot_route=True,
        ),
    ]
    write_reports(results)
    print(json.dumps({"variants": results}, indent=2))
    return 0 if all(item["readback_failures"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
