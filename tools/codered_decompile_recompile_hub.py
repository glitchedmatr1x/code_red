#!/usr/bin/env python3
"""Code RED decompile/recompile capability hub.

Creates one honest index for archive extraction, copied-archive patching,
script read/decode, and SC-CL compile paths.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_JSON = ROOT / "logs" / "CodeRED_Decompile_Recompile_Hub_Report.json"
LOG_MD = ROOT / "logs" / "CodeRED_Decompile_Recompile_Hub_Report.md"
GUIDE = ROOT / "docs" / "CodeRED_DECOMPILE_RECOMPILE_GUIDE.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def run_quiet(command: list[str], timeout: int = 120) -> dict:
    try:
        proc = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "command": command,
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout": "\n".join(proc.stdout.splitlines()[:80]),
            "stderr": "\n".join(proc.stderr.splitlines()[:80]),
        }
    except Exception as exc:
        return {"command": command, "returncode": None, "ok": False, "stdout": "", "stderr": str(exc)}


def detect_sccl() -> dict:
    candidates = [
        ROOT / "script_compiling" / "sccl" / "output" / "SC-CL.exe",
        ROOT / "SC-CL-master" / "bin" / "SC-CL.exe",
        ROOT / "resources" / "SC-CL_DROP_HERE" / "SC-CL.exe",
    ]
    found = [str(path) for path in candidates if path.exists()]
    proof_artifacts = [
        ROOT / "script_compiling" / "sccl" / "output" / "vehicle_menu_probe" / "vehicle_menu_probe.xsc",
        ROOT / "script_compiling" / "sccl" / "output" / "camp_car_probe_sco" / "camp_car_probe.sco",
        ROOT / "script_compiling" / "sccl" / "output" / "camp_car_probe_wsc" / "camp_car_probe.wsc",
    ]
    return {
        "available": bool(found),
        "candidates": found,
        "proof_artifacts": [str(path) for path in proof_artifacts if path.exists()],
        "proven_compile_log": str(ROOT / "logs" / "MILESTONE_SCCL_Compile_Lane_Proven_2026-05-04.md") if (ROOT / "logs" / "MILESTONE_SCCL_Compile_Lane_Proven_2026-05-04.md").exists() else "",
    }


def detect_magic_rdr_name_sources() -> dict:
    candidates = [
        ROOT / "research" / "menu resources" / "ImportedFileNames.txt",
        ROOT.parent / "game" / "BACKUP BEFORE MODDING" / "rdr1" / "mods" / "Magic-RDR-main" / "ImportedFileNames.txt",
        ROOT.parent / "game" / "BACKUP BEFORE MODDING" / "rdr1" / "mods" / "Magic-RDR-main" / "Settings" / "ImportedFileNames.txt",
        ROOT.parent / "game" / "BACKUP BEFORE MODDING" / "rdr1" / "mods" / "Magic-RDR-main.zip",
    ]
    proof_log = ROOT / "logs" / "IMPORTANT_CodeRED_Magic_RDR_Parity_Extraction_2026-05-06.md"
    return {
        "available": any(path.exists() for path in candidates),
        "candidates": [str(path) for path in candidates if path.exists()],
        "proof_log": str(proof_log) if proof_log.exists() else "",
    }


def build_report(validate: bool) -> dict:
    lanes = {
        "magic_rdr_name_recovery": {
            "state": "ready" if detect_magic_rdr_name_sources()["available"] else "missing",
            "tool": "python_workbench.py + tools/codered_magic_rdr_bridge.py",
            "proof": "Magic-RDR imported filename lists restore RPF6 hash-name resolution for inventory/extract",
        },
        "rpf_inventory_extract": {
            "state": "ready" if exists("tools/codered_rpf_utils.py") and exists("python_workbench.py") else "missing",
            "tool": "tools/codered_rpf_utils.py",
            "proof": "RPF6 parse + extract through python_workbench backend",
        },
        "rpf_patch_copied_archive": {
            "state": "ready" if exists("tools/codered_rpf_utils_patch.py") and exists("python_workbench.py") else "missing",
            "tool": "tools/codered_rpf_utils_patch.py",
            "proof": "Patch-folder apply writes a copied archive, not the source archive",
        },
        "file_io_full_decode": {
            "state": "ready" if exists("tools/codered_file_io_validation.py") else "missing",
            "tool": "tools/codered_file_io_validation.py",
            "proof": "Full-file and RPF sample extraction validation",
        },
        "script_read_decode": {
            "state": "ready" if exists("tools/codered_script_pipeline.py") and exists("tools/codered_script_workshop_decode.py") else "missing",
            "tool": "tools/codered_script_pipeline.py",
            "proof": "Source/text decode plus compiled-script binary string/hash/native mining",
        },
        "script_source_compile": {
            "state": "ready" if detect_sccl()["available"] else "missing",
            "tool": "script_compiling/sccl/compile_vehicle_menu_probe_windows.bat",
            "proof": "SC-CL compile lane has produced real .xsc/.sco/.wsc proof artifacts where present",
        },
        "wsc_source_edit_compile_pack": {
            "state": "ready" if exists("tools/codered_wsc_edit_workflow.py") and detect_sccl()["available"] and exists("tools/codered_content_convert_overlay_builder.py") else "missing",
            "tool": "tools/codered_wsc_edit_workflow.py",
            "proof": "Creates a safe edit workspace, compiles source to WSC/RSC85 through SC-CL, and packs only a copied RPF output under build/",
        },
        "compiled_script_source_decompile": {
            "state": "blocked",
            "tool": "",
            "proof": "No proven WSC/CSC/XSC/SCO bytecode-to-source decompiler was found; keep binary pseudo-decompile/export honest",
        },
    }
    validation = {}
    if validate:
        validation["file_io"] = run_quiet([sys.executable, "tools/codered_file_io_validation.py", "--root", ".", "--sample-limit", "3"], timeout=240)
        validation["archive_lane"] = run_quiet([sys.executable, "tools/codered_archive_lane_validation.py", "--root", ".", "--sample-limit", "4"], timeout=240)
    report = {
        "generated_utc": utc_now(),
        "root": str(ROOT),
        "lanes": lanes,
        "sccl": detect_sccl(),
        "magic_rdr_name_sources": detect_magic_rdr_name_sources(),
        "validation": validation,
        "status": "READY_WITH_BLOCKED_SOURCE_DECOMPILER" if all(lane["state"] != "missing" for lane in lanes.values()) else "NEEDS_ATTENTION",
    }
    return report


def write_outputs(report: dict) -> None:
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    GUIDE.parent.mkdir(parents=True, exist_ok=True)
    LOG_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lane_lines = []
    for name, lane in report["lanes"].items():
        lane_lines.append(f"| `{name}` | `{lane['state']}` | `{lane['tool']}` | {lane['proof']} |")
    md = "# Code RED Decompile / Recompile Hub\n\n"
    md += f"Generated UTC: `{report['generated_utc']}`\n\n"
    md += f"Status: **{report['status']}**\n\n"
    md += "## Capability Matrix\n\n| Lane | State | Tool | Proof / Boundary |\n|---|---|---|---|\n"
    md += "\n".join(lane_lines)
    md += "\n\n## Important Boundary\n\n"
    md += "Code RED can extract/decode RPF entries, patch supported entries into copied archives, and compile source through SC-CL proof lanes. It still does not have a proven compiled-script bytecode-to-source decompiler, so `.wsc/.csc/.xsc/.sco` binary decompile remains readable/pseudo-decompile only until a real decompiler is found or built.\n"
    md += "\n## Magic-RDR Parity / Name Recovery\n\n"
    md += "Code RED now uses local Magic-RDR `ImportedFileNames.txt` resources for RPF6 hash-name recovery. Validated result: live `content.rpf` resolved `1636/1636` entries and extracted `1320/1320` files through the internal RPF6 extractor.\n\n"
    md += "Primary proof log: `logs\\IMPORTANT_CodeRED_Magic_RDR_Parity_Extraction_2026-05-06.md`\n\n"
    md += "Important distinction: the live PC `content.rpf` extracted here contains `release64` SP/system/gringo content, while the older extracted root reference under `game\\BACKUP BEFORE MODDING\\rdr1\\mods\\root` contains the `content\\release\\multiplayer` `.csc` branch. Keep those as correlated evidence, not automatically identical archive versions.\n"
    md += "\n## Main Commands\n\n"
    md += "```bat\n"
    md += "Run_CodeRED_RPF_Edit_Lab.bat\n"
    md += "Run_CodeRED_Decompile_Recompile_Hub.bat --validate\n"
    md += "Run_CodeRED_WSC_Edit_Workflow.bat --help\n"
    md += "python tools\\codered_wsc_edit_workflow.py decompile --name codered_wait_probe --archive-path root/content/release64/init/initpopulation.wsc\n"
    md += "python tools\\codered_wsc_edit_workflow.py recompile --workspace build\\wsc_edit\\codered_wait_probe --clean\n"
    md += "python tools\\codered_wsc_edit_workflow.py pack --workspace build\\wsc_edit\\codered_wait_probe --write\n"
    md += "script_compiling\\sccl\\compile_vehicle_menu_probe_windows.bat\n"
    md += "```\n"
    LOG_MD.write_text(md, encoding="utf-8")
    GUIDE.write_text(md, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED decompile/recompile capability hub")
    parser.add_argument("--validate", action="store_true", help="Run archive/file validation proof commands.")
    args = parser.parse_args(argv)
    report = build_report(args.validate)
    write_outputs(report)
    print(json.dumps({"status": report["status"], "report": str(LOG_MD), "guide": str(GUIDE)}, indent=2))
    return 0 if report["status"] != "NEEDS_ATTENTION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
