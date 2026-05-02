#!/usr/bin/env python3
"""Code RED Build Assistant.

Small, conservative helper for the ScriptHookRDR AI Menu workflow. It scans the
repo, checks for a Windows C++ build environment, optionally builds the ASI, and
can install the built files into a selected game folder. It does not delete game
files and backs up overwritten runtime files.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.1.0-restored-main-safe"
AI_DIR = Path("related_apps/Code_RED_ScriptHookRDR_AI_Menu")
AI_CPP = AI_DIR / "CodeRED_AI_Menu.cpp"
AI_INI = AI_DIR / "CodeRED_AI_Menu.ini"
AI_BUILD = AI_DIR / "build"
AI_ASI = AI_BUILD / "CodeRED_AI_Menu.asi"
DATA_DIR = Path("data/codered")
LOG_PATH = Path("logs/CodeRED_Build_Assistant_last.log")
REPORT_PATH = Path("logs/CodeRED_Build_Assistant_last_report.json")


@dataclass
class ScanReport:
    version: str
    project_root: str
    game_root: str | None
    source_exists: bool
    ini_exists: bool
    data_exists: bool
    built_asi_exists: bool
    built_asi_valid: bool
    python: str
    cl: str | None
    can_build: bool
    can_install: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def valid_asi(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 1024 and path.read_bytes()[:2] == b"MZ"
    except OSError:
        return False


def find_cl() -> str | None:
    return shutil.which("cl")


def find_vsdevcmd() -> Path | None:
    candidates = []
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env)
        if base:
            candidates.append(Path(base) / "Microsoft Visual Studio/2022/Community/Common7/Tools/VsDevCmd.bat")
            candidates.append(Path(base) / "Microsoft Visual Studio/2022/BuildTools/Common7/Tools/VsDevCmd.bat")
            candidates.append(Path(base) / "Microsoft Visual Studio/2019/Community/Common7/Tools/VsDevCmd.bat")
            candidates.append(Path(base) / "Microsoft Visual Studio/2019/BuildTools/Common7/Tools/VsDevCmd.bat")
    for path in candidates:
        if path.exists():
            return path
    return None


def scan(project_root: Path, game_root: Path | None = None) -> ScanReport:
    root = project_root.resolve()
    game = game_root.resolve() if game_root else None
    source = root / AI_CPP
    ini = root / AI_INI
    data = root / DATA_DIR
    asi = root / AI_ASI
    cl = find_cl()
    vsdev = find_vsdevcmd()
    warnings: list[str] = []
    errors: list[str] = []
    if not source.exists():
        errors.append(f"Missing AI Menu source: {AI_CPP}")
    if not ini.exists():
        warnings.append(f"Missing AI Menu INI: {AI_INI}")
    if not data.exists():
        warnings.append(f"Missing data folder: {DATA_DIR}")
    if not cl and not vsdev:
        warnings.append("cl.exe is not on PATH and a common VsDevCmd.bat was not found. Build may require a Developer Command Prompt.")
    game_ok = bool(game and game.exists())
    if game and not game_ok:
        errors.append(f"Game folder does not exist: {game}")
    if game_ok and not (game / "RDR.exe").exists():
        warnings.append("Selected game folder does not contain RDR.exe.")
    if game_ok and not (game / "ScriptHookRDR.dll").exists():
        warnings.append("Selected game folder does not contain ScriptHookRDR.dll.")
    if game_ok and not (game / "dinput8.dll").exists():
        warnings.append("Selected game folder does not contain dinput8.dll ASI loader.")
    asi_valid = valid_asi(asi)
    return ScanReport(
        version=VERSION,
        project_root=str(root),
        game_root=str(game) if game else None,
        source_exists=source.exists(),
        ini_exists=ini.exists(),
        data_exists=data.exists(),
        built_asi_exists=asi.exists(),
        built_asi_valid=asi_valid,
        python=sys.executable,
        cl=cl or (str(vsdev) if vsdev else None),
        can_build=source.exists() and bool(cl or vsdev),
        can_install=bool(game_ok and asi_valid and ini.exists()),
        warnings=warnings,
        errors=errors,
    )


def write_report(root: Path, report: ScanReport) -> None:
    path = root / REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")


def log(root: Path, message: str) -> None:
    path = root / LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n")
    print(message)


def summarize(report: ScanReport) -> str:
    lines = [
        f"Code RED Build Assistant {report.version}",
        f"Project: {report.project_root}",
        f"Game:    {report.game_root or '(not selected)'}",
        "",
        f"Source exists:   {report.source_exists}",
        f"INI exists:      {report.ini_exists}",
        f"Data exists:     {report.data_exists}",
        f"Built ASI valid: {report.built_asi_valid}",
        f"Build tool:      {report.cl or '(not found)'}",
        f"Can build:       {report.can_build}",
        f"Can install:     {report.can_install}",
    ]
    if report.warnings:
        lines.append("\nWarnings:")
        lines.extend(f"- {x}" for x in report.warnings)
    if report.errors:
        lines.append("\nErrors:")
        lines.extend(f"- {x}" for x in report.errors)
    return "\n".join(lines)


def build(project_root: Path) -> int:
    root = project_root.resolve()
    (root / LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / LOG_PATH).write_text("", encoding="utf-8")
    report = scan(root)
    write_report(root, report)
    if not report.can_build:
        log(root, summarize(report))
        return 2
    src = root / AI_CPP
    out_dir = root / AI_BUILD
    out_dir.mkdir(parents=True, exist_ok=True)
    out = root / AI_ASI
    obj = out_dir / "CodeRED_AI_Menu.obj"
    pdb = out_dir / "CodeRED_AI_Menu.pdb"
    lib = out_dir / "CodeRED_AI_Menu.lib"
    cmd = f'cl /std:c++17 /EHsc /LD /nologo "{src}" /Fo"{obj}" /Fd"{pdb}" /Fe"{out}" /link /OUT:"{out}" /IMPLIB:"{lib}"'
    if shutil.which("cl"):
        full_cmd = cmd
    elif report.cl and report.cl.lower().endswith("vsdevcmd.bat"):
        full_cmd = f'call "{report.cl}" -arch=x64 -host_arch=x64 >nul && {cmd}'
    else:
        log(root, "No C++ build environment available.")
        return 2
    log(root, "Building CodeRED_AI_Menu.asi...")
    proc = subprocess.run(["cmd.exe", "/d", "/s", "/c", full_cmd], cwd=str(root), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.stdout:
        log(root, proc.stdout)
    if proc.returncode != 0:
        log(root, f"Build failed with exit code {proc.returncode}.")
        return proc.returncode
    if not valid_asi(out):
        log(root, "Build output failed ASI validation.")
        return 3
    log(root, f"Built: {out}")
    return 0


def backup_copy(src: Path, dst: Path, backup_dir: Path) -> None:
    if dst.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup_dir / dst.name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def install(project_root: Path, game_root: Path) -> int:
    root = project_root.resolve()
    game = game_root.resolve()
    report = scan(root, game)
    write_report(root, report)
    if not report.can_install:
        log(root, summarize(report))
        return 2
    backup_dir = game / "CodeRED_Backups" / f"AI_Menu_{stamp()}"
    backup_copy(root / AI_ASI, game / "CodeRED_AI_Menu.asi", backup_dir)
    backup_copy(root / AI_INI, game / "CodeRED_AI_Menu.ini", backup_dir)
    src_data = root / DATA_DIR
    if src_data.exists():
        for file in src_data.rglob("*"):
            if file.is_file():
                dst = game / DATA_DIR / file.relative_to(src_data)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dst)
    (game / "scratch").mkdir(parents=True, exist_ok=True)
    log(root, f"Installed AI Menu runtime to {game}")
    return 0


def clean(project_root: Path) -> int:
    root = project_root.resolve()
    build_dir = root / AI_BUILD
    if build_dir.exists():
        shutil.rmtree(build_dir)
        log(root, f"Removed {build_dir}")
    else:
        log(root, f"Nothing to remove: {build_dir}")
    return 0


def run_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext
    root_dir = repo_root()
    app = tk.Tk()
    app.title("Code RED Build Assistant")
    app.geometry("820x560")
    project_var = tk.StringVar(value=str(root_dir))
    game_var = tk.StringVar(value="")
    out = scrolledtext.ScrolledText(app, wrap="word")

    def project() -> Path:
        return Path(project_var.get()).expanduser()

    def game() -> Path | None:
        text = game_var.get().strip()
        return Path(text).expanduser() if text else None

    def show(text: str) -> None:
        out.delete("1.0", "end")
        out.insert("end", text)

    def do_scan() -> None:
        report = scan(project(), game())
        write_report(project(), report)
        show(summarize(report))

    def do_build() -> None:
        code = build(project())
        do_scan()
        if code != 0:
            messagebox.showerror("Build failed", f"Build exited with code {code}.")

    def do_install(build_first: bool = False) -> None:
        g = game()
        if not g:
            messagebox.showwarning("Missing game folder", "Select the folder containing RDR.exe first.")
            return
        if build_first:
            code = build(project())
            if code != 0:
                do_scan()
                messagebox.showerror("Build failed", f"Build exited with code {code}.")
                return
        code = install(project(), g)
        do_scan()
        if code != 0:
            messagebox.showerror("Install failed", f"Install exited with code {code}.")

    top = tk.Frame(app)
    top.pack(fill="x", padx=10, pady=8)
    tk.Label(top, text="Project").grid(row=0, column=0, sticky="w")
    tk.Entry(top, textvariable=project_var).grid(row=0, column=1, sticky="ew", padx=5)
    tk.Button(top, text="Browse", command=lambda: project_var.set(filedialog.askdirectory() or project_var.get())).grid(row=0, column=2)
    tk.Label(top, text="Game folder").grid(row=1, column=0, sticky="w")
    tk.Entry(top, textvariable=game_var).grid(row=1, column=1, sticky="ew", padx=5)
    tk.Button(top, text="Browse", command=lambda: game_var.set(filedialog.askdirectory() or game_var.get())).grid(row=1, column=2)
    top.columnconfigure(1, weight=1)
    buttons = tk.Frame(app)
    buttons.pack(fill="x", padx=10)
    tk.Button(buttons, text="Scan", command=do_scan).pack(side="left", padx=3)
    tk.Button(buttons, text="Build", command=do_build).pack(side="left", padx=3)
    tk.Button(buttons, text="Install", command=lambda: do_install(False)).pack(side="left", padx=3)
    tk.Button(buttons, text="Build + Install", command=lambda: do_install(True)).pack(side="left", padx=3)
    tk.Button(buttons, text="Clean", command=lambda: (clean(project()), do_scan())).pack(side="left", padx=3)
    out.pack(fill="both", expand=True, padx=10, pady=8)
    do_scan()
    app.mainloop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Code RED Build Assistant")
    parser.add_argument("cmd", nargs="?", default="gui", choices=["gui", "scan", "build", "install", "build-install", "clean"])
    parser.add_argument("--project-root", type=Path, default=repo_root())
    parser.add_argument("--game-root", type=Path)
    args = parser.parse_args()
    if args.cmd == "gui":
        return run_gui()
    root = args.project_root.resolve()
    if args.cmd == "scan":
        report = scan(root, args.game_root)
        write_report(root, report)
        print(summarize(report))
        return 0 if not report.errors else 1
    if args.cmd == "build":
        return build(root)
    if args.cmd == "install":
        if not args.game_root:
            print("install requires --game-root")
            return 2
        return install(root, args.game_root)
    if args.cmd == "build-install":
        if not args.game_root:
            print("build-install requires --game-root")
            return 2
        code = build(root)
        return code if code else install(root, args.game_root)
    if args.cmd == "clean":
        return clean(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
