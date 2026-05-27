#!/usr/bin/env python3
"""Build a focused MP loading trace candidate.

Base is the latest auth/free-roam D candidate. This pass keeps the converted MP
tree and Free Roam routes intact, then removes remaining local XML gates that
can stall before or during MP loading:

* NetStats/GameSpy XML auth calls from the existing Code RED bypass package.
* wrong-disc/title-update style auth failures in PlayMpConf and taskmachine.
* hidden Zombie entry on Ultimate builds, so the start-screen route is visible.
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
BASE_RPF = ROOT / "build" / "mp_auth_freeroam_pass1" / "D_auth1_execute_direct_xml_zombie_entry_freeroam.rpf"
OUT_ROOT = ROOT / "build" / "mp_loading_trace_pass1"
REPORT_ROOT = ROOT / "reports" / "mp_loading_trace_pass1"
GAME_COPY_ROOT = GAME_ROOT / "mp_loading_trace_pass1"
EXTRACT_ROOT = OUT_ROOT / "D_extract"
NETSTATS_BYPASS = OUT_ROOT / "netstats_gamespy_auth_bypass_pass1_full_package" / "variants" / "variant_B_full_auth_failure_bypass"
LATEST_BUILDER = ROOT / "tools" / "codered_mp_latest_candidate_builder.py"
OUTPUT_RPF = OUT_ROOT / "E_loading_trace_gamespy_titleupdate_bypass.rpf"
GAME_COPY = GAME_COPY_ROOT / OUTPUT_RPF.name
OUTPUT_RPF_NO_BOOT = OUT_ROOT / "F_loading_trace_no_boot_patch.rpf"
GAME_COPY_NO_BOOT = GAME_COPY_ROOT / OUTPUT_RPF_NO_BOOT.name


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


latest = load_module(LATEST_BUILDER, "codered_mp_latest_candidate_builder_for_loading_trace")


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


def patch_text(path: Path, replacements: list[tuple[str, str, str]], out_name: str) -> tuple[Path, list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    edits: list[dict[str, Any]] = []
    for old, new, reason in replacements:
        count = text.count(old)
        if count < 1:
            raise RuntimeError(f"pattern not found in {path}: {reason}")
        text = text.replace(old, new)
        edits.append({"source": str(path), "reason": reason, "replace_count": count})
    ET.fromstring(text)
    out = OUT_ROOT / "patched_xml" / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out, edits


def patch_boot() -> tuple[Path, list[dict[str, Any]]]:
    boot = EXTRACT_ROOT / "content" / "ui" / "boot.sc.xml"
    replacements = [
        (
            '    <onfocused\texpr="Exclude(StartScreen_Zombie)"></onfocused>',
            '    <!-- CodeRED loading trace: keep StartScreen_Zombie visible as local Free Roam test route. -->',
            "keep Zombie start entry visible on Ultimate builds",
        ),
        (
            '<UIButton text="Common_Yes" icon="{@UI.ACCEPT}" e_action_released="NetMachine.Authenticate(\'Online\')" ></UIButton>',
            '<UIButton text="Common_Yes" icon="{@UI.ACCEPT}" e_action_released="SendEvent(\'auth.success\')" ></UIButton>',
            "avoid Online auth call in SSConf_JoinWish",
        ),
        (
            """      <transition event="auth.fail_NotSignedIn">
        <action expr="Exit(SSConf_JoinWish)"></action>
        <action expr="SSAlert_NotSignedIn"></action>
      </transition>""",
            """      <transition event="auth.fail_NotSignedIn">
        <action expr="SendEvent('auth.success')"></action>
      </transition>""",
            "route SSConf_JoinWish not-signed-in failure to auth.success",
        ),
        (
            """      <transition event="auth.fail_NoCable">
        <action expr="Exit(SSConf_JoinWish)"></action>
        <action expr="SSAlert_NoCable"></action>
      </transition>""",
            """      <transition event="auth.fail_NoCable">
        <action expr="SendEvent('auth.success')"></action>
      </transition>""",
            "route SSConf_JoinWish no-cable failure to auth.success",
        ),
        (
            """      <transition event="auth.fail_NotOnline">
        <action expr="Exit(SSConf_JoinWish)"></action>
        <action expr="SSAlert_NotOnline"></action>
      </transition>""",
            """      <transition event="auth.fail_NotOnline">
        <action expr="SendEvent('auth.success')"></action>
      </transition>""",
            "route SSConf_JoinWish not-online failure to auth.success",
        ),
        (
            """      <transition event="auth.fail_Privileges">
        <action expr="Exit(SSConf_JoinWish)"></action>
        <action expr="SSAlert_BlockedMP"></action>
      </transition>""",
            """      <transition event="auth.fail_Privileges">
        <action expr="SendEvent('auth.success')"></action>
      </transition>""",
            "route SSConf_JoinWish privileges failure to auth.success",
        ),
        (
            """        <transition event="auth.fail_WrongDisc">
          <action expr="Exit(SSConf_JoinWish)"           ></action>
          <action expr="Enter(NetConf_JoinWishWrongDisc)" ></action>
        </transition>""",
            """        <transition event="auth.fail_WrongDisc">
          <action expr="SendEvent('auth.success')" ></action>
        </transition>""",
            "route wrong-disc/title-update style failure to auth.success",
        ),
        (
            """      <transition event="auth.success">
        <action expr="Exit(SSConf_JoinWish)"></action>
        <action expr="SendEvent('net.EnterOnlineForInvite')"></action>
      </transition>""",
            """      <transition event="auth.success">
        <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
        <action expr="Exit(SSConf_JoinWish)"></action>
        <action expr="SendEvent('net.EnterOnlineForInvite')"></action>
      </transition>""",
            "seed MULTI_FREE_ROAM before invite/JoinWish MP load path",
        ),
        (
            """      <transition event="net.EnterOnlineForInvite" >
        <action expr="SendEvent('fileSetForMPLoad')"></action>
        <action expr="NetMachine.SetMultiplayerModeToLaunch('JoinWish')"></action>
        <action expr="UIGame.ValidateNormalMode()"></action>""",
            """      <transition event="net.EnterOnlineForInvite" >
        <action expr="SendEvent('fileSetForMPLoad')"></action>
        <action expr="NetMachine.SetMultiplayerModeToLaunch('Offline')"></action>
        <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
        <action expr="UIGame.ValidateNormalMode()"></action>""",
            "avoid JoinWish mode when forcing local/offline Free Roam",
        ),
    ]
    return patch_text(boot, replacements, "boot.sc.xml")


def patch_plaympconf() -> tuple[Path, list[dict[str, Any]]]:
    play = EXTRACT_ROOT / "content" / "ui" / "pausemenu" / "net" / "plaympconf.sc.xml"
    replacements = [
        (
            """  <ifdef expr="ULTIMATE_1">
    <data name="description" expr="mp_enter_warning_wrongdisc"></data>
  </ifdef>""",
            """  <!-- CodeRED loading trace: suppress wrong-disc/title-update warning for local Free Roam tests. -->""",
            "suppress wrong-disc warning text",
        ),
        (
            """  <ifdef expr="ULTIMATE_1">
    <transition event="auth.fail_WrongDisc">
      <action expr="Exit(arg0)"           ></action>
      <action expr="Enter(NetConf_JoinWishWrongDisc)" ></action>
    </transition>
  </ifdef>""",
            """  <transition event="auth.fail_WrongDisc">
    <action expr="SendEvent('auth.success')"></action>
  </transition>""",
            "route wrong-disc/title-update style failure to auth.success",
        ),
        (
            '<action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>',
            '<action expr="NetMachine.SetGameWish(\'MULTI_FREE_ROAM\')"></action>\n    <action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>',
            "seed MULTI_FREE_ROAM immediately before TriggerMultiplayerLoad(arg2)",
        ),
    ]
    return patch_text(play, replacements, "plaympconf.sc.xml")


def patch_taskmachine() -> tuple[Path, list[dict[str, Any]]]:
    task = EXTRACT_ROOT / "content" / "ui" / "net" / "taskmachine.sc.xml"
    replacements = [
        (
            '<UIButton text="Common_Yes" icon="action" e_action_released="NetMachine.Authenticate(\'Online\')" ></UIButton>',
            '<UIButton text="Common_Yes" icon="action" e_action_released="SendEvent(\'auth.success\')" ></UIButton>',
            "avoid Online auth call in NetConf_JoinWish",
        ),
        (
            """        <transition event="auth.fail_NotSignedIn">
          <action expr="Exit(NetConf_JoinWish)"></action>
          <action expr="NetAlert_NotSignedIn"></action>
        </transition>""",
            """        <transition event="auth.fail_NotSignedIn">
          <action expr="SendEvent('auth.success')"></action>
        </transition>""",
            "route NetConf_JoinWish not-signed-in failure to auth.success",
        ),
        (
            """        <transition event="auth.fail_NoCable">
          <action expr="Exit(NetConf_JoinWish)"></action>
          <action expr="NetAlert_NoCable"></action>
        </transition>""",
            """        <transition event="auth.fail_NoCable">
          <action expr="SendEvent('auth.success')"></action>
        </transition>""",
            "route NetConf_JoinWish no-cable failure to auth.success",
        ),
        (
            """        <transition event="auth.fail_NotOnline">
          <action expr="Exit(NetConf_JoinWish)"></action>
          <action expr="NetAlert_NotOnline"></action>
        </transition>""",
            """        <transition event="auth.fail_NotOnline">
          <action expr="SendEvent('auth.success')"></action>
        </transition>""",
            "route NetConf_JoinWish not-online failure to auth.success",
        ),
        (
            """        <transition event="auth.fail_Privileges">
          <action expr="Exit(NetConf_JoinWish)"></action>
          <action expr="NetAlert_BlockedMP"></action>
        </transition>""",
            """        <transition event="auth.fail_Privileges">
          <action expr="SendEvent('auth.success')"></action>
        </transition>""",
            "route NetConf_JoinWish privileges failure to auth.success",
        ),
        (
            """          <transition event="auth.fail_WrongDisc">
            <action expr="Exit(NetConf_JoinWish)"           ></action>
            <action expr="Enter(NetConf_JoinWishWrongDisc)" ></action>
          </transition>""",
            """          <transition event="auth.fail_WrongDisc">
            <action expr="SendEvent('auth.success')" ></action>
          </transition>""",
            "route NetConf_JoinWish wrong-disc/title-update failure to auth.success",
        ),
        (
            """        <transition event="auth.success">
          <action expr="Exit(NetConf_JoinWish)"   ></action>
          <action expr="StackPush(HudSceneOnline)"></action>
          <action expr="Enter(NM_JoinProcess)"    ></action>""",
            """        <transition event="auth.success">
          <action expr="NetMachine.SetGameWish('MULTI_FREE_ROAM')"></action>
          <action expr="Exit(NetConf_JoinWish)"   ></action>
          <action expr="StackPush(HudSceneOnline)"></action>
          <action expr="Enter(NM_JoinProcess)"    ></action>""",
            "seed MULTI_FREE_ROAM before taskmachine TriggerMultiplayerLoad",
        ),
    ]
    return patch_text(task, replacements, "taskmachine.sc.xml")


def netstats_rows() -> list[dict[str, Any]]:
    rows = []
    mappings = [
        ("main.sc.xml", "root/content/ui/pausemenu/netstats/main.sc.xml"),
        ("prompts.sc.xml", "root/content/ui/pausemenu/netstats/prompts.sc.xml"),
        ("errormsg.sc.xml", "root/content/ui/pausemenu/netstats/errormsg.sc.xml"),
        ("errormsgrecovery.sc.xml", "root/content/ui/pausemenu/netstats/errormsgrecovery.sc.xml"),
    ]
    for name, archive_path in mappings:
        source = NETSTATS_BYPASS / name
        payload = source.read_bytes()
        rows.append(latest.make_row("netstats_gamespy_auth_bypass_variant_B", source, archive_path, payload, False, "replace"))
    return rows


def build(output_rpf: Path = OUTPUT_RPF, game_copy: Path = GAME_COPY, include_boot: bool = True) -> dict[str, Any]:
    rows = []
    edit_rows: list[dict[str, Any]] = []
    patched_play, play_edits = patch_plaympconf()
    patched_task, task_edits = patch_taskmachine()
    patched_files = [
        (patched_play, "root/content/ui/pausemenu/net/plaympconf.sc.xml", "plaympconf_wrongdisc_local_freeroam", play_edits),
        (patched_task, "root/content/ui/net/taskmachine.sc.xml", "taskmachine_gamespy_joinwish_local_freeroam", task_edits),
    ]
    if include_boot:
        patched_boot, boot_edits = patch_boot()
        patched_files.insert(0, (patched_boot, "root/content/ui/boot.sc.xml", "boot_joinwish_wrongdisc_local_freeroam", boot_edits))
    for source, archive_path, layer, edits in patched_files:
        payload = source.read_bytes()
        rows.append(latest.make_row(layer, source, archive_path, payload, False, "replace"))
        for edit in edits:
            edit_rows.append({"archive_path": archive_path, "layer": layer, **edit})
    rows.extend(netstats_rows())

    result = latest.build_overlay_rpf(BASE_RPF, output_rpf, rows)
    validation = latest.verify_rows(output_rpf, rows)
    failures = [row for row in validation if row.get("status") != "exact_match"]
    game_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_rpf, game_copy)
    manifest = [{k: v for k, v in row.items() if k != "payload"} for row in rows]
    summary = {
        "base_rpf": str(BASE_RPF),
        "base_sha1": sha1_file(BASE_RPF),
        "output_rpf": str(output_rpf),
        "output_sha1": sha1_file(output_rpf),
        "game_copy": str(game_copy),
        "game_copy_sha1": sha1_file(game_copy),
        "include_boot_patch": include_boot,
        "row_count": len(rows),
        "readback_exact": len(validation) - len(failures),
        "readback_failures": len(failures),
        "build": result,
        "manifest": manifest,
        "validation": validation,
        "edits": edit_rows,
    }
    return summary


def write_reports(summaries: list[dict[str, Any]]) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_ROOT / "summary.json", {"candidates": summaries})
    write_csv(REPORT_ROOT / "manifest.csv", [dict(row, candidate=item["output_rpf"]) for item in summaries for row in item["manifest"]])
    write_csv(REPORT_ROOT / "readback_validation.csv", [dict(row, candidate=item["output_rpf"]) for item in summaries for row in item["validation"]])
    write_csv(REPORT_ROOT / "xml_edits.csv", [dict(row, candidate=item["output_rpf"]) for item in summaries for row in item["edits"]])
    summary = summaries[0]
    lines = [
        "# MP Loading Trace Pass 1",
        "",
        "This candidate is a cloned RPF only. It keeps the converted MP tree and the D auth/free-roam route, then removes remaining local XML gates before MP loading.",
        "",
        f"- base: `{summary['base_rpf']}`",
        f"- base SHA1: `{summary['base_sha1']}`",
        f"- output: `{summary['output_rpf']}`",
        f"- game copy: `{summary['game_copy']}`",
        f"- output SHA1: `{summary['output_sha1']}`",
        f"- changed entries: `{summary['row_count']}`",
        f"- readback failures: `{summary['readback_failures']}`",
        "",
        "## Included Changes",
        "",
        "- NetStats/GameSpy variant B: removes NetMachine auth calls from leaderboard/netstats XML paths.",
        "- `plaympconf.sc.xml`: treats wrong-disc/title-update style failure as auth success and seeds `MULTI_FREE_ROAM` before `TriggerMultiplayerLoad(arg2)`.",
        "- `taskmachine.sc.xml`: skips Online auth in `NetConf_JoinWish`, routes local auth failures to success, and seeds `MULTI_FREE_ROAM` before the JoinWish loading path.",
        "- `boot.sc.xml`: keeps the Zombie start entry visible on Ultimate builds and routes its local Free Roam/JoinWish path away from Online/JoinWish gates.",
        "",
        "## Test Goal",
        "",
        "The expected useful result is either reaching a later loading state, an online HUD scene, a new crash after MP backend work starts, or a more specific missing-resource/session error.",
        "",
        "## Candidates",
        "",
    ]
    for item in summaries:
        lines.extend([
            f"- `{item['output_rpf']}`",
            f"  - SHA1: `{item['output_sha1']}`",
            f"  - boot patch included: `{item['include_boot_patch']}`",
            f"  - readback failures: `{item['readback_failures']}`",
        ])
    (REPORT_ROOT / "build_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    test = [
        "# MP Loading Trace Test Steps",
        "",
        "1. Back up `D:\\Games\\Red Dead Redemption\\game\\content.rpf`.",
        f"2. Copy either `{GAME_COPY}` or `{GAME_COPY_NO_BOOT}` to `D:\\Games\\Red Dead Redemption\\game\\content.rpf`.",
        "3. Launch the original Red Dead Redemption PC install.",
        "4. Wait at least two minutes. If it closes before then, this candidate failed at boot/startup.",
        "5. Try the visible MP/Free Roam route and the start-screen Zombie/Free Roam route.",
        "6. Record whether it reaches loading, online HUD scene, unable-to-join, hang, crash, or returns to menu.",
        "7. Restore the backed-up `content.rpf` after testing.",
    ]
    (REPORT_ROOT / "test_steps.md").write_text("\n".join(test) + "\n", encoding="utf-8")


def main() -> int:
    for path in [BASE_RPF, NETSTATS_BYPASS, EXTRACT_ROOT / "content" / "ui" / "boot.sc.xml"]:
        if not path.exists():
            raise FileNotFoundError(path)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summaries = [
        build(OUTPUT_RPF, GAME_COPY, include_boot=True),
        build(OUTPUT_RPF_NO_BOOT, GAME_COPY_NO_BOOT, include_boot=False),
    ]
    write_reports(summaries)
    print(json.dumps({"candidates": summaries}, indent=2))
    return 0 if all(item["readback_failures"] == 0 for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
