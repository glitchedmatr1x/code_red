#!/usr/bin/env python3
"""Build a focused local/offline Free Roam seed RPF.

This pass starts from the known-booting Pass 5 RPF, keeps its visible MP menu
route, installs a named WSC bootstrap resource, and changes only local/LAN UI
flow so Code RED Free Roam aims at a local start path instead of invite/join.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GAME_ROOT = ROOT.parent
GAME_CONTENT = GAME_ROOT / "game" / "content.rpf"
RDR_EXE = GAME_ROOT / "RDR.exe"
PASS5_RPF = ROOT / "build" / "mp_content_restore_pass5" / "content_mp_restore_pass5_access_trainer_sectors.rpf"
BUILD_ROOT = ROOT / "build" / "mp_local_freeroam_session_seed"
REPORTS_ROOT = BUILD_ROOT / "reports"
OUTPUT_RPF = BUILD_ROOT / "content_mp_local_freeroam_session_seed.rpf"

PASS3_FIXED_TOOL = ROOT / "tools" / "codered_mp_freeroam_pass3_fixed.py"
WSC_AUTHOR_TOOL = ROOT / "tools" / "codered_wsc_author.py"
RPF_UTILS_TOOL = ROOT / "tools" / "codered_rpf_utils.py"

NETWORK_ARCHIVE = "root/content/ui/pausemenu/networking.sc.xml"
PLAYMP_ARCHIVE = "root/content/ui/pausemenu/net/plaympconf.sc.xml"
LOBBY_ARCHIVE = "root/content/ui/pausemenu/lobby/main.sc.xml"
LONG_ARCHIVE = "root/content/release64/scripting/designerdefined/long_update_thread.wsc"
BOOTSTRAP_ARCHIVE = "root/content/release64/scripting/designerdefined/socialclub/sc_aa_challenge.wsc"
TARGET_LAUNCH_PATH = "$/content/scripting/designerdefined/socialclub/sc_aa_challenge"

LOCAL_SEED_SOURCE = """/*
   Code RED local/offline Free Roam session seed.

   This script intentionally does not spoof public servers or public
   matchmaking. Global_26119 bit 256 is documented by the decompiled donor MP
   thread, but no safe global-write primitive is mapped in this authoring lane,
   so this bootstrap only starts the restored local MP backend scripts.
*/

#include "../include/types.h"
#include "../include/intrinsics.h"
#include "../include/natives.h"
#include "../include/RDR/natives32.h"

void main(void)
{
    int waited;
    int ready;

    waited = 0;
    ready = 0;

    /*
       The long update-thread hook can fire during normal boot. Do not launch
       the restored MP backend until the frontend/net layer has created a
       visible session. NET_GET_PLAYMODE() can be non-zero during startup on
       this PC build, so it is deliberately not used as a launch gate.
    */
    while (waited < 180000)
    {
        if (NET_IS_IN_SESSION())
        {
            ready = 1;
            break;
        }
        WAIT(500);
        waited += 500;
    }

    if (!ready)
    {
        while (true)
        {
            WAIT(0);
        }
    }

    LAUNCH_NEW_SCRIPT("$/content/multiplayer/multiplayer_system_thread", 0);
    WAIT(500);
    LAUNCH_NEW_SCRIPT("$/content/multiplayer/PR_Multiplayer", 0);

    while (true)
    {
        WAIT(0);
    }
}
"""


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def file_meta(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha1": sha1_bytes(data)}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def diff_text(original: str, candidate: str, path: Path, left: str, right: str) -> None:
    diff = "\n".join(
        difflib.unified_diff(original.splitlines(), candidate.splitlines(), fromfile=left, tofile=right, lineterm="")
    )
    write_text(path, diff + ("\n" if diff else ""))


def extract_text_from_rpf(rpf: Path, archive_path: str) -> str:
    utils = load_module(RPF_UTILS_TOOL, "codered_rpf_utils_local_seed_extract")
    wb = utils.load_backend()
    info = utils.parse_archive(rpf)
    entry = utils.find_entry(info, archive_path)
    data = utils.extract_entry_payload(wb, rpf, entry)
    return data.decode("utf-8")


def patch_networking(text: str) -> tuple[str, list[dict[str, Any]]]:
    text = text.replace("\r\n", "\n")
    rows: list[dict[str, Any]] = []

    if "NetConf_CodeRED_FreeRoam" not in text:
        lan_label = """      <UILabel id="NetOffTab_CodeREDLAN" desc="mp_fe_play_lan_tab" target="NetConf_PlayLAN" consume="false">
        <onfocused expr="Select(NetContent_LAN)"></onfocused>
      </UILabel>"""
        new_label = """      <UILabel id="NetOffTab_CodeREDLAN" desc="mp_fe_play_lan_tab" target="NetConf_CodeRED_FreeRoam" consume="false">
        <onfocused expr="Select(NetContent_LAN)"></onfocused>
      </UILabel>"""
        if lan_label in text:
            text = text.replace(lan_label, new_label, 1)
            rows.append({"archive_path": NETWORK_ARCHIVE, "change": "retarget_pass5_codered_lan_label"})
        else:
            fallback_label = """      <UILabel desc="mp_fe_play_lan_tab"     target="NetConf_PlayLAN" consume="false">
        <onfocused expr="Select(NetContent_LAN)"></onfocused>
      </UILabel>"""
            injected_label = """      <!-- CodeRED local/offline Free Roam seed route. -->
      <UILabel id="NetOffTab_CodeREDLAN" desc="mp_fe_play_lan_tab" target="NetConf_CodeRED_FreeRoam" consume="false">
        <onfocused expr="Select(NetContent_LAN)"></onfocused>
      </UILabel>

