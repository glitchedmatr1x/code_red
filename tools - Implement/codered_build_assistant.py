#!/usr/bin/env python3
"""Code RED Build Assistant.

Automates the local Visual Studio compile/install loop for the CodeRED AI Menu ASI.
It is intentionally conservative: scan first, refuse unsafe/incomplete builds, validate
ASI output, back up old runtime files, and keep build clutter out of the game folder.
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
from typing import Callable

VERSION = "1.0.1-vs-command-quote-fix"
AI_DIR = Path("related_apps/Code_RED_ScriptHookRDR_AI_Menu")
AI_CPP = AI_DIR / "CodeRED_AI_Menu.cpp"
AI_INI = AI_DIR / "CodeRED_AI_Menu.ini"
AI_BUILD = AI_DIR / "build"
AI_ASI = AI_BUILD / "CodeRED_AI_Menu.asi"
AI_OBJ = AI_BUILD / "CodeRED_AI_Menu.obj"
AI_PDB = AI_BUILD / "CodeRED_AI_Menu.pdb"
AI_LIB = AI_BUILD / "CodeRED_AI_Menu.lib"
DATA_CODERED = Path("data/codered")
LOG_PATH = Path("logs/CodeRED_Build_Assistant_last.log")
REPORT_PATH = Path("logs/CodeRED_Build_Assistant_last_report.json")
BUILD_BAT = AI_BUILD / "_codered_build_ai_menu.bat"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def q(value: Path | str) -> str:
    """Quote a Windows command/batch argument without backslash escaping.

    cmd.exe and .bat files expect plain double quotes around paths with spaces.
    Backslash-escaped quotes produce literal \" characters and break paths such
    as C:\\Program Files\\Microsoft Visual Studio\\...
    """
    return '"' + str(value).replace('"', '""') + '"'


def stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


@dataclass
class VSInfo:
    cl: str | None = None
    link: str | None = None
    vswhere: str | None = None
    install: str | None = None
    devcmd: str | None = None
    vcvars64: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.cl or self.devcmd or self.vcvars64)


@dataclass
class ScanReport:
    version: str
    project_root: str
    game_root: str | None
    vs: VSInfo
    project_exists: bool
    game_exists: bool
    rdr_exe: bool
    scripthook: bool
    asi_loader: bool
    source_exists: bool
    ini_exists: bool
    data_exists: bool
    built_asi_exists: bool
    built_asi_valid: bool
    can_build: bool
    can_install: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Log:
    def __init__(self, path: Path, sink: Callable[[str], None] | None = None) -> None:
        self.path = path
        self.sink = sink
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def write(self, msg: str = "") -> None:
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(msg + "\n")
        if self.sink:
            self.sink(msg)

    def section(self, title: str) -> None:
        self.write("\n" + "=" * 72)
        self.write(title)
        self.write("=" * 72)


def find_vswhere() -> Path | None:
    paths: list[Path] = []
    if os.environ.get("ProgramFiles(x86)"):
        paths.append(Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe")
    if os.environ.get("ProgramFiles"):
        paths.append(Path(os.environ["ProgramFiles"]) / "Microsoft Visual Studio/Installer/vswhere.exe")
    for path in paths:
        if path.exists():
            return path
    found = shutil.which("vswhere")
    return Path(found) if found else None


def detect_vs() -> VSInfo:
    info = VSInfo(cl=shutil.which("cl"), link=shutil.which("link"))
    if info.cl:
        info.notes.append("cl.exe is already available in PATH.")
    where = find_vswhere()
    if not where:
        info.notes.append("vswhere.exe not found.")
        if not info.ready:
            info.notes.append("No Visual Studio C++ environment detected.")
        return info
    info.vswhere = str(where)
    proc = subprocess.run([
        str(where), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    install = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    if not install:
        info.notes.append("vswhere found, but no C++ toolset install was returned.")
        return info
    info.install = install
    devcmd = Path(install) / "Common7/Tools/VsDevCmd.bat"
    vcvars = Path(install) / "VC/Auxiliary/Build/vcvars64.bat"
    if devcmd.exists():
        info.devcmd = str(devcmd)
    if vcvars.exists():
        info.vcvars64 = str(vcvars)
    info.notes.append(f"Visual Studio C++ toolset found: {install}")
    return info


def valid_asi(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 1024 and path.read_bytes()[:2] == b"MZ"
    except OSError:
        return False


def scan(project: Path, game: Path | None = None) -> ScanReport:
    project = project.resolve()
    game = game.resolve() if game else None
    vs = detect_vs()
    source = project / AI_CPP
    ini = project / AI_INI
    data = project / DATA_CODERED
    asi = project / AI_ASI
    game_exists = bool(game and game.exists())
    rdr = bool(game and (game / "RDR.exe").exists())
    scripthook = bool(game and (game / "ScriptHookRDR.dll").exists())
    loader = bool(game and (game / "dinput8.dll").exists())
    errors: list[str] = []
    warnings: list[str] = []
    if not project.exists():
        errors.append(f"Project folder missing: {project}")
    if not source.exists():
        errors.append(f"AI Menu source missing: {source}")
    if not vs.ready:
        errors.append("Visual Studio C++ tools not detected.")
    if game and not game_exists:
        errors.append(f"Game folder missing: {game}")
    if game and game_exists and not rdr:
        warnings.append("RDR.exe not found in selected game folder.")
    if game and game_exists and not scripthook:
        warnings.append("ScriptHookRDR.dll not found in selected game folder.")
    if game and game_exists and not loader:
        warnings.append("dinput8.dll ASI loader not found in selected game folder.")
    if not ini.exists():
        warnings.append(f"AI Menu INI missing: {ini}")
    if not data.exists():
        warnings.append(f"data/codered missing: {data}")
    asi_valid = valid_asi(asi)
    return ScanReport(
        version=VERSION, project_root=str(project), game_root=str(game) if game else None, vs=vs,
        project_exists=project.exists(), game_exists=game_exists, rdr_exe=rdr, scripthook=scripthook,
        asi_loader=loader, source_exists=source.exists(), ini_exists=ini.exists(), data_exists=data.exists(),
        built_asi_exists=asi.exists(), built_asi_valid=asi_valid,
        can_build=project.exists() and source.exists() and vs.ready,
        can_install=bool(game and game_exists and rdr and ini.exists() and asi_valid),
        errors=errors, warnings=warnings,
    )


def save_report(report: ScanReport, project: Path) -> None:
    out = project / REPORT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")


def summarize(report: ScanReport) -> str:
    lines = [
        f"CodeRED Build Assistant {report.version}",
        f"Project: {report.project_root}",
        f"Game:    {report.game_root or '(not selected)'}", "",
        f"Visual Studio ready: {report.vs.ready}",
        f"RDR.exe found:        {report.rdr_exe}",
        f"ScriptHookRDR found:  {report.scripthook}",
        f"ASI loader found:     {report.asi_loader}",
        f"Source exists:        {report.source_exists}",
        f"Built ASI valid:      {report.built_asi_valid}",
        f"Can build:            {report.can_build}",
        f"Can install:          {report.can_install}",
    ]
    if report.vs.notes:
        lines += ["", "Visual Studio detection:"] + [f"  - {x}" for x in report.vs.notes]
    if report.errors:
        lines += ["", "Errors:"] + [f"  - {x}" for x in report.errors]
    if report.warnings:
        lines += ["", "Warnings:"] + [f"  - {x}" for x in report.warnings]
    return "\n".join(lines)


def write_build_batch(project: Path, vs: VSInfo, cl_command: str) -> Path:
    batch = project / BUILD_BAT
    batch.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "@echo off",
        "setlocal",
        "echo CodeRED Build Assistant native build script",
    ]
    if vs.cl:
        lines.append("echo cl.exe already available in PATH")
    elif vs.devcmd:
        lines.append(f"call {q(vs.devcmd)} -arch=x64 -host_arch=x64")
        lines.append("if errorlevel 1 exit /b %ERRORLEVEL%")
    elif vs.vcvars64:
        lines.append(f"call {q(vs.vcvars64)}")
        lines.append("if errorlevel 1 exit /b %ERRORLEVEL%")
    else:
        raise RuntimeError("No usable Visual Studio command environment was found.")
    lines.extend([
        cl_command,
        "exit /b %ERRORLEVEL%",
    ])
    batch.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return batch


def build(project: Path, log: Log) -> Path:
    project = project.resolve()
    report = scan(project)
    save_report(report, project)
    if not report.can_build:
        log.section("Build refused")
        for item in report.errors:
            log.write("ERROR: " + item)
        raise RuntimeError("Build requirements were not satisfied.")
    outdir = project / AI_BUILD
    outdir.mkdir(parents=True, exist_ok=True)
    src, out = project / AI_CPP, project / AI_ASI
    obj, pdb, lib = project / AI_OBJ, project / AI_PDB, project / AI_LIB
    cl_command = (
        f"cl /std:c++17 /EHsc /LD /nologo {q(src)} /Fo{q(obj)} /Fd{q(pdb)} /Fe{q(out)} "
        f"/link /OUT:{q(out)} /IMPLIB:{q(lib)}"
    )
    batch = write_build_batch(project, report.vs, cl_command)
    log.section("Building CodeRED_AI_Menu.asi")
    log.write(f"Source: {src}")
    log.write(f"Output: {out}")
    log.write(f"Build script: {batch}")
    proc = subprocess.run(["cmd.exe", "/d", "/c", str(batch)], cwd=str(project), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.stdout:
        log.write(proc.stdout.rstrip())
    if proc.returncode != 0:
        raise RuntimeError(f"Build failed with exit code {proc.returncode}.")
    if not valid_asi(out):
        raise RuntimeError("Build output failed ASI validation. It is missing, too small, or not MZ/PE.")
    log.write(f"Built and validated: {out}")
    return out


def backup(path: Path, backup_dir: Path, log: Log) -> None:
    if not path.exists():
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / path.name
    shutil.copy2(path, dst)
    log.write(f"Backed up {path.name} -> {dst}")


def copy_data(src: Path, dst: Path, log: Log) -> None:
    if not src.exists():
        log.write(f"Skipped missing data folder: {src}")
        return
    for item in src.rglob("*"):
        if item.is_file():
            target = dst / item.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            log.write(f"Copied {target}")


def install(project: Path, game: Path, log: Log, build_first: bool = False) -> None:
    project, game = project.resolve(), game.resolve()
    if build_first:
        build(project, log)
    report = scan(project, game)
    save_report(report, project)
    if not report.can_install:
        log.section("Install refused")
        for item in report.errors + report.warnings:
            log.write(item)
        raise RuntimeError("Install requirements were not satisfied.")
    backup_dir = game / "CodeRED_Backups" / f"AI_Menu_{stamp()}"
    log.section("Installing CodeRED AI Menu runtime")
    backup(game / "CodeRED_AI_Menu.asi", backup_dir, log)
    backup(game / "CodeRED_AI_Menu.ini", backup_dir, log)
    shutil.copy2(project / AI_ASI, game / "CodeRED_AI_Menu.asi")
    shutil.copy2(project / AI_INI, game / "CodeRED_AI_Menu.ini")
    copy_data(project / DATA_CODERED, game / DATA_CODERED, log)
    (game / "scratch").mkdir(parents=True, exist_ok=True)
    log.write("Install complete.")


def clean(project: Path, log: Log) -> None:
    build_dir = project.resolve() / AI_BUILD
    log.section("Cleaning AI Menu build folder")
    if build_dir.exists():
        shutil.rmtree(build_dir)
        log.write(f"Removed: {build_dir}")
    else:
        log.write(f"Nothing to remove: {build_dir}")


class GUI:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext
        self.tk, self.filedialog, self.messagebox = tk, filedialog, messagebox
        self.root = tk.Tk()
        self.root.title("CodeRED Build Assistant")
        self.root.geometry("900x620")
        self.project_var = tk.StringVar(value=str(repo_root()))
        self.game_var = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready")
        top = tk.Frame(self.root); top.pack(fill="x", padx=10, pady=8)
        self.row(top, "Project folder", self.project_var, self.pick_project, 0)
        self.row(top, "RDR game folder", self.game_var, self.pick_game, 1)
        buttons = tk.Frame(self.root); buttons.pack(fill="x", padx=10, pady=4)
        for label, fn in [("Scan", self.do_scan), ("Build", self.do_build), ("Install", self.do_install),
                          ("Build + Install", self.do_build_install), ("Clean", self.do_clean), ("Open Logs", self.open_logs)]:
            tk.Button(buttons, text=label, command=fn).pack(side="left", padx=4)
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=10)
        self.out = scrolledtext.ScrolledText(self.root, wrap="word")
        self.out.pack(fill="both", expand=True, padx=10, pady=8)
        self.do_scan()

    def row(self, parent, label, var, fn, row):
        tk = self.tk
        tk.Label(parent, text=label, width=16, anchor="w").grid(row=row, column=0, sticky="w")
        tk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=4, pady=3)
        tk.Button(parent, text="Browse", command=fn).grid(row=row, column=2, padx=4)
        parent.columnconfigure(1, weight=1)

    def project(self) -> Path: return Path(self.project_var.get()).expanduser()
    def game(self) -> Path | None: return Path(self.game_var.get()).expanduser() if self.game_var.get().strip() else None
    def write(self, text: str) -> None:
        self.out.insert("end", text + "\n"); self.out.see("end"); self.root.update_idletasks()
    def clear(self) -> None: self.out.delete("1.0", "end")
    def logger(self) -> Log: return Log(self.project() / LOG_PATH, self.write)
    def pick_project(self):
        path = self.filedialog.askdirectory(title="Select Code_RED project folder")
        if path: self.project_var.set(path); self.do_scan()
    def pick_game(self):
        path = self.filedialog.askdirectory(title="Select folder containing RDR.exe")
        if path: self.game_var.set(path); self.do_scan()
    def do_scan(self):
        self.clear(); report = scan(self.project(), self.game()); save_report(report, self.project())
        self.write(summarize(report)); self.status.set("Ready to build" if report.can_build else "Cannot build yet")
    def run_action(self, fn, ok: str, fail: str):
        self.clear(); log = self.logger()
        try: fn(log); self.status.set(ok)
        except Exception as exc: log.write("ERROR: " + str(exc)); self.status.set(fail); self.messagebox.showerror(fail, str(exc))
    def do_build(self): self.run_action(lambda log: build(self.project(), log), "Build succeeded", "Build failed")
    def do_install(self):
        game = self.game()
        if not game: self.messagebox.showwarning("Missing game folder", "Select the folder containing RDR.exe first."); return
        self.run_action(lambda log: install(self.project(), game, log, False), "Install succeeded", "Install failed")
    def do_build_install(self):
        game = self.game()
        if not game: self.messagebox.showwarning("Missing game folder", "Select the folder containing RDR.exe first."); return
        self.run_action(lambda log: install(self.project(), game, log, True), "Build + install succeeded", "Build + install failed")
    def do_clean(self): self.run_action(lambda log: clean(self.project(), log), "Clean complete", "Clean failed")
    def open_logs(self):
        path = self.project() / "logs"; path.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"): os.startfile(str(path))  # type: ignore[attr-defined]
        else: subprocess.Popen(["xdg-open", str(path)])
    def mainloop(self): self.root.mainloop()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Code RED local ASI build/install assistant.")
    p.add_argument("cmd", nargs="?", default="gui", choices=["gui", "scan", "build", "install", "build-install", "clean"])
    p.add_argument("--project-root", type=Path, default=repo_root())
    p.add_argument("--game-root", type=Path)
    p.add_argument("--log", type=Path)
    return p


def main() -> int:
    args = parser().parse_args()
    if args.cmd == "gui":
        GUI().mainloop(); return 0
    project = args.project_root.resolve()
    log = Log(args.log or project / LOG_PATH, print)
    try:
        if args.cmd == "scan":
            report = scan(project, args.game_root); save_report(report, project); print(summarize(report)); return 0 if report.can_build else 1
        if args.cmd == "build": build(project, log); return 0
        if args.cmd == "install":
            if not args.game_root: raise RuntimeError("install requires --game-root")
            install(project, args.game_root, log, False); return 0
        if args.cmd == "build-install":
            if not args.game_root: raise RuntimeError("build-install requires --game-root")
            install(project, args.game_root, log, True); return 0
        if args.cmd == "clean": clean(project, log); return 0
    except Exception as exc:
        log.write("ERROR: " + str(exc)); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
