"""Tiny Code RED WSC authoring bridge for Pass 1.

SC-CL can currently emit RDR_SCO reliably.  This tool compiles tiny source
templates as SCO, then wraps that decoded SCO payload into a known-good PC
RSC85 WSC container using codered_wsc.resource's AES/Zstandard repacker.  The
result is a real Code RED-decodable WSC resource candidate: inspect and repack
must round-trip before it is reported as valid.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codered_wsc.resource import KeyOptions, ResourceError, open_script, repack_script

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "script_compiling" / "sccl"
PROJECTS = LANE / "projects"
COMPILE_SCRIPT = LANE / "compile_sccl_project_windows.ps1"
DEFAULT_BUILD = ROOT / "build" / "wsc_authoring_pass1"
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_RDR_EXE = ROOT.parent / "RDR.exe"
DEFAULT_TEMPLATE_CANDIDATES = [
    ROOT / "game" / "content_extracted" / "release64" / "scripting" / "designerdefined" / "short_update_thread.wsc",
    ROOT / "logs" / "content_rpf_full_extract_after_magic_names" / "content" / "release64" / "scripting" / "designerdefined" / "short_update_thread.wsc",
]


HELLO_SOURCE = """/*
   Code RED WSC authoring pass 1: hello bootstrap.
   Local/offline proof script. No network spoofing and no public matchmaking.
*/

#include "../include/types.h"
#include "../include/intrinsics.h"
#include "../include/natives.h"
#include "../include/RDR/natives32.h"

void main(void)
{
    while (true)
    {
        WAIT(0);
    }
}
"""


MP_BOOTSTRAP_SOURCE = """/*
   Code RED WSC authoring pass 1: local MP bootstrap.
   It only attempts to launch local restored multiplayer scripts.
   It does not spoof public servers, auth, or matchmaking.
*/

#include "../include/types.h"
#include "../include/intrinsics.h"
#include "../include/natives.h"
#include "../include/RDR/natives32.h"

