#!/usr/bin/env python3
"""
Code Red Syringe v0.3 Lite

No visible editor automation. No Magic-RDR moving. No fake injection claims.

Default behavior:
  - Read a changed-files folder or zip.
  - Map relative paths to RPF internal paths.
  - Build a verified patch package + manifest + command notes.
  - Do not alter the RPF.

Advanced behavior:
  - Can call a true headless command-line writer if you explicitly configure it.
  - Verifies the RPF bytes changed before counting it as injected.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Code Red Syringe"
APP_VERSION = "0.3.0-lite"
CONFIG_NAME = "CodeRedSyringe.config.json"
OUT_DIR = "__syringe_output__"
WORK_DIR = "__syringe_work__"
BACKUP_DIR = "__syringe_backups__"
RPF_MAGIC = {
    b"RPF6": "RPF6 / Red Dead Redemption",
    b"RPF7": "RPF7 / GTA V",
    b"RPF8": "RPF8 / RDR2",
    b"RPF5": "RPF5",
    b"RPF4": "RPF4",
    b"RPF3": "RPF3",
    b"RPF2": "RPF2",
    b"RPF0": "RPF0",
    b"RPF\0": "RPF0",
}
DEFAULT_CONFIG = {
    "version": APP_VERSION,
    "strip_prefixes": [],
    "blocked_extensions": [".bak", ".tmp", ".log"],
    "exclude_names": [".DS_Store", "Thumbs.db", "desktop.ini"],
    "writer": {
        "enabled": False,
        "executable": "",
        "command_template": "{writer} -replace {rpf} {internal_dir} {import_dir} -current",
        "timeout_seconds_per_directory": 300,
        "hide_console_window": True,
        "verify_archive_changed": True
    }
}

@dataclass(frozen=True)
class Item:
    source: Path
    internal_path: str
    internal_dir: str
    file_name: str
    size: int
    sha256: str

@dataclass(frozen=True)
class Job:
    internal_dir: str
    import_dir: Path
    item_count: int
    command: str


def app_home() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_config(home: Path) -> dict:
    cfg_path = home / CONFIG_NAME
    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Could not read {CONFIG_NAME}: {exc}") from exc
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for k, v in cfg.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    cfg_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rpf_type(path: Path) -> str:
    if not path.exists() or path.stat().st_size < 4:
        return "missing/invalid"
    return RPF_MAGIC.get(path.read_bytes()[:4], f"unknown magic {path.read_bytes()[:4]!r}")


def choose_rpf(home: Path, rpf_arg: str | None) -> Path:
    if rpf_arg:
        p = Path(rpf_arg)
        if not p.is_absolute():
            p = home / p
        p = p.resolve()
        if not p.exists():
            raise FileNotFoundError(f"RPF not found: {p}")
        if p.suffix.lower() != ".rpf":
            raise ValueError(f"Not an RPF: {p}")
        return p
    rpfs = sorted(home.glob("*.rpf"))
    if not rpfs:
        raise FileNotFoundError("No .rpf found beside the app. Put one there or pass --rpf.")
    if len(rpfs) > 1:
        raise RuntimeError("More than one .rpf found beside the app. Pass --rpf to choose one.")
    return rpfs[0].resolve()


def safe_extract(zip_path: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"Zip failed integrity at: {bad}")
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or name.startswith("../") or "/../" in name:
                raise ValueError(f"Unsafe zip path: {info.filename}")
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise ValueError(f"Unsafe zip target: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    return dest


def resolve_replacements(input_arg: str, work: Path) -> Path:
    p = Path(input_arg)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Replacement input not found: {p}")
    if p.is_dir():
        return p
    if p.is_file() and p.suffix.lower() == ".zip":
        return safe_extract(p, work / "unzipped" / p.stem)
    raise ValueError("Replacement input must be a folder or .zip")


def internal_path_for(path: Path, root: Path, cfg: dict) -> str:
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    for prefix in cfg.get("strip_prefixes", []):
        pre = str(prefix).replace("\\", "/").strip("/")
        if pre and rel.startswith(pre + "/"):
            rel = rel[len(pre) + 1:]
            break
    rel = re.sub(r"/+", "/", rel).strip("/")
    if not rel or rel.startswith("/") or "../" in rel:
        raise ValueError(f"Unsafe internal path: {rel}")
    return rel


def collect(root: Path, cfg: dict) -> list[Item]:
    blocked = {x.lower() for x in cfg.get("blocked_extensions", [])}
    excluded = set(cfg.get("exclude_names", []))
    items: list[Item] = []
    seen: set[str] = set()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name in excluded or p.suffix.lower() in blocked:
            continue
        if p.stat().st_size == 0:
            raise ValueError(f"Refusing empty replacement file: {p}")
        internal = internal_path_for(p, root, cfg)
        key = internal.lower()
        if key in seen:
            raise ValueError(f"Duplicate internal path: {internal}")
        seen.add(key)
        parent = Path(internal).parent.as_posix()
        items.append(Item(p.resolve(), internal, "" if parent == "." else parent, p.name, p.stat().st_size, sha256(p)))
    if not items:
        raise RuntimeError("No replacement files found.")
    return items


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", (s or "__root__").strip("/")).strip("_") or "__root__"


def cmd_display(parts: list[str]) -> str:
    return subprocess.list2cmdline(parts) if os.name == "nt" else " ".join(shlex.quote(x) for x in parts)


def make_jobs(items: list[Item], work: Path, writer: Path | None, rpf: Path, home: Path, cfg: dict) -> list[Job]:
    groups: dict[str, list[Item]] = {}
    for it in items:
        groups.setdefault(it.internal_dir, []).append(it)
    jobs: list[Job] = []
    imports = work / "directory_imports"
    if imports.exists():
        shutil.rmtree(imports)
    for internal_dir, group in sorted(groups.items()):
        import_dir = imports / slug(internal_dir)
        import_dir.mkdir(parents=True, exist_ok=True)
        for it in group:
            shutil.copy2(it.source, import_dir / it.file_name)
        if writer:
            target_dir = internal_dir or "/"
            values = {"writer": str(writer), "rpf": str(rpf), "internal_dir": target_dir, "import_dir": str(import_dir), "app_home": str(home)}
            rendered = cfg["writer"].get("command_template", DEFAULT_CONFIG["writer"]["command_template"]).format(**values)
            command = cmd_display(shlex.split(rendered, posix=(os.name != "nt")))
        else:
            command = f"PACKAGE ONLY: import {len(group)} file(s) into RPF folder {internal_dir or '/'}"
        jobs.append(Job(internal_dir, import_dir, len(group), command))
    return jobs


def write_manifest(items: list[Item], jobs: list[Job], out: Path) -> None:
    by_dir = {j.internal_dir: j for j in jobs}
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["internal_path", "internal_dir", "file_name", "size", "sha256", "source", "import_dir", "command"])
        for it in items:
            job = by_dir[it.internal_dir]
            w.writerow([it.internal_path, it.internal_dir or "/", it.file_name, it.size, it.sha256, str(it.source), str(job.import_dir), job.command])


def make_patch_zip(items: list[Item], jobs: list[Job], out: Path, rpf: Path, run_stamp: str, manifest: Path, commands: Path) -> Path:
    package = out / f"Code_Red_Syringe_PatchPackage_{rpf.stem}_{run_stamp}.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(manifest, "manifest.csv")
        z.write(commands, "commands.txt")
        z.writestr("README_PATCH_PACKAGE.txt", (
            f"Code Red Syringe patch package\nTarget RPF: {rpf.name}\nFiles: {len(items)}\nFolders: {len(jobs)}\n\n"
            "This package does not mean the RPF was modified. It is a verified import package.\n"
        ))
        for it in items:
            z.write(it.source, f"patch_files/{it.internal_path}")
        for job in jobs:
            for p in sorted(job.import_dir.glob("*")):
                if p.is_file():
                    z.write(p, f"directory_imports/{slug(job.internal_dir)}/{p.name}")
    with zipfile.ZipFile(package, "r") as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"Output zip failed integrity at: {bad}")
    return package


def hidden_win_flags():
    if os.name != "nt":
        return None, 0
    startup = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    startup.wShowWindow = 0
    return startup, getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_headless(jobs: list[Job], writer: Path, rpf: Path, home: Path, cfg: dict, log: Path) -> tuple[int, int, list[str]]:
    before = (rpf.stat().st_size, sha256(rpf)) if cfg["writer"].get("verify_archive_changed", True) else None
    startup, flags = hidden_win_flags() if cfg["writer"].get("hide_console_window", True) else (None, 0)
    timeout = int(cfg["writer"].get("timeout_seconds_per_directory", 300))
    injected_dirs = 0
    injected_files = 0
    failures: list[str] = []
    for job in jobs:
        target = job.internal_dir or "/"
        values = {"writer": str(writer), "rpf": str(rpf), "internal_dir": target, "import_dir": str(job.import_dir), "app_home": str(home)}
        rendered = cfg["writer"].get("command_template", DEFAULT_CONFIG["writer"]["command_template"]).format(**values)
        parts = shlex.split(rendered, posix=(os.name != "nt"))
        with log.open("a", encoding="utf-8") as f:
            f.write("COMMAND: " + cmd_display(parts) + "\n")
        proc = subprocess.run(parts, cwd=str(home), text=True, capture_output=True, timeout=timeout, startupinfo=startup, creationflags=flags)
        if proc.returncode != 0:
            failures.append(f"{target}: writer exit code {proc.returncode}")
            break
        injected_dirs += 1
        injected_files += job.item_count
    if before and (rpf.stat().st_size, sha256(rpf)) == before:
        failures.append("Writer finished, but RPF bytes did not change. Not counted as injected.")
    return injected_dirs, injected_files, failures


def build(args: argparse.Namespace) -> int:
    home = Path(args.app_home).resolve() if args.app_home else app_home()
    home.mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    run_stamp = stamp()
    out = home / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    work = home / WORK_DIR / run_stamp
    work.mkdir(parents=True, exist_ok=True)
    rpf = choose_rpf(home, args.rpf)
    replacements = resolve_replacements(args.replacements, work)
    writer = None
    if args.apply:
        if not cfg["writer"].get("enabled", False):
            raise RuntimeError("Headless writer is disabled in config. No external editor was launched and no RPF was changed.")
        exe = Path(cfg["writer"].get("executable", ""))
        writer = exe if exe.is_absolute() else home / exe
        if not writer.exists():
            raise RuntimeError(f"Configured writer not found: {writer}")
    items = collect(replacements, cfg)
    jobs = make_jobs(items, work, writer, rpf, home, cfg)
    manifest = out / f"{rpf.stem}_{run_stamp}_manifest.csv"
    commands = out / f"{rpf.stem}_{run_stamp}_commands.txt"
    log = out / f"Code_Red_Syringe_{run_stamp}.log"
    write_manifest(items, jobs, manifest)
    commands.write_text("\n".join(j.command for j in jobs) + "\n", encoding="utf-8")
    package = make_patch_zip(items, jobs, out, rpf, run_stamp, manifest, commands)
    backup = ""
    injected_files = 0
    failures: list[str] = []
    if args.apply and writer:
        backup_path = home / BACKUP_DIR / f"{rpf.stem}_{run_stamp}{rpf.suffix}.bak"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rpf, backup_path)
        backup = str(backup_path)
        _, injected_files, failures = run_headless(jobs, writer, rpf, home, cfg, log)
    print(f"{APP_NAME} {APP_VERSION}")
    print(f"RPF: {rpf}")
    print(f"RPF type: {rpf_type(rpf)}")
    print(f"Files mapped: {len(items)}")
    print(f"Directory jobs: {len(jobs)}")
    print(f"Patch package: {package}")
    print(f"Manifest: {manifest}")
    print(f"Commands: {commands}")
    print(f"Log: {log}")
    if backup:
        print(f"Backup: {backup}")
    if injected_files:
        print(f"Injected files: {injected_files}")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"- {f}")
    if not args.apply:
        print("Status: package-only. No RPF bytes changed.")
    return 1 if failures else 0


def self_test() -> int:
    root = Path(tempfile.mkdtemp(prefix="code_red_syringe_selftest_"))
    fake_rpf = root / "fake.rpf"
    fake_rpf.write_bytes(b"RPF6" + b"\0" * 128)
    repl = root / "changed_files" / "tune" / "level" / "territory"
    repl.mkdir(parents=True)
    (repl / "level.pop").write_text("self test\n", encoding="utf-8")
    ns = argparse.Namespace(replacements=str(root / "changed_files"), rpf=str(fake_rpf), app_home=str(root), apply=False)
    code = build(ns)
    print("Self-test passed: package builder works and no external editor was launched.")
    return code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=f"{APP_NAME} {APP_VERSION}: no-window RPF patch package builder.")
    p.add_argument("--replacements", "-i", help="Changed-files folder or zip.")
    p.add_argument("--rpf", help="Target RPF. Defaults to the only .rpf beside the app.")
    p.add_argument("--app-home", help="Override app home.")
    p.add_argument("--apply", action="store_true", help="Advanced: run configured headless writer. Disabled by default.")
    p.add_argument("--init-config", action="store_true", help="Create config and exit.")
    p.add_argument("--self-test", action="store_true", help="Run a no-editor self-test.")
    args = p.parse_args(argv)
    home = Path(args.app_home).resolve() if args.app_home else app_home()
    if args.self_test:
        return self_test()
    if args.init_config:
        load_config(home)
        print(f"Config ready: {home / CONFIG_NAME}")
        return 0
    if not args.replacements:
        p.error("--replacements is required unless --self-test or --init-config is used")
    try:
        return build(args)
    except Exception as exc:
        print(f"{APP_NAME} error: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
