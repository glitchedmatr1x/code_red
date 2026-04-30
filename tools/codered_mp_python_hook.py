#!/usr/bin/env python3
"""Code RED MP Python hook / content override builder.

This is a conservative pre-launch hook. It does not hook process memory and it
never edits the source archive in place unless `activate` is explicitly used.

Primary job:
- read the current content.rpf
- extract the current PlayMpConf SCXML
- build a donor-style MP override patch from the live file
- apply that patch to a copied content.rpf through the bundled Code RED runtime
- write proof reports and state files for the MP Companion / Workbench

The override is intentionally small: PlayMpConf auth failures are routed to
NetMachine.TriggerMultiplayerLoad(arg2), preserving the rest of the current
version file. This matches the working.zip research clue without bulk merging
mixed-version UI files.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

PLAYMPCONF_PATH = "root/content/ui/pausemenu/0x007B97C6/plaympconf.sc.xml"
NETWORKING_PATH = "root/content/ui/pausemenu/networking.sc.xml"
TASKMACHINE_PATH = "root/content/ui/net/taskmachine.sc.xml"
LOBBY_PATH = "root/content/ui/pausemenu/lobby/0x2B5C38A8"
HUDONLINE_PATH = "root/content/ui/net/hudsceneonline.sc.xml"
STATE_FILE = "mp_python_hook_state.json"

AUTH_FAILURE_ALERTS = {
    "auth.fail_NotSignedIn": "NetAlert_NotSignedIn",
    "auth.fail_NoCable": "NetAlert_NoCable",
    "auth.fail_NotOnline": "NetAlert_NotOnline",
    "auth.fail_Privileges": "NetAlert_BlockedMP",
    "auth.fail_WrongDisc": "Enter(NetConf_JoinWishWrongDisc)",
}

CORE_MP_MARKERS = [
    "NetMachine.TriggerMultiplayerLoad",
    "NetMachine.StartMultiplayer",
    "NetScene.RequestJoin",
    "NetMachine.ReturnToFreeRoam",
    "MULTI_FREE_ROAM",
    "NetMachine.SetGameWish",
    "NetConf_StartGame",
    "HudSceneOnline",
]


@dataclass
class ExtractedText:
    path: str
    found: bool
    decode_ok: bool
    text: str
    size: int
    error: str = ""


@dataclass
class BuildResult:
    ok: bool
    mode: str
    source_archive: str
    working_copy: str
    patch_root: str
    report_json: str
    report_md: str
    state_path: str
    changed_actions: int
    xml_valid_before: bool
    xml_valid_after: bool
    applied: int
    blocked: int
    warnings: list[str]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "python_workbench.py").exists() or (candidate / "tools").exists() or (candidate / ".git").exists():
            return candidate
    return current


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_runtime(repo_root: Path, companion_root: Path | None = None):
    candidates = []
    if companion_root:
        candidates.append(companion_root / "runtime" / "codered_runtime.py")
    candidates.extend(
        [
            repo_root / "related_apps" / "Code_RED_MP_Companion_v19" / "runtime" / "codered_runtime.py",
            repo_root / "runtime" / "codered_runtime.py",
            repo_root / "python_workbench.py",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            module = load_module(candidate, "codered_mp_hook_runtime")
            return module, candidate
    raise FileNotFoundError("Could not find Code RED runtime or python_workbench.py")


def load_rpf6(repo_root: Path, runtime_module: Any):
    rpf6 = getattr(runtime_module, "RPF6", None)
    if rpf6 is not None:
        return rpf6
    tool_candidates = [
        repo_root / "tools" / "codered_wsi_explorer.py",
        repo_root / "codered_wsi_explorer.py",
    ]
    for candidate in tool_candidates:
        if candidate.exists():
            if str(candidate.parent) not in sys.path:
                sys.path.insert(0, str(candidate.parent))
            module = load_module(candidate, "codered_mp_hook_wsi_explorer")
            rpf6 = getattr(module, "RPF6", None)
            if rpf6 is not None:
                return rpf6
    raise RuntimeError("RPF6 parser was not found in the runtime or tools/codered_wsi_explorer.py")


def runtime_apply_patch(runtime_module: Any):
    names = [
        "_codered_apply_patch_folder_to_archive_copy",
        "apply_patch_folder_to_archive_copy",
        "apply_patch_folder",
    ]
    for name in names:
        fn = getattr(runtime_module, name, None)
        if callable(fn):
            return fn
    raise RuntimeError("No copied-archive patch-folder function is exposed by the Code RED runtime")


def archive_find_entry(rpf: Any, path: str):
    find = getattr(rpf, "find", None)
    if callable(find):
        entry = find(path)
        if entry:
            return entry
    normalized = path.replace("\\", "/").lower()
    files = rpf.files() if callable(getattr(rpf, "files", None)) else []
    for entry in files:
        entry_path = getattr(entry, "path", "").replace("\\", "/").lower()
        entry_name = getattr(entry, "name", "").lower()
        if entry_path == normalized or entry_name == Path(path).name.lower():
            return entry
    return None


def extract_text_from_archive(archive: Path, internal_path: str, rpf6_cls: Any) -> ExtractedText:
    try:
        rpf = rpf6_cls(archive)
        entry = archive_find_entry(rpf, internal_path)
        if not entry:
            return ExtractedText(internal_path, False, False, "", 0, "entry not found")
        raw = rpf.slot(entry)
        if isinstance(raw, str):
            raw_bytes = raw.encode("utf-8")
        else:
            raw_bytes = bytes(raw)
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                text = raw_bytes.decode(encoding)
                return ExtractedText(internal_path, True, True, text, len(raw_bytes), "")
            except UnicodeDecodeError:
                continue
        return ExtractedText(internal_path, True, False, "", len(raw_bytes), "text decode failed")
    except Exception as exc:
        return ExtractedText(internal_path, False, False, "", 0, str(exc))


def xml_is_valid(text: str) -> bool:
    try:
        ET.fromstring(text)
        return True
    except Exception:
        return False


def patch_plaympconf_text(text: str, mode: str = "override-auth-failures") -> tuple[str, int, list[str]]:
    """Patch PlayMpConf while keeping the live file as the base."""
    warnings: list[str] = []
    if "NetMachine.TriggerMultiplayerLoad(arg2)" not in text:
        warnings.append("Base PlayMpConf did not contain the stock success TriggerMultiplayerLoad action.")

    if mode not in {"override-auth-failures", "lan-research"}:
        raise ValueError(f"Unsupported mode: {mode}")

    changed = 0
    new_text = text
    for event, old_expr in AUTH_FAILURE_ALERTS.items():
        if event not in new_text:
            warnings.append(f"Transition not found: {event}")
            continue
        if old_expr not in new_text:
            pattern = rf'<transition[^>]+event="{re.escape(event)}"[\s\S]*?NetMachine\.TriggerMultiplayerLoad\(arg2\)[\s\S]*?</transition>'
            if re.search(pattern, new_text):
                continue
            warnings.append(f"Expected action not found for {event}: {old_expr}")
            continue
        new_text = new_text.replace(f'<action expr="{old_expr}"></action>', '<action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>')
        new_text = new_text.replace(f'<action expr="{old_expr}" ></action>', '<action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>')
        new_text = new_text.replace(f'<action expr="{old_expr}"           ></action>', '<action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>')
        changed += 1

    for event, old_expr in AUTH_FAILURE_ALERTS.items():
        transition_pattern = rf'(<transition[^>]+event="{re.escape(event)}"[^>]*>[\s\S]*?</transition>)'
        match = re.search(transition_pattern, new_text)
        if not match:
            continue
        block = match.group(1)
        if "NetMachine.TriggerMultiplayerLoad(arg2)" in block:
            continue
        if old_expr in block:
            replacement_block = re.sub(
                rf'<action\s+expr="{re.escape(old_expr)}"\s*>\s*</action>',
                '<action expr="NetMachine.TriggerMultiplayerLoad(arg2)"></action>',
                block,
            )
            if replacement_block != block:
                new_text = new_text[: match.start(1)] + replacement_block + new_text[match.end(1) :]
                changed += 1

    if mode == "lan-research":
        warnings.append(
            "lan-research mode currently builds the same PlayMpConf auth-failure override because this SCXML file receives Public/Private/LAN through arg2; use copied archive proof before activation."
        )
    return new_text, changed, warnings


def write_text_patch(patch_root: Path, internal_path: str, text: str) -> Path:
    output = patch_root / Path(*[part for part in internal_path.replace("\\", "/").split("/") if part])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="")
    return output


def marker_hits(text: str) -> dict[str, int]:
    return {marker: text.count(marker) for marker in CORE_MP_MARKERS if marker in text}


def build_report_md(result: dict[str, Any]) -> str:
    lines = [
        "# Code RED MP Python Hook Report",
        "",
        f"Generated: `{result.get('generated_at')}`",
        f"Mode: `{result.get('mode')}`",
        f"Source archive: `{result.get('source_archive')}`",
        f"Patch root: `{result.get('patch_root')}`",
        f"Working copy: `{result.get('working_copy')}`",
        "",
        "## Result",
        "",
        f"- OK: `{result.get('ok')}`",
        f"- Changed PlayMpConf auth actions: `{result.get('changed_actions')}`",
        f"- XML valid before: `{result.get('xml_valid_before')}`",
        f"- XML valid after: `{result.get('xml_valid_after')}`",
        f"- Runtime applied: `{result.get('applied')}`",
        f"- Runtime blocked: `{result.get('blocked')}`",
        "",
        "## MP Marker Hits",
        "",
    ]
    hits = result.get("marker_hits") or {}
    if hits:
        for path, path_hits in hits.items():
            lines.append(f"### `{path}`")
            for marker, count in sorted(path_hits.items()):
                lines.append(f"- `{marker}`: {count}")
            lines.append("")
    else:
        lines.append("No marker hits were collected.")
        lines.append("")
    warnings = result.get("warnings") or []
    lines.extend(["## Warnings", ""])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- The source `content.rpf` was not modified by `build`.",
            "- The override starts from the current-version PlayMpConf file and changes only the auth-failure route actions.",
            "- `activate` is a separate explicit command that creates a timestamped backup before replacing a target archive.",
        ]
    )
    return "\n".join(lines)


def normalize_patch_result(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {"raw_result": repr(payload)}


def build_hook(args: argparse.Namespace) -> BuildResult:
    repo_root = find_repo_root(Path(args.repo_root or Path.cwd()))
    companion_root = Path(args.companion_root).resolve() if args.companion_root else repo_root / "related_apps" / "Code_RED_MP_Companion_v19"
    runtime, runtime_path = load_runtime(repo_root, companion_root)
    rpf6_cls = load_rpf6(repo_root, runtime)
    apply_patch = runtime_apply_patch(runtime)

    source_archive = Path(args.content).resolve()
    if not source_archive.exists():
        raise FileNotFoundError(f"content.rpf not found: {source_archive}")

    stamp = now_stamp()
    output_root = Path(args.outdir).resolve() if args.outdir else companion_root / "hotswap" / "staged" / "mp_python_hook" / stamp
    patch_root = output_root / "patches" / "content.rpf"
    reports_root = output_root / "reports"
    reports_root.mkdir(parents=True, exist_ok=True)
    patch_root.mkdir(parents=True, exist_ok=True)

    extracted = {path: extract_text_from_archive(source_archive, path, rpf6_cls) for path in [PLAYMPCONF_PATH, NETWORKING_PATH, TASKMACHINE_PATH, LOBBY_PATH, HUDONLINE_PATH]}
    play = extracted[PLAYMPCONF_PATH]
    if not play.found or not play.decode_ok:
        raise RuntimeError(f"Could not extract PlayMpConf from archive: {play.error}")

    xml_before = xml_is_valid(play.text)
    patched_text, changed, warnings = patch_plaympconf_text(play.text, mode=args.mode)
    xml_after = xml_is_valid(patched_text)
    if not xml_after:
        warnings.append("Patched PlayMpConf did not parse as XML. Runtime patching blocked.")

    diff_text = "\n".join(
        difflib.unified_diff(
            play.text.splitlines(),
            patched_text.splitlines(),
            fromfile="content.rpf/plaympconf.sc.xml",
            tofile="patched/plaympconf.sc.xml",
            lineterm="",
        )
    )
    write_text_patch(patch_root, PLAYMPCONF_PATH, patched_text)
    (reports_root / "plaympconf_override.diff").write_text(diff_text, encoding="utf-8")

    marker_report: dict[str, dict[str, int]] = {}
    for path, item in extracted.items():
        if item.found and item.decode_ok:
            marker_report[path] = marker_hits(item.text)

    patch_result: dict[str, Any] = {}
    working_copy = output_root / f"content__mp_python_hook_{stamp}.rpf"
    applied = 0
    blocked = 1
    if xml_after:
        try:
            try:
                raw_patch_result = apply_patch(source_archive, patch_root, output_archive=working_copy)
            except TypeError:
                raw_patch_result = apply_patch(source_archive, patch_root, working_copy)
            patch_result = normalize_patch_result(raw_patch_result)
            applied = int(patch_result.get("applied") or patch_result.get("patched") or 0)
            blocked = int(patch_result.get("blocked") or 0)
            if not working_copy.exists():
                candidate = patch_result.get("working_copy") or patch_result.get("output") or patch_result.get("archive_copy")
                if candidate:
                    working_copy = Path(candidate)
        except Exception as exc:
            warnings.append(f"Runtime copied-archive patch failed: {exc}")
            patch_result = {"error": str(exc), "runtime_path": str(runtime_path)}

    ok = bool(xml_before and xml_after and changed > 0 and blocked == 0 and (applied > 0 or working_copy.exists()))
    result_dict: dict[str, Any] = {
        "ok": ok,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "repo_root": str(repo_root),
        "companion_root": str(companion_root),
        "runtime_path": str(runtime_path),
        "source_archive": str(source_archive),
        "patch_root": str(patch_root),
        "working_copy": str(working_copy),
        "changed_actions": changed,
        "xml_valid_before": xml_before,
        "xml_valid_after": xml_after,
        "applied": applied,
        "blocked": blocked,
        "patch_result": patch_result,
        "extracted": {path: asdict(item) | {"text": f"<omitted {len(item.text)} chars>"} for path, item in extracted.items()},
        "marker_hits": marker_report,
        "warnings": warnings,
    }
    report_json = reports_root / "mp_python_hook_report.json"
    report_md = reports_root / "mp_python_hook_report.md"
    state_path = companion_root / "config" / STATE_FILE
    write_json(report_json, result_dict)
    report_md.write_text(build_report_md(result_dict), encoding="utf-8")
    write_json(state_path, result_dict)

    return BuildResult(
        ok=ok,
        mode=args.mode,
        source_archive=str(source_archive),
        working_copy=str(working_copy),
        patch_root=str(patch_root),
        report_json=str(report_json),
        report_md=str(report_md),
        state_path=str(state_path),
        changed_actions=changed,
        xml_valid_before=xml_before,
        xml_valid_after=xml_after,
        applied=applied,
        blocked=blocked,
        warnings=warnings,
    )


def activate_hook(args: argparse.Namespace) -> dict[str, Any]:
    target = Path(args.target).resolve()
    patched = Path(args.patched).resolve() if args.patched else None
    state_path = Path(args.state).resolve() if args.state else Path.cwd() / "related_apps" / "Code_RED_MP_Companion_v19" / "config" / STATE_FILE
    state = read_json(state_path)
    if patched is None:
        patched_text = state.get("working_copy")
        if patched_text:
            patched = Path(patched_text).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Target archive not found: {target}")
    if patched is None or not patched.exists():
        raise FileNotFoundError("Patched working copy not found. Run build first or pass --patched.")
    backup_dir = Path(args.backup_dir).resolve() if args.backup_dir else target.parent / "Code_RED_Backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{target.stem}.before_mp_python_hook_{now_stamp()}{target.suffix}"
    shutil.copy2(target, backup)
    shutil.copy2(patched, target)
    result = {
        "ok": True,
        "activated_at": datetime.now().isoformat(timespec="seconds"),
        "target": str(target),
        "patched": str(patched),
        "backup": str(backup),
    }
    if state_path:
        state.update({"activation": result})
        write_json(state_path, state)
    print(json.dumps(result, indent=2))
    return result


def restore_hook(args: argparse.Namespace) -> dict[str, Any]:
    target = Path(args.target).resolve()
    backup = Path(args.backup).resolve()
    if not backup.exists():
        raise FileNotFoundError(f"Backup not found: {backup}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, target)
    result = {
        "ok": True,
        "restored_at": datetime.now().isoformat(timespec="seconds"),
        "target": str(target),
        "backup": str(backup),
    }
    print(json.dumps(result, indent=2))
    return result


def print_build_result(result: BuildResult) -> None:
    print(json.dumps(asdict(result), indent=2))
    print(f"Report: {result.report_md}")
    print(f"Patched copy: {result.working_copy}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/activate Code RED MP Python hook overrides")
    sub = parser.add_subparsers(dest="command", required=True)

    q = sub.add_parser("build", help="Build a copied content.rpf with the PlayMpConf MP override")
    q.add_argument("--content", required=True, help="Path to source content.rpf")
    q.add_argument("--repo-root", default="", help="Code RED repository root. Defaults to current tree search.")
    q.add_argument("--companion-root", default="", help="Code_RED_MP_Companion_v19 root. Defaults to related_apps path.")
    q.add_argument("--outdir", default="", help="Output folder for patch root, reports, and copied archive.")
    q.add_argument("--mode", choices=["override-auth-failures", "lan-research"], default="override-auth-failures")
    q.set_defaults(fn=lambda ns: print_build_result(build_hook(ns)))

    q = sub.add_parser("activate", help="Explicitly replace a target archive with the built copy after backing it up")
    q.add_argument("--target", required=True, help="Live target content.rpf to replace")
    q.add_argument("--patched", default="", help="Patched copied archive. Defaults to state file working_copy.")
    q.add_argument("--state", default="", help="mp_python_hook_state.json path")
    q.add_argument("--backup-dir", default="", help="Backup output directory")
    q.set_defaults(fn=activate_hook)

    q = sub.add_parser("restore", help="Restore a target archive from a backup")
    q.add_argument("--target", required=True)
    q.add_argument("--backup", required=True)
    q.set_defaults(fn=restore_hook)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