void main(void)
{
    WAIT(1000);
    LAUNCH_NEW_SCRIPT("$/content/multiplayer/PR_Multiplayer", 0);
    LAUNCH_NEW_SCRIPT("$/content/multiplayer/multiplayer_system_thread", 0);

    while (true)
    {
        WAIT(0);
    }
}
"""


@dataclass
class BuildSpec:
    project_name: str
    output_name: str
    source: str
    purpose: str


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def sha1_file(path: Path) -> str:
    return sha1_bytes(path.read_bytes())


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
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def resolve_template(explicit: str) -> Path:
    candidates = [Path(explicit)] if explicit else []
    candidates.extend(DEFAULT_TEMPLATE_CANDIDATES)
    for path in candidates:
        if path.exists():
            return path
    searched = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(f"No PC WSC template found. Searched:\n{searched}")


def ensure_project(spec: BuildSpec, build_dir: Path) -> Path:
    project = PROJECTS / spec.project_name
    if project.exists():
        shutil.rmtree(project)
    src_dir = project / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "main.c").write_text(spec.source, encoding="utf-8")
    source_archive = build_dir / "source" / spec.project_name
    source_archive.mkdir(parents=True, exist_ok=True)
    (source_archive / "main.c").write_text(spec.source, encoding="utf-8")
    lane_include = LANE / "include"
    project_include = project / "include"
    if lane_include.exists():
        shutil.copytree(lane_include, project_include)
    return project


def run_sccl_compile(spec: BuildSpec) -> dict[str, Any]:
    if not COMPILE_SCRIPT.exists():
        raise FileNotFoundError(f"Missing SC-CL compile helper: {COMPILE_SCRIPT}")
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(COMPILE_SCRIPT),
        "-RepoRoot",
        str(ROOT),
        "-ProjectName",
        spec.project_name,
        "-OutputName",
        spec.output_name,
        "-Target",
        "RDR_SCO",
        "-Platform",
        "X360",
    ]
    proc = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=180)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout.splitlines(),
        "stderr": proc.stderr.splitlines(),
    }


def newest_sco(project_name: str, output_name: str) -> Path:
    out_root = LANE / "output" / project_name
    exact = out_root / f"{output_name}.sco"
    if exact.exists():
        return exact
    matches = sorted(out_root.rglob("*.sco"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"No SCO artifact found for {project_name}/{output_name} under {out_root}")
    return matches[0]


def wrap_sco_as_wsc(sco: Path, output_wsc: Path, template_wsc: Path, rdr_exe: Path) -> dict[str, Any]:
    resource = open_script(template_wsc, KeyOptions(rdr_exe=str(rdr_exe)))
    decoded = sco.read_bytes()
    payload, repack_report = repack_script(resource, decoded, allow_growth=True)
    output_wsc.parent.mkdir(parents=True, exist_ok=True)
    output_wsc.write_bytes(payload)

    reopened = open_script(output_wsc, KeyOptions(rdr_exe=str(rdr_exe)))
    _, second_report = repack_script(reopened, reopened.decoded, allow_growth=True)
    return {
        "template_wsc": str(template_wsc),
        "sco": str(sco),
        "output_wsc": str(output_wsc),
        "sco_size": sco.stat().st_size,
        "output_size": output_wsc.stat().st_size,
        "sco_sha1": sha1_file(sco),
        "output_sha1": sha1_file(output_wsc),
        "decoded_size": len(reopened.decoded),
        "decoded_matches_sco": reopened.decoded == decoded,
        "inspect_reopen_ok": reopened.decoded == decoded and not reopened.decode_error,
        "repack_reopen_ok": bool(second_report.get("validate_ok")),
        "wrap_fit_mode": repack_report.get("fit_mode"),
        "wrap_codec": repack_report.get("codec"),
        "wrap_validate_ok": repack_report.get("validate_ok"),
        "repack_validate_ok": second_report.get("validate_ok"),
        "runtime_status": "not_game_runtime_proven",
        "import_status": "standalone_pc_rsc85_import_candidate",
    }


def cleanup_sccl_scratch(spec: BuildSpec) -> None:
    for path in (PROJECTS / spec.project_name, LANE / "output" / spec.project_name):
        if path.exists():
            shutil.rmtree(path)
    for path in (
        LANE / "output" / f"{spec.project_name}_compile_report.json",
        LANE / "output" / f"{spec.project_name}_compile_report.md",
    ):
        if path.exists():
            path.unlink()


def build_one(spec: BuildSpec, build_dir: Path, template_wsc: Path, rdr_exe: Path, keep_sccl_workspace: bool) -> dict[str, Any]:
    ensure_project(spec, build_dir)
    compile_log = run_sccl_compile(spec)
    row: dict[str, Any] = {
        "name": spec.output_name,
        "project_name": spec.project_name,
        "purpose": spec.purpose,
        "compile_exit_code": compile_log["returncode"],
        "status": "compile_failed",
    }
    log_dir = build_dir / "compile_logs"
    write_json(log_dir / f"{spec.output_name}_compile_log.json", compile_log)
    if compile_log["returncode"] != 0:
        row["compile_log"] = str(log_dir / f"{spec.output_name}_compile_log.json")
        if not keep_sccl_workspace:
            cleanup_sccl_scratch(spec)
        return row

    sco = newest_sco(spec.project_name, spec.output_name)
    copied_sco = build_dir / f"{spec.output_name}.sco"
    shutil.copy2(sco, copied_sco)
    output_wsc = build_dir / f"{spec.output_name}.wsc"
    try:
        wrap_report = wrap_sco_as_wsc(copied_sco, output_wsc, template_wsc, rdr_exe)
        row.update(wrap_report)
        row["status"] = "generated_wsc_validated" if row["inspect_reopen_ok"] and row["repack_reopen_ok"] else "generated_wsc_validation_failed"
    except (ResourceError, FileNotFoundError, ValueError) as exc:
        row["status"] = "wrap_failed"
        row["error"] = str(exc)
    finally:
        if not keep_sccl_workspace:
            cleanup_sccl_scratch(spec)
    return row


def write_pass_report(build_dir: Path, reports_dir: Path, rows: list[dict[str, Any]], template_wsc: Path, rdr_exe: Path) -> None:
    write_csv(reports_dir / "generated_wsc_validation.csv", rows)
    ok = [row for row in rows if row.get("status") == "generated_wsc_validated"]
    lines = [
        "# WSC Authoring Pass 1",
        "",
        "This pass builds minimal local/offline script resources only. It does not spoof public servers, patch matchmaking, or overwrite game archives.",
        "",
        f"- Template PC WSC: `{template_wsc}`",
        f"- RDR.exe for AES key: `{rdr_exe}`",
        f"- Build folder: `{build_dir}`",
        f"- Validated WSC outputs: `{len(ok)}/{len(rows)}`",
        "",
        "## Outputs",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['name']}",
                f"- status: `{row.get('status', '')}`",
                f"- output: `{row.get('output_wsc', '')}`",
                f"- decoded matches SCO: `{row.get('decoded_matches_sco', '')}`",
                f"- inspect reopen ok: `{row.get('inspect_reopen_ok', '')}`",
                f"- repack reopen ok: `{row.get('repack_reopen_ok', '')}`",
                f"- runtime status: `{row.get('runtime_status', '')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "These WSC files are valid Code RED-decodable PC RSC85 resources containing SC-CL RDR_SCO decoded payloads. "
            "That proves authoring, wrapping, inspect, and repack. It does not prove the game runtime will execute the SCO payload from a WSC path until imported and tested.",
        ]
    )
    (reports_dir / "wsc_authoring_pass1_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build minimal Code RED PC RSC85 WSC bootstrap resources.")
    parser.add_argument("--build-dir", default=str(DEFAULT_BUILD))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS))
    parser.add_argument("--template-wsc", default="")
    parser.add_argument("--rdr-exe", default=str(DEFAULT_RDR_EXE))
    parser.add_argument("--keep-sccl-workspace", action="store_true", help="Keep generated SC-CL project/output scratch folders for debugging.")
    args = parser.parse_args(argv)

    build_dir = Path(args.build_dir)
    reports_dir = Path(args.reports_dir)
    template_wsc = resolve_template(args.template_wsc)
    rdr_exe = Path(args.rdr_exe)
    if not rdr_exe.exists():
        raise FileNotFoundError(f"RDR.exe not found for AES key extraction: {rdr_exe}")

    specs = [
        BuildSpec("codered_author_hello_bootstrap", "hello_bootstrap", HELLO_SOURCE, "minimal WAIT loop bootstrap"),
        BuildSpec(
            "codered_author_mp_bootstrap_minimal",
            "codered_mp_bootstrap_minimal",
            MP_BOOTSTRAP_SOURCE,
            "attempt local restored MP launcher scripts",
        ),
    ]
    build_dir.mkdir(parents=True, exist_ok=True)
    rows = [build_one(spec, build_dir, template_wsc, rdr_exe, args.keep_sccl_workspace) for spec in specs]
    write_pass_report(build_dir, reports_dir, rows, template_wsc, rdr_exe)
    status = "pass" if all(row.get("status") == "generated_wsc_validated" for row in rows) else "partial"
    print(json.dumps({"status": status, "build_dir": str(build_dir), "reports_dir": str(reports_dir), "rows": rows}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
