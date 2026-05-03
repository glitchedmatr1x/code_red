#!/usr/bin/env python3
"""Timeout-safe SC-CL compiled menu probe.

This probe now prefers the real SC-CL project layout:

    resources/SC-CL_bitbucket_source/bin/projects/CodeREDMenu/CodeREDMenu.c
    resources/SC-CL_bitbucket_source/bin/include

The old compile-lab source remains useful for static validation, but real SC-CL
compile proof must use the Bitbucket include kit because native wrappers require
_native32(hash) implementations.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.2.0-safe-sccl-project-compile-probe"
STATUS_DLL_NOT_FOUND = 0xC0000135
KIT = Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1")
LAB = Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1")
DROP = Path("resources/SC-CL_DROP_HERE")
SC_CL_SOURCE = Path("resources/SC-CL_bitbucket_source")
STAGE_TOOL = Path("tools/codered_sccl_stage_menu_project.py")
REPORT_JSON = Path("logs/CodeRED_SCCL_Safe_Compile_Probe_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Safe_Compile_Probe_Report.md")
OUTPUT_LOG = Path("logs/CodeRED_SCCL_Safe_Compile_Probe_Output.txt")


@dataclass
class CommandResult:
    name: str
    command: list[str]
    exit_code: int | None
    timed_out: bool = False
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass
class ProbeReport:
    version: str
    generated_utc: str
    root: str
    ok: bool
    sccl_exe: str | None
    source: str
    output_dir: str
    project: str
    include_dir: str | None = None
    commands: list[CommandResult] = field(default_factory=list)
    output_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def root_from_arg(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else Path(__file__).resolve().parents[1]


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def tail(text: str, limit: int = 8000) -> str:
    return text if len(text) <= limit else text[-limit:]


def status_hex(code: int | None) -> str:
    if code is None:
        return "None"
    return f"0x{code & 0xFFFFFFFF:08X}"


def is_dll_launch_failure(code: int | None) -> bool:
    return code is not None and (code & 0xFFFFFFFF) == STATUS_DLL_NOT_FOUND


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="ignore")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def find_sccl(root: Path, explicit: str | None = None) -> Path | None:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("SCCL_EXE")
    if env:
        candidates.append(Path(env))
    candidates.extend([
        root / KIT / "SC-CL.exe",
        root / DROP / "SC-CL.exe",
        root / "SC-CL.exe",
        root / "SC-CL-master" / "bin" / "SC-CL.exe",
        root / "SC-CL-master" / "SC-CL.exe",
        root / SC_CL_SOURCE / "bin" / "SC-CL.exe",
        root / SC_CL_SOURCE / "SC-CL.exe",
    ])
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists():
            return resolved
    return None


def run_command(name: str, cmd: list[str], cwd: Path, timeout: int) -> CommandResult:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
        return CommandResult(name=name, command=cmd, exit_code=proc.returncode, stdout_tail=tail(proc.stdout), stderr_tail=tail(proc.stderr))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            name=name,
            command=cmd,
            exit_code=None,
            timed_out=True,
            stdout_tail=tail((exc.stdout or "") if isinstance(exc.stdout, str) else ""),
            stderr_tail=tail((exc.stderr or "") if isinstance(exc.stderr, str) else ""),
        )


def list_outputs(out_dir: Path, root: Path) -> list[str]:
    if not out_dir.exists():
        return []
    return [rel(p, root) for p in out_dir.rglob("*") if p.is_file()]


def project_paths(root: Path, project: str) -> tuple[Path, Path | None, Path]:
    if project == "codered_menu_v1":
        src = root / SC_CL_SOURCE / "bin" / "projects" / "CodeREDMenu" / "CodeREDMenu.c"
        include_dir = root / SC_CL_SOURCE / "bin" / "include"
        out_dir = root / KIT / "output" / "codered_menu_v1"
        return src, include_dir, out_dir
    src = root / LAB / "src" / "main.c"
    out_dir = root / KIT / "output" / "vehicle_menu_probe_build"
    return src, None, out_dir


def ensure_staged_project(root: Path, project: str, report: ProbeReport) -> None:
    if project != "codered_menu_v1":
        return
    src = root / SC_CL_SOURCE / "bin" / "projects" / "CodeREDMenu" / "CodeREDMenu.c"
    if src.exists():
        return
    tool = root / STAGE_TOOL
    if not tool.exists():
        report.warnings.append("Staged CodeREDMenu.c is missing and the stage helper is unavailable.")
        return
    result = run_command("stage CodeREDMenu project", [sys.executable, str(tool)], root, timeout=60)
    report.commands.append(result)


def make_compile_commands(sccl: Path, src: Path, out_dir: Path, name: str, include_dir: Path | None) -> list[list[str]]:
    base = [str(sccl)]
    include_args: list[str] = []
    if include_dir is not None:
        include_args = [f"-extra-arg=-I{include_dir}"]
    return [
        base + ["-target=RDR_#SC", "-platform=X360", "-out-dir", str(out_dir), f"-name={name}", *include_args, str(src)],
        base + ["-target=RDR_SCO", "-platform=X360", "-out-dir", str(out_dir), f"-name={name}", *include_args, str(src)],
    ]


def compile_probe(root: Path, sccl_arg: str | None, timeout: int, project: str) -> ProbeReport:
    root = root.resolve()
    sccl = find_sccl(root, sccl_arg)
    src, include_dir, out_dir = project_paths(root, project)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = ProbeReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        ok=False,
        sccl_exe=str(sccl) if sccl else None,
        source=rel(src, root),
        output_dir=rel(out_dir, root),
        project=project,
        include_dir=rel(include_dir, root) if include_dir else None,
    )
    ensure_staged_project(root, project, report)
    if not sccl:
        report.warnings.append("SC-CL.exe was not found.")
        report.next_steps = ["Run: py -3 tools\\codered_sccl_finalize_build.py --validate"]
        write_outputs(root, report)
        return report
    if not src.exists():
        report.warnings.append(f"Missing probe source: {src}")
        report.next_steps = ["Run: py -3 tools\\codered_sccl_stage_menu_project.py"] if project == "codered_menu_v1" else []
        write_outputs(root, report)
        return report
    if include_dir is not None and not include_dir.exists():
        report.warnings.append(f"Missing real SC-CL include dir: {include_dir}")
        write_outputs(root, report)
        return report

    print(f"[CodeRED] Project: {project}", flush=True)
    print(f"[CodeRED] SC-CL: {sccl}", flush=True)
    print(f"[CodeRED] Source: {src}", flush=True)
    print(f"[CodeRED] Include: {include_dir}", flush=True)
    print(f"[CodeRED] Output: {out_dir}", flush=True)

    help_result = run_command("SC-CL help", [str(sccl), "-help"], root, timeout=min(timeout, 20))
    report.commands.append(help_result)
    if is_dll_launch_failure(help_result.exit_code):
        report.warnings.append(f"SC-CL.exe cannot launch: {status_hex(help_result.exit_code)} / STATUS_DLL_NOT_FOUND. A required DLL/runtime is missing.")
        report.next_steps = ["Run: py -3 tools\\codered_sccl_dependency_probe.py"]
        write_outputs(root, report)
        return report

    name = "codered_menu_v1" if project == "codered_menu_v1" else "vehicle_menu_probe"
    compile_commands = make_compile_commands(sccl, src, out_dir, name, include_dir)
    for index, cmd in enumerate(compile_commands, 1):
        print(f"[CodeRED] Compile attempt {index}/{len(compile_commands)}...", flush=True)
        result = run_command(f"compile attempt {index}", cmd, root, timeout=timeout)
        report.commands.append(result)
        report.output_files = list_outputs(out_dir, root)
        if is_dll_launch_failure(result.exit_code):
            report.warnings.append(f"Compile attempt {index} failed with {status_hex(result.exit_code)} / STATUS_DLL_NOT_FOUND. Stopping compile attempts.")
            report.next_steps = ["Run: py -3 tools\\codered_sccl_dependency_probe.py"]
            write_outputs(root, report)
            return report
        if result.timed_out:
            report.warnings.append(f"Compile attempt {index} timed out after {timeout}s; trying next target/options.")
            continue
        if result.exit_code == 0 and report.output_files:
            report.ok = True
            break

    if not report.ok:
        report.output_files = list_outputs(out_dir, root)
        report.warnings.append("SC-CL did not produce a verified output file from the probe source.")
        report.next_steps = [
            "Open logs\\CodeRED_SCCL_Safe_Compile_Probe_Output.txt and inspect the first compile error.",
            "Do not install/promote any compiled output until this probe passes.",
        ]
    else:
        report.next_steps = ["Compiled menu probe produced output. Next: controlled compiled-output verification before archive import."]
    write_outputs(root, report)
    return report


def markdown(report: ProbeReport) -> str:
    lines = [
        "# Code RED SC-CL Safe Compile Probe Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Result: **{'PASS' if report.ok else 'NEEDS ATTENTION'}**",
        f"Project: `{report.project}`",
        f"SC-CL.exe: `{report.sccl_exe}`",
        f"Source: `{report.source}`",
        f"Include dir: `{report.include_dir}`",
        f"Output dir: `{report.output_dir}`",
        "",
        "## Output Files",
        "",
    ]
    lines.extend(f"- `{p}`" for p in report.output_files or ["none"])
    lines.extend(["", "## Commands", ""])
    for item in report.commands:
        lines.extend([
            f"### {item.name}",
            f"- exit: `{item.exit_code}`",
            f"- exit_hex: `{status_hex(item.exit_code)}`",
            f"- timed_out: `{item.timed_out}`",
            f"- command: `{' '.join(item.command)}`",
            "",
        ])
        if item.stdout_tail:
            lines.extend(["stdout:", "```text", item.stdout_tail, "```", ""])
        if item.stderr_tail:
            lines.extend(["stderr:", "```text", item.stderr_tail, "```", ""])
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in report.warnings)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {s}" for s in report.next_steps)
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, report: ProbeReport) -> None:
    write_json(root / REPORT_JSON, asdict(report))
    md = markdown(report)
    write_text(root / REPORT_MD, md)
    chunks = []
    for item in report.commands:
        chunks.append("\n".join([
            f"## {item.name}",
            f"exit={item.exit_code} exit_hex={status_hex(item.exit_code)} timed_out={item.timed_out}",
            "COMMAND: " + " ".join(item.command),
            "STDOUT:\n" + item.stdout_tail,
            "STDERR:\n" + item.stderr_tail,
        ]))
    write_text(root / OUTPUT_LOG, "\n\n".join(chunks) + "\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run a timeout-safe SC-CL compile probe.")
    p.add_argument("--root", default=None)
    p.add_argument("--sccl", default=None, help="Explicit SC-CL.exe path")
    p.add_argument("--timeout", type=int, default=90, help="Seconds per compile attempt")
    p.add_argument("--project", default="codered_menu_v1", choices=["codered_menu_v1", "legacy_vehicle_probe"], help="Compile target project")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = root_from_arg(args.root)
    report = compile_probe(root, args.sccl, timeout=max(5, args.timeout), project=args.project)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