""" + fallback_label
            if fallback_label not in text:
                raise RuntimeError("Could not find LAN label in networking.sc.xml")
            text = text.replace(fallback_label, injected_label, 1)
            rows.append({"archive_path": NETWORK_ARCHIVE, "change": "insert_codered_lan_label"})

        lan_box = """  <UIMessageBox id="NetConf_PlayLAN">
    <transition event="auth.fail_NotSignedIn">
      <action expr="Exit(NetConf_PlayLAN)"></action>
      <action expr="NetAlert_NotSignedInSysLink"></action>
    </transition>
    <include src="net/PlayMpConf.sc" arg="NetConf_PlayLAN,'LAN Multiplayer','LAN'"></include>
  </UIMessageBox>"""
        codered_box = """  <!-- CodeRED local/offline Free Roam seed route. No public matchmaking. -->
  <UIMessageBox id="NetConf_CodeRED_FreeRoam">
    <data name="Ok_Cancel"></data>
    <data name="Alert"></data>
    <data name="description" expr="MULTI_FREE_ROAM_detail"></data>
    <onshow expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></onshow>
    <transition event="auth.success" consume="false">
      <action expr="Exit(NetConf_CodeRED_FreeRoam)"></action>
      <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
      <action expr="NetMachine.TriggerMultiplayerLoad('LAN')"></action>
    </transition>
    <transition event="auth.fail_NotSignedIn" consume="true">
      <action expr="Exit(NetConf_CodeRED_FreeRoam)"></action>
      <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
      <action expr="NetMachine.TriggerMultiplayerLoad('LAN')"></action>
    </transition>
    <UIPromptStrip>
      <UIButton text="Common_Continue" icon="{@UI.ACCEPT}" e_action_released="NetMachine.Authenticate('LAN Multiplayer')"></UIButton>
      <UIButton text="Common_Cancel" icon="{@UI.CANCEL}" e_cancel_released="Exit(NetConf_CodeRED_FreeRoam)"></UIButton>
    </UIPromptStrip>
  </UIMessageBox>

