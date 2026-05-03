#!/usr/bin/env python3
"""Code RED SC-CL Easy Setup.

Guided setup for the Script Workshop / Script Compile Lab compiler stage.

This tool makes the previously manual stage straightforward:
- detect SC-CL.exe in known Code RED locations
- detect Visual Studio / Build Tools compiler helpers where possible
- adopt a user-supplied SC-CL.exe into the build kit safely
- write proof reports and a reusable environment helper
- optionally run the script compile validator after setup

It never installs scripts into the game and never promotes compiled outputs automatically.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.1-sccl-easy-setup-friendly-errors"
BUNDLE = Path("related_apps/code_red_sccl_attempt_bundle_v1")
LAB = BUNDLE / "code_red_script_compile_lab_v1"
KIT = BUNDLE / "code_red_sccl_windows_build_kit_v1"
DROP = Path("resources/SC-CL_DROP_HERE")
REPORT_JSON = Path("logs/CodeRED_SCCL_Easy_Setup_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Easy_Setup_Report.md")
PASS_LOG = Path("logs/CodeRED_SCCL_Easy_Setup_Lane_Pass_2026-05-03.md")
ENV_BAT = KIT / "CodeRED_SCCL_Env.bat"
ENV_PS1 = KIT / "CodeRED_SCCL_Env.ps1"
PLACEHOLDER_TOKENS = {"PATH_TO_SC-CL.EXE", "PATH_TO_SCCL.EXE", "C:\\PATH\\TO\\SC-CL.EXE"}


@dataclass
class SetupReport:
    version: str
    generated_utc: str
    root: str
    ok: bool
    windows_host: bool
    sccl_exe: str | None = None
    cl_exe: str | None = None
    msbuild_exe: str | None = None
    vswhere_exe: str | None = None
    python_exe: str = sys.executable
    searched_paths: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def root_from_arg(raw: str | None) -> Path:
    if raw:
        return Path(raw).resolve()
    return Path(__file__).resolve().parents[1]


def candidate_sccl_paths(root: Path) -> list[Path]:
    env = os.environ.get("SCCL_EXE")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.extend([
        root / "SC-CL.exe",
        root / "resources" / "SC-CL.exe",
        root / "resources" / "SC-CL" / "SC-CL.exe",
        root / DROP / "SC-CL.exe",
        root / "resources" / "SC-CL-master" / "bin" / "SC-CL.exe",
        root / "resources" / "SC-CL-master" / "llvm-14.0.0.src" / "MinSizeRel" / "bin" / "SC-CL.exe",
        root / BUNDLE / "SC-CL.exe",
        root / KIT / "SC-CL.exe",
        root / LAB / "SC-CL.exe",
    ])
    seen: set[str] = set()
    out = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            out.append(resolved)
    return out


def find_first(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def shutil_which(name: str) -> str | None:
    return shutil.which(name)


def find_vswhere() -> str | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return shutil_which("vswhere")


def find_msbuild(vswhere: str | None) -> str | None:
    msbuild = shutil_which("MSBuild.exe") or shutil_which("msbuild")
    if msbuild:
        return msbuild
    if not vswhere:
        return None
    try:
        proc = subprocess.run(
            [vswhere, "-latest", "-requires", "Microsoft.Component.MSBuild", "-find", "MSBuild\\**\\Bin\\MSBuild.exe"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        for line in proc.stdout.splitlines():
            candidate = line.strip()
            if candidate and Path(candidate).exists():
                return candidate
    except Exception:
        return None
    return None


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def ensure_drop_readme(root: Path) -> Path:
    drop = root / DROP
    drop.mkdir(parents=True, exist_ok=True)
    readme = drop / "README_DROP_SC_CL_EXE_HERE.txt"
    if not readme.exists():
        write_text(readme,
            "Code RED SC-CL Drop Folder\n"
            "==========================\n\n"
            "Put the real SC-CL.exe here:\n\n"
            "  resources\\SC-CL_DROP_HERE\\SC-CL.exe\n\n"
            "Then run:\n\n"
            "  py -3 tools\\codered_sccl_easy_setup.py adopt --sccl resources\\SC-CL_DROP_HERE\\SC-CL.exe --run-validator\n",
        )
    return readme


def write_env_helpers(root: Path, sccl: Path | None, report: SetupReport) -> None:
    kit = root / KIT
    kit.mkdir(parents=True, exist_ok=True)
    sccl_text = str(sccl) if sccl else str(root / DROP / "SC-CL.exe")
    write_text(root / ENV_BAT,
        "@echo off\n"
        "rem Code RED SC-CL environment helper.\n"
        f"set \"SCCL_EXE={sccl_text}\"\n"
        "echo SCCL_EXE=%SCCL_EXE%\n",
    )
    write_text(root / ENV_PS1,
        "# Code RED SC-CL environment helper.\n"
        f"$env:SCCL_EXE = '{sccl_text}'\n"
        "Write-Host \"SCCL_EXE=$env:SCCL_EXE\"\n",
    )
    report.outputs["env_bat"] = rel_to(root / ENV_BAT, root)
    report.outputs["env_ps1"] = rel_to(root / ENV_PS1, root)
    report.outputs["drop_readme"] = rel_to(ensure_drop_readme(root), root)


def is_placeholder_path(source: Path) -> bool:
    raw = str(source).upper()
    return source.name.upper() in PLACEHOLDER_TOKENS or "PATH_TO" in raw or "PATH\\TO" in raw


def adopt_sccl(root: Path, source: Path, report: SetupReport) -> Path | None:
    if is_placeholder_path(source):
        report.warnings.append("The --sccl value is still a placeholder. Replace PATH_TO_SC-CL.exe with the real file path, or put SC-CL.exe in resources\\SC-CL_DROP_HERE.")
        report.actions.append("Adopt skipped because a placeholder path was supplied.")
        return None
    if not source.exists():
        report.warnings.append(f"SC-CL.exe was not found at: {source}")
        report.actions.append("Adopt skipped because the supplied file does not exist.")
        return None
    if source.name.lower() != "sc-cl.exe":
        report.warnings.append(f"The supplied file is named {source.name!r}; expected SC-CL.exe. It will still be staged if it exists.")
    target = root / KIT / "SC-CL.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
        report.actions.append(f"Copied SC-CL.exe to {rel_to(target, root)}")
    else:
        report.actions.append(f"SC-CL.exe already staged at {rel_to(target, root)}")
    report.sccl_exe = str(target)
    return target


def next_steps_for(sccl_found: bool) -> list[str]:
    if sccl_found:
        return [
            "Run: py -3 tools\\codered_script_compile_validation.py",
            "Run: related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat",
        ]
    return [
        "Run: py -3 tools\\codered_sccl_source_probe.py --source \"D:\\Games\\Red Dead Redemption\\Code_RED\\SC-CL-master\"",
        "If the source probe says RDR-ready but no exe exists, build SC-CL or obtain the Windows SC-CL.exe.",
        "Place the real SC-CL.exe at: resources\\SC-CL_DROP_HERE\\SC-CL.exe",
        "Run: py -3 tools\\codered_sccl_easy_setup.py adopt --sccl resources\\SC-CL_DROP_HERE\\SC-CL.exe --run-validator",
    ]


def build_report(root: Path, *, adopt: Path | None = None, run_validator: bool = False) -> SetupReport:
    searched = candidate_sccl_paths(root)
    report = SetupReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        ok=False,
        windows_host=sys.platform.startswith("win"),
        searched_paths=[str(p) for p in searched],
    )
    staged_sccl: Path | None = None
    if adopt is not None:
        staged_sccl = adopt_sccl(root, adopt, report)
    else:
        staged_sccl = find_first(searched)
        if staged_sccl:
            report.sccl_exe = str(staged_sccl)
            report.actions.append(f"Detected SC-CL.exe at {staged_sccl}")
    report.cl_exe = shutil_which("cl")
    report.vswhere_exe = find_vswhere()
    report.msbuild_exe = find_msbuild(report.vswhere_exe)
    write_env_helpers(root, staged_sccl, report)

    if not staged_sccl:
        report.warnings.append("SC-CL.exe is not staged yet. This blocks real compiled-script output, but not scan/read/edit/export queue preparation.")
    if report.windows_host and not report.cl_exe and not report.msbuild_exe:
        report.warnings.append("Visual Studio Build Tools/MSVC were not detected in PATH. This is only needed if building SC-CL or C/C++ helper binaries locally.")
    if not report.windows_host:
        report.warnings.append("Non-Windows host: setup can validate paths, but real SC-CL Windows proof should run on Windows.")

    report.next_steps = next_steps_for(staged_sccl is not None)

    if run_validator:
        proc = subprocess.run(
            [sys.executable, str(root / "tools" / "codered_script_compile_validation.py")],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        report.actions.append(f"Script compile validation exit: {proc.returncode}")
        validator_log = root / "logs" / "CodeRED_SCCL_Easy_Setup_Validator_Output.txt"
        write_text(validator_log, proc.stdout + "\n" + proc.stderr)
        report.outputs["validator_output"] = rel_to(validator_log, root)
    report.ok = bool(report.sccl_exe)
    return report


def report_markdown(report: SetupReport) -> str:
    lines = [
        "# Code RED SC-CL Easy Setup Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"Result: **{'READY' if report.ok else 'NEEDS SC-CL'}**",
        "",
        "## Detected Tools",
        "",
        f"- SC-CL.exe: `{report.sccl_exe}`",
        f"- cl.exe: `{report.cl_exe}`",
        f"- MSBuild: `{report.msbuild_exe}`",
        f"- vswhere: `{report.vswhere_exe}`",
        f"- Python: `{report.python_exe}`",
        f"- Windows host: `{report.windows_host}`",
        "",
        "## Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in report.actions or ["No setup actions were needed."])
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in report.warnings)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- `{item}`" for item in report.next_steps)
    lines.extend(["", "## Searched SC-CL Paths", ""])
    lines.extend(f"- `{item}`" for item in report.searched_paths)
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, report: SetupReport) -> None:
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, report_markdown(report))
    write_text(root / PASS_LOG,
        "# Code RED SC-CL Easy Setup Lane Pass\n\n"
        "Added guided setup for the Script Workshop compiler stage.\n\n"
        f"Report: `{REPORT_MD.as_posix()}`\n",
    )


def open_folder(path: Path) -> None:
    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code RED SC-CL Easy Setup")
    sub = parser.add_subparsers(dest="command")
    p_status = sub.add_parser("status", help="Detect SC-CL/MSVC state and write proof report")
    p_status.add_argument("--root", default=None)
    p_status.add_argument("--run-validator", action="store_true")
    p_adopt = sub.add_parser("adopt", help="Copy a supplied SC-CL.exe into the Code RED build kit")
    p_adopt.add_argument("--root", default=None)
    p_adopt.add_argument("--sccl", required=True, help="Path to the real SC-CL.exe file. Do not use the placeholder text PATH_TO_SC-CL.exe.")
    p_adopt.add_argument("--run-validator", action="store_true")
    p_open = sub.add_parser("open-kit", help="Open the Windows build kit folder")
    p_open.add_argument("--root", default=None)
    p_drop = sub.add_parser("open-drop", help="Open/create the SC-CL.exe drop folder")
    p_drop.add_argument("--root", default=None)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    command = args.command or "status"
    root = root_from_arg(getattr(args, "root", None))
    if command == "open-kit":
        (root / KIT).mkdir(parents=True, exist_ok=True)
        open_folder(root / KIT)
        return 0
    if command == "open-drop":
        ensure_drop_readme(root)
        open_folder(root / DROP)
        return 0
    adopt = Path(args.sccl).resolve() if command == "adopt" else None
    report = build_report(root, adopt=adopt, run_validator=getattr(args, "run_validator", False))
    write_outputs(root, report)
    print(report_markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
