#!/usr/bin/env python3
"""
Code RED AI Menu install/load doctor.

Read-only local check for the installed ScriptHookRDR AI Menu.
It checks whether the built .asi was copied to the selected game root, whether
support files are present, whether an ASI/ScriptHook loader appears present,
and whether CodeRED_AI_Menu.log exists.

Run from repo root:
  py -3 tools\codered_ai_menu_install_doctor.py --game-root "%RDR_GAME_DIR%"
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_ASI_SHA1 = "A68CCB9F518BF85B70A52D41C2A6B6CE58FAE484"


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_tail(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return text[-max_chars:]


def file_info(path: Path) -> dict:
    row = {"path": str(path), "exists": path.exists(), "length": None, "sha1": None}
    if path.exists() and path.is_file():
        row["length"] = path.stat().st_size
        row["sha1"] = sha1(path)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-root", required=True, help="Folder containing the game executable")
    parser.add_argument("--repo-root", default=".", help="Code_RED repo root")
    parser.add_argument("--out", default="logs/ai_menu_install_doctor", help="Output prefix")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    game_root = Path(args.game_root).resolve()
    if not game_root.exists():
        raise SystemExit(f"Missing game root: {game_root}")

    installed_asi = game_root / "CodeRED_AI_Menu.asi"
    built_asi = repo_root / "related_apps" / "Code_RED_ScriptHookRDR_AI_Menu" / "build" / "CodeRED_AI_Menu.asi"
    ini = game_root / "CodeRED_AI_Menu.ini"
    log = game_root / "CodeRED_AI_Menu.log"
    data_dir = game_root / "data" / "codered"
    roster = data_dir / "npc_roster.txt"
    actor_map = data_dir / "actor_enum_map.csv"
    actions = data_dir / "ai_behavior_actions.csv"
    scratch = game_root / "scratch"

    exe_files = sorted(game_root.glob("*.exe"))
    asi_files = sorted(game_root.glob("*.asi"))
    dll_files = {p.name.lower(): p for p in game_root.glob("*.dll")}

    loader_candidates = [
        "dinput8.dll", "ScriptHookRDR.dll", "ScriptHook.dll", "version.dll", "dsound.dll", "xinput1_3.dll"
    ]
    loader_status = {name: file_info(dll_files[name]) if name in dll_files else {"path": str(game_root / name), "exists": False, "length": None, "sha1": None} for name in loader_candidates}

    log_tail = read_tail(log)
    missing_export_lines = [line for line in log_tail.splitlines() if "Missing ScriptHookRDR export" in line]
    status_lines = [line for line in log_tail.splitlines() if "CodeRED" in line or "Config loaded" in line or "Actor enum map" in line]

    installed_info = file_info(installed_asi)
    built_info = file_info(built_asi)
    installed_matches_build = installed_info["exists"] and built_info["exists"] and installed_info["sha1"] == built_info["sha1"]
    installed_matches_expected = installed_info["sha1"] == EXPECTED_ASI_SHA1

    verdict = []
    if not exe_files:
        verdict.append("No .exe found directly in the supplied game root. The install path may be wrong.")
    else:
        verdict.append(f"Found game-root exe candidate(s): {', '.join(p.name for p in exe_files[:5])}")

    if not installed_asi.exists():
        verdict.append("CodeRED_AI_Menu.asi is not installed in the supplied game root.")
    elif installed_matches_build:
        verdict.append("Installed CodeRED_AI_Menu.asi matches the local built ASI.")
    elif installed_matches_expected:
        verdict.append("Installed CodeRED_AI_Menu.asi matches the expected successful-build hash.")
    else:
        verdict.append("Installed CodeRED_AI_Menu.asi exists but does not match the latest known build hash.")

    if not any(loader_status[name]["exists"] for name in loader_candidates):
        verdict.append("No obvious ASI/ScriptHook loader DLL found beside the game executable.")
    else:
        verdict.append("At least one ASI/ScriptHook loader DLL candidate exists beside the game executable.")

    if not ini.exists():
        verdict.append("CodeRED_AI_Menu.ini is missing beside the game executable.")
    if not roster.exists() or not actor_map.exists() or not actions.exists():
        verdict.append("One or more data/codered menu data files are missing in the game root.")
    else:
        verdict.append("data/codered menu data files are present in the game root.")

    if not log.exists():
        verdict.append("No CodeRED_AI_Menu.log found. If the game was launched after install, the ASI likely did not load.")
    else:
        verdict.append("CodeRED_AI_Menu.log exists, so the ASI probably loaded at least far enough to write logs.")
        if missing_export_lines:
            verdict.append("Log reports missing ScriptHookRDR exports; native/menu bridge may not be compatible with the installed ScriptHookRDR.")

    report = {
        "repo_root": str(repo_root),
        "game_root": str(game_root),
        "exe_files": [str(p) for p in exe_files],
        "asi_files": [str(p) for p in asi_files],
        "built_asi": built_info,
        "installed_asi": installed_info,
        "installed_matches_build": installed_matches_build,
        "installed_matches_expected": installed_matches_expected,
        "ini": file_info(ini),
        "data_files": {
            "roster": file_info(roster),
            "actor_enum_map": file_info(actor_map),
            "actions": file_info(actions),
            "scratch_dir_exists": scratch.exists(),
        },
        "loader_status": loader_status,
        "log": file_info(log),
        "log_tail": log_tail,
        "missing_export_lines": missing_export_lines,
        "status_lines": status_lines[-50:],
        "verdict": verdict,
        "boundary": "Read-only install/load diagnosis. No files modified.",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_path = out.with_suffix(".json")
    md_path = out.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Code RED AI Menu Install Doctor",
        "",
        f"Game root: `{game_root}`",
        "",
        "Boundary: read-only install/load diagnosis. No files modified.",
        "",
        "## Verdict",
        "",
    ]
    for item in verdict:
        lines.append(f"- {item}")
    lines.extend(["", "## Installed ASI", ""])
    lines.append(f"- exists: `{installed_info['exists']}`")
    lines.append(f"- length: `{installed_info['length']}`")
    lines.append(f"- sha1: `{installed_info['sha1']}`")
    lines.append(f"- matches local build: `{installed_matches_build}`")
    lines.append(f"- matches expected hash: `{installed_matches_expected}`")
    lines.extend(["", "## Loader DLL candidates", ""])
    for name, row in loader_status.items():
        lines.append(f"- `{name}` exists=`{row['exists']}` length=`{row['length']}`")
    lines.extend(["", "## Data files", ""])
    for key, row in report["data_files"].items():
        if isinstance(row, dict):
            lines.append(f"- `{key}` exists=`{row['exists']}` length=`{row['length']}`")
        else:
            lines.append(f"- `{key}`: `{row}`")
    lines.extend(["", "## Log", ""])
    lines.append(f"- exists: `{log.exists()}`")
    if missing_export_lines:
        lines.append("### Missing exports")
        for line in missing_export_lines[:30]:
            lines.append(f"- `{line}`")
    if log_tail:
        lines.append("### Tail")
        lines.append("```text")
        lines.append(log_tail[-3000:])
        lines.append("```")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("# Code RED AI Menu Install Doctor")
    print(f"Game root: {game_root}")
    print(f"JSON: {json_path}")
    print(f"MD: {md_path}")
    for item in verdict:
        print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