""" + lan_box
        if lan_box not in text:
            raise RuntimeError("Could not find NetConf_PlayLAN block in networking.sc.xml")
        text = text.replace(lan_box, codered_box, 1)
        rows.append({"archive_path": NETWORK_ARCHIVE, "change": "add_local_freeroam_messagebox"})
    return text, rows


def patch_plaympconf(text: str) -> tuple[str, list[dict[str, Any]]]:
    text = text.replace("\r\n", "\n")
    rows: list[dict[str, Any]] = []
    if "CodeRED local session seed" not in text:
        old = '  <onshow expr="NetMachine.ResetNewGameWarning(arg2)"></onshow>'
        new = old + '\n  <onshow expr="NetMachine.SetGameWish(\'MULTI_FREE_ROAM\')"></onshow>\n  <!-- CodeRED local session seed: only NotSignedIn is rerouted for local/LAN testing. -->'
        if old not in text:
            raise RuntimeError("Could not find PlayMpConf onshow anchor")
        text = text.replace(old, new, 1)
        rows.append({"archive_path": PLAYMP_ARCHIVE, "change": "seed_freeroam_gamewish_onshow"})

        old_fail = """  <transition event="auth.fail_NotSignedIn">
    <action expr="Exit(arg0)"></action>
    <action expr="NetAlert_NotSignedIn"></action>
  </transition>"""
        new_fail = """  <transition event="auth.fail_NotSignedIn">
    <action expr="Exit(arg0)"></action>
    <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
    <action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>
  </transition>"""
        if old_fail not in text:
            raise RuntimeError("Could not find PlayMpConf NotSignedIn branch")
        text = text.replace(old_fail, new_fail, 1)
        rows.append({"archive_path": PLAYMP_ARCHIVE, "change": "local_not_signed_in_to_trigger_load"})
    return text, rows


def patch_lobby(text: str) -> tuple[str, list[dict[str, Any]]]:
    text = text.replace("\r\n", "\n")
    rows: list[dict[str, Any]] = []
    if "CodeRED local Free Roam seed" not in text:
        old = '    <onactivate expr="NetMachine.SendNetModeEvent(OL_NetworkingMenu)" ></onactivate>'
        new = old + "\n    <onactivate expr=\"NetMachine.SetGameWish('MULTI_FREE_ROAM')\" ></onactivate>\n    <!-- CodeRED local Free Roam seed: Free Roam stays selected before any start attempt. -->"
        if old not in text:
            raise RuntimeError("Could not find lobby onactivate anchor")
        text = text.replace(old, new, 1)
        rows.append({"archive_path": LOBBY_ARCHIVE, "change": "seed_lobby_freeroam_gamewish"})

        old_accept = """            <transition event="@UI.ACCEPT*RELEASED" consume="true">
              <action expr="SendEvent('AUDIO_StartMenuItemSelected')"></action>
              <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
              <action expr="goto(NetConf_StartGame)"></action>
            </transition>"""
        new_accept = """            <transition event="@UI.ACCEPT*RELEASED" consume="true">
              <action expr="SendEvent('AUDIO_StartMenuItemSelected')"></action>
              <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
              <action expr="NetMachine.StartGameWish()"></action>
            </transition>"""
        if old_accept not in text:
            raise RuntimeError("Could not find MULTI_FREE_ROAM accept transition")
        text = text.replace(old_accept, new_accept, 1)
        rows.append({"archive_path": LOBBY_ARCHIVE, "change": "free_roam_accept_direct_start_game_wish"})
    return text, rows


def build_seed_bootstrap() -> tuple[Path, dict[str, Any]]:
    author = load_module(WSC_AUTHOR_TOOL, "codered_wsc_author_local_seed")
    build_dir = BUILD_ROOT / "wsc_author"
    spec = author.BuildSpec(
        project_name="codered_author_mp_local_seed",
        output_name="codered_mp_local_seed",
        source=LOCAL_SEED_SOURCE,
        purpose="local/offline Free Roam backend seed; launch system thread then PR_Multiplayer",
    )
    template = author.resolve_template("")
    row = author.build_one(spec, build_dir, template, RDR_EXE, keep_sccl_workspace=False)
    output = build_dir / "codered_mp_local_seed.wsc"
    if row.get("status") != "generated_wsc_validated" or not output.exists():
        raise RuntimeError(f"Seed bootstrap WSC build failed: {row}")
    write_json(REPORTS_ROOT / "mp_local_seed_wsc_author_report.json", row)
    return output, row


def build_local_seed(install_live: bool, boot_test: bool, boot_timeout: int) -> dict[str, Any]:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    pass3 = load_module(PASS3_FIXED_TOOL, "codered_mp_pass3_fixed_local_seed")

    bootstrap_wsc, bootstrap_report = build_seed_bootstrap()
    patched_long = BUILD_ROOT / "working" / "long_update_thread.wsc"
    patch_summary, patch_rows = pass3.patch_long_update_thread(patched_long)

    xml_sources = {
        NETWORK_ARCHIVE: extract_text_from_rpf(PASS5_RPF, NETWORK_ARCHIVE),
        PLAYMP_ARCHIVE: extract_text_from_rpf(PASS5_RPF, PLAYMP_ARCHIVE),
        LOBBY_ARCHIVE: extract_text_from_rpf(PASS5_RPF, LOBBY_ARCHIVE),
    }
    network_text, network_rows = patch_networking(xml_sources[NETWORK_ARCHIVE])
    playmp_text, playmp_rows = patch_plaympconf(xml_sources[PLAYMP_ARCHIVE])
    lobby_text, lobby_rows = patch_lobby(xml_sources[LOBBY_ARCHIVE])
    xml_payloads = {
        NETWORK_ARCHIVE: network_text,
        PLAYMP_ARCHIVE: playmp_text,
        LOBBY_ARCHIVE: lobby_text,
    }
    xml_rows = network_rows + playmp_rows + lobby_rows

    candidates_dir = BUILD_ROOT / "xml_candidates"
    for archive_path, candidate in xml_payloads.items():
        safe = archive_path.replace("root/", "").replace("/", "__")
        original = xml_sources[archive_path]
        write_text(candidates_dir / f"{safe}.decoded.xml", candidate)
        write_text(candidates_dir / f"{safe}.original.decoded.xml", original)
        diff_text(original, candidate, candidates_dir / f"{safe}.diff", f"pass5:{archive_path}", f"local_seed:{archive_path}")

    rows: list[dict[str, Any]] = []
    for source, archive_path, layer in [
        (patched_long, LONG_ARCHIVE, "long_update_thread_hook"),
        (bootstrap_wsc, BOOTSTRAP_ARCHIVE, "named_local_seed_bootstrap_resource"),
    ]:
        data = source.read_bytes()
        rows.append(
            {
                "source_path": str(source),
                "archive_path": archive_path,
                "layer": layer,
                "payload": data,
                "sha1": sha1_bytes(data),
                "size": len(data),
            }
        )
    for archive_path, text in xml_payloads.items():
        data = text.encode("utf-8")
        rows.append(
            {
                "source_path": str(candidates_dir / f"{archive_path.replace('root/', '').replace('/', '__')}.decoded.xml"),
                "archive_path": archive_path,
                "layer": "local_freeroam_xml_seed",
                "payload": data,
                "sha1": sha1_bytes(data),
                "size": len(data),
            }
        )

    build_summary = pass3.build_overlay_rpf(PASS5_RPF, OUTPUT_RPF, rows)
    verify_summary, verify_rows = pass3.verify_output(OUTPUT_RPF, rows[:2])
    write_csv(REPORTS_ROOT / "mp_local_seed_manifest.csv", [{k: v for k, v in row.items() if k != "payload"} for row in rows])
    write_csv(REPORTS_ROOT / "mp_local_seed_long_thread_offsets.csv", patch_rows)
    write_csv(REPORTS_ROOT / "mp_local_seed_xml_changes.csv", xml_rows)
    write_csv(REPORTS_ROOT / "mp_local_seed_wsc_readback_verification.csv", verify_rows)

    install_summary = pass3.install_live(OUTPUT_RPF, "local_seed") if install_live else None
    boot_summary = pass3.run_boot_test(boot_timeout, "local_seed") if boot_test else None

    summary = {
        "pass": "mp_local_freeroam_session_seed",
        "goal": "route Code RED local/LAN Free Roam away from invite/join and seed local MP backend startup",
        "source_base": file_meta(PASS5_RPF),
        "output_rpf": file_meta(OUTPUT_RPF),
        "bootstrap_wsc": file_meta(bootstrap_wsc),
        "bootstrap_author_report": bootstrap_report,
        "long_update_thread_patch": patch_summary,
        "build_summary": build_summary,
        "verify_summary": verify_summary,
        "xml_changes": xml_rows,
        "installed_live": bool(install_summary),
        "install_summary": install_summary,
        "boot_test": boot_summary,
        "global_26119_bit_256_status": "not_patched; no safe global-write primitive mapped in current WSC authoring lane",
        "public_server_spoofing": False,
        "public_matchmaking_patch": False,
    }
    write_json(REPORTS_ROOT / "mp_local_seed_summary.json", summary)
    write_text(
        REPORTS_ROOT / "mp_local_seed_report.md",
        "# Code RED Local Free Roam Session Seed\n\n"
        f"- Base: `{PASS5_RPF}`\n"
        f"- Output: `{OUTPUT_RPF}`\n"
        f"- Named bootstrap resource: `{BOOTSTRAP_ARCHIVE}`\n"
        f"- Long-thread launch path: `{TARGET_LAUNCH_PATH}`\n"
        f"- Installed live: `{bool(install_summary)}`\n"
        f"- Boot test: `{boot_summary['status'] if boot_summary else 'not_run'}`\n\n"
        "## Intent\n\n"
        "- Keep the Pass 5 visible route.\n"
        "- Retarget the Code RED LAN label to `NetConf_CodeRED_FreeRoam`.\n"
        "- Seed `MULTI_FREE_ROAM` before local load/start calls.\n"
        "- Keep public matchmaking and public-server behavior untouched.\n\n"
        "## WSC Seed\n\n"
        "The WSC waits until `NET_IS_IN_SESSION()` before it launches "
        "`$/content/multiplayer/multiplayer_system_thread` first, then `$/content/multiplayer/PR_Multiplayer`. "
        "`Global_26119` bit `256` is not blindly patched because this lane does not yet have a safe mapped "
        "global-write primitive.\n",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-live", action="store_true")
    parser.add_argument("--boot-test", action="store_true")
    parser.add_argument("--boot-timeout", type=int, default=60)
    args = parser.parse_args()
    print(json.dumps(build_local_seed(args.install_live, args.boot_test, args.boot_timeout), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
