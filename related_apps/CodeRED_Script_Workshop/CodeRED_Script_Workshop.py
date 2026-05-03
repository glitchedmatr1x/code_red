#!/usr/bin/env python3
"""Code RED Script Workshop extension.

Standalone extension for the script lane:
scan -> read -> open -> edit -> export decompiled/readable -> import queue -> recompile queue.

This tool is deliberately source-safe:
- text/source files are copied into edit/import/recompile workspaces
- compiled script binaries are fully read and exported as raw + readable reports
- binary bytecode decompile/recompile remains blocked until real compiler/decompiler proof exists
- Windows compile proof is generated as a task/helper instead of guessed
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-script-workshop-extension"
TEXT_SUFFIXES = {".c", ".h", ".hpp", ".cpp", ".cc", ".cxx", ".py", ".bat", ".cmd", ".ps1", ".txt", ".md", ".xml", ".ini", ".csv", ".json", ".toml", ".cfg"}
SOURCE_SUFFIXES = {".c", ".h", ".hpp", ".cpp", ".cc", ".cxx"}
COMPILED_SCRIPT_SUFFIXES = {".wsc", ".csc", ".xsc", ".sco", ".ysc"}
SCRIPTISH_SUFFIXES = TEXT_SUFFIXES | COMPILED_SCRIPT_SUFFIXES
SKIP_DIRS = {".git", ".vs", ".vscode", "__pycache__", "build", "dist", "x64", "x86", "Debug", "Release", "node_modules", ".pytest_cache", "scratch"}
ASCII_RE = re.compile(rb"[ -~]{4,}")
HASH_RE = re.compile(r"0x[0-9A-Fa-f]{8,16}")
NATIVE_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b")


@dataclass
class ScriptRecord:
    path: str
    suffix: str
    size: int
    sha1: str
    kind: str
    state: str
    full_read_export: str = ""
    open_target: str = ""
    edit_copy: str = ""
    decompiled_export: str = ""
    raw_export: str = ""
    import_queue: str = ""
    recompile_queue: str = ""
    native_tokens: list[str] = field(default_factory=list)
    hash_tokens: list[str] = field(default_factory=list)
    string_count: int = 0
    warning: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__).resolve()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "main.py").exists() and (candidate / "python_workbench.py").exists():
            return candidate
    # extension path: related_apps/CodeRED_Script_Workshop/CodeRED_Script_Workshop.py
    return Path(__file__).resolve().parents[2]


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def safe_name(rel: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", rel.replace("\\", "/").strip("/")) or "unnamed"


def open_path(path: Path) -> None:
    if sys.platform.startswith("win") and hasattr(os, "startfile"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def workspace_root(root: Path) -> Path:
    return root / "related_apps" / "CodeRED_Script_Workshop" / "workspace"


def ensure_workspace(root: Path) -> dict[str, Path]:
    base = workspace_root(root)
    folders = {
        "base": base,
        "scan": base / "scan",
        "read": base / "read",
        "edit": base / "edit",
        "decompiled_export": base / "decompiled_export",
        "import_queue": base / "import_queue",
        "recompile_queue": base / "recompile_queue",
        "proof": base / "proof",
        "new_script_templates": base / "new_script_templates",
        "raw_binary": base / "raw_binary",
    }
    for path in folders.values():
        path.mkdir(parents=True, exist_ok=True)
    return folders


def source_roots(root: Path) -> list[Path]:
    candidates = [
        root / "related_apps" / "code_red_sccl_attempt_bundle_v1" / "code_red_script_compile_lab_v1",
        root / "related_apps" / "Code_RED_ScriptHookRDR_AI_Menu",
        root / "tools",
        root / "docs",
        root / "research",
        root / "data" / "codered",
    ]
    return [p for p in candidates if p.exists()]


def iter_script_files(root: Path, extra_roots: Iterable[Path] = ()) -> Iterable[Path]:
    seen: set[str] = set()
    for base in [*source_roots(root), *extra_roots]:
        if not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            candidates = []
            for current, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for name in filenames:
                    candidates.append(Path(current) / name)
        for path in candidates:
            if path.suffix.lower() not in SCRIPTISH_SUFFIXES:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            yield path


def load_native_names(root: Path) -> set[str]:
    names: set[str] = set()
    for candidate in [root / "data" / "codered" / "native_database.json", root / "data" / "natives.json"]:
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            records = data.get("records") or data.get("natives") or data.get("items") or []
        else:
            records = data if isinstance(data, list) else []
        for item in records:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("native") or "").strip().upper()
            else:
                name = str(item).strip().upper()
            if name:
                names.add(name)
    return names


def text_tokens(text: str, native_names: set[str]) -> tuple[list[str], list[str]]:
    upper = {tok for tok in NATIVE_TOKEN_RE.findall(text.upper())}
    natives = sorted(tok for tok in upper if tok in native_names or tok.startswith(("TASK_", "CREATE_", "GET_", "SET_", "IS_", "AI_")))
    hashes = sorted(set(h.upper() for h in HASH_RE.findall(text)))
    return natives, hashes


def binary_strings(data: bytes, limit: int = 500) -> list[str]:
    out: list[str] = []
    for raw in ASCII_RE.findall(data):
        try:
            s = raw.decode("ascii", errors="ignore").strip()
        except Exception:
            continue
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build_templates(folders: dict[str, Path]) -> None:
    h = folders["new_script_templates"] / "codered_new_script_template.h"
    c = folders["new_script_templates"] / "codered_new_script_template.c"
    readme = folders["new_script_templates"] / "README_NEW_SCRIPTS.md"
    if not h.exists():
        write_text(h, "#pragma once\n\nvoid CodeRED_NewScript_Tick(void);\n")
    if not c.exists():
        write_text(c, "#include \"codered_new_script_template.h\"\n\nvoid CodeRED_NewScript_Tick(void)\n{\n    /* Add safe source-level script behavior here. */\n}\n")
    if not readme.exists():
        write_text(readme, "# New Script Templates\n\nStart source-first. Run Scan/Decode, then Compile Prep, then Windows Compile Proof.\n")


def scan_pipeline(root: Path, refresh: bool = False, extra_roots: Iterable[Path] = ()) -> dict:
    folders = ensure_workspace(root)
    native_names = load_native_names(root)
    if refresh:
        for key in ("scan", "read", "edit", "decompiled_export", "import_queue", "recompile_queue", "raw_binary"):
            if folders[key].exists():
                shutil.rmtree(folders[key])
            folders[key].mkdir(parents=True, exist_ok=True)
    build_templates(folders)
    records: list[ScriptRecord] = []
    import_queue: list[dict] = []
    recompile_queue: list[dict] = []

    for path in sorted(iter_script_files(root, extra_roots), key=lambda p: rel_to(p, root).lower()):
        rel = rel_to(path, root)
        suffix = path.suffix.lower()
        try:
            data = path.read_bytes()
        except Exception as exc:
            records.append(ScriptRecord(path=rel, suffix=suffix, size=0, sha1="", kind="unknown", state="read_failed", warning=str(exc)))
            continue
        digest = sha1_bytes(data)
        key = safe_name(rel)
        natives: list[str] = []
        hashes: list[str] = []
        string_count = 0
        kind = "source_text" if suffix in TEXT_SUFFIXES else "compiled_binary" if suffix in COMPILED_SCRIPT_SUFFIXES else "binary"
        state = "editable_source" if suffix in TEXT_SUFFIXES else "binary_readonly"
        full_read_export = ""
        open_target = ""
        edit_copy = ""
        decompiled = ""
        raw_export = ""
        import_item = ""
        recompile_item = ""

        if suffix in TEXT_SUFFIXES:
            text = data.decode("utf-8", errors="replace")
            natives, hashes = text_tokens(text, native_names)
            read_path = folders["read"] / f"{key}.fullread.txt"
            write_text(read_path, text)
            full_read_export = rel_to(read_path, root)
            edit_path = folders["edit"] / rel
            copy_file(path, edit_path)
            edit_copy = rel_to(edit_path, root)
            open_target = edit_copy
            decomp_path = folders["decompiled_export"] / f"{key}.decompiled_source.txt"
            write_text(decomp_path, "# Code RED source/decompiled export\n" + f"# Source: {rel}\n# SHA1: {digest}\n\n" + text)
            decompiled = rel_to(decomp_path, root)
            import_path = folders["import_queue"] / rel
            copy_file(path, import_path)
            import_item = rel_to(import_path, root)
            import_queue.append({"path": rel, "source": edit_copy, "import_queue": import_item, "state": "safe_text_import_candidate"})
            if suffix in SOURCE_SUFFIXES:
                rec_path = folders["recompile_queue"] / rel
                copy_file(path, rec_path)
                recompile_item = rel_to(rec_path, root)
                recompile_queue.append({"path": rel, "source": recompile_item, "native_tokens": natives, "hash_tokens": hashes, "state": "source_recompile_candidate"})
        else:
            raw_path = folders["raw_binary"] / rel
            copy_file(path, raw_path)
            raw_export = rel_to(raw_path, root)
            strings = binary_strings(data)
            string_count = len(strings)
            blob = "\n".join(strings)
            natives, hashes = text_tokens(blob, native_names)
            report_path = folders["decompiled_export"] / f"{key}.readable_binary_report.txt"
            write_text(report_path, textwrap.dedent(f"""
                # Code RED compiled script readable export

                Source: {rel}
                SHA1: {digest}
                Size: {len(data)}
                State: binary read-only until bytecode/compiler roundtrip proof passes.

                Native tokens: {', '.join(natives) if natives else 'none'}
                Hash tokens: {', '.join(hashes) if hashes else 'none'}
                String count: {len(strings)}

                ## Strings
                {chr(10).join('- ' + s for s in strings[:250])}
                """).strip() + "\n")
            full_read_export = rel_to(report_path, root)
            decompiled = full_read_export
            open_target = full_read_export

        records.append(ScriptRecord(
            path=rel,
            suffix=suffix,
            size=len(data),
            sha1=digest,
            kind=kind,
            state=state,
            full_read_export=full_read_export,
            open_target=open_target,
            edit_copy=edit_copy,
            decompiled_export=decompiled,
            raw_export=raw_export,
            import_queue=import_item,
            recompile_queue=recompile_item,
            native_tokens=natives,
            hash_tokens=hashes,
            string_count=string_count,
        ))

    # Manifests expected by Code RED script lanes.
    decode_manifest = []
    compile_manifest = []
    for rec in records:
        decode_manifest.append({
            "path": rec.path,
            "suffix": rec.suffix,
            "size": rec.size,
            "sha1": rec.sha1,
            "editable": rec.state == "editable_source",
            "kind": rec.kind,
            "state": rec.state,
            "full_read_export": rec.full_read_export,
            "decompiled_export": rec.decompiled_export,
            "native_tokens": rec.native_tokens,
            "hash_tokens": rec.hash_tokens,
        })
        if rec.recompile_queue:
            compile_manifest.append({
                "path": rec.path,
                "compile_state": "source_compile_candidate",
                "edit_state": "safe_edit_copy",
                "source": rec.recompile_queue,
                "native_tokens": rec.native_tokens,
                "hash_tokens": rec.hash_tokens,
            })

    data_dir = root / "data" / "codered"
    logs_dir = root / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    write_json(data_dir / "script_workshop_decode_manifest.json", decode_manifest)
    write_json(data_dir / "script_workshop_compile_candidates.json", compile_manifest)
    write_json(folders["import_queue"] / "IMPORT_QUEUE.json", import_queue)
    write_json(folders["recompile_queue"] / "RECOMPILE_QUEUE.json", recompile_queue)
    write_json(data_dir / "script_workshop_extension_manifest.json", [asdict(r) for r in records])

    csv_path = data_dir / "script_workshop_extension_manifest.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["path", "suffix", "kind", "state", "size", "sha1", "full_read_export", "open_target", "edit_copy", "decompiled_export", "import_queue", "recompile_queue", "native_tokens", "hash_tokens", "warning"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            row = asdict(rec)
            writer.writerow({k: "|".join(row[k]) if isinstance(row.get(k), list) else row.get(k, "") for k in fields})

    proof = {
        "version": VERSION,
        "generated_utc": utc_now(),
        "root": str(root),
        "workspace": str(folders["base"]),
        "records": len(records),
        "editable": sum(1 for r in records if r.state == "editable_source"),
        "compiled_binary_readonly": sum(1 for r in records if r.state == "binary_readonly"),
        "import_queue": len(import_queue),
        "recompile_queue": len(recompile_queue),
        "new_script_templates": len(list(folders["new_script_templates"].glob("*"))),
        "outputs": {
            "extension_manifest_json": rel_to(data_dir / "script_workshop_extension_manifest.json", root),
            "extension_manifest_csv": rel_to(csv_path, root),
            "decode_manifest": rel_to(data_dir / "script_workshop_decode_manifest.json", root),
            "compile_candidates": rel_to(data_dir / "script_workshop_compile_candidates.json", root),
            "import_queue": rel_to(folders["import_queue"] / "IMPORT_QUEUE.json", root),
            "recompile_queue": rel_to(folders["recompile_queue"] / "RECOMPILE_QUEUE.json", root),
        },
    }
    write_json(logs_dir / "CodeRED_Script_Workshop_Extension_Report.json", proof)
    write_text(logs_dir / "CodeRED_Script_Workshop_Extension_Report.md", report_markdown(proof))
    return proof


def report_markdown(proof: dict) -> str:
    return textwrap.dedent(f"""
    # Code RED Script Workshop Extension Report

    Generated: {proof['generated_utc']}
    Version: `{proof['version']}`

    ## Summary

    - Records: `{proof['records']}`
    - Editable source/text files: `{proof['editable']}`
    - Compiled binary read-only files: `{proof['compiled_binary_readonly']}`
    - Import queue items: `{proof['import_queue']}`
    - Recompile queue items: `{proof['recompile_queue']}`
    - New script templates: `{proof['new_script_templates']}`

    ## Safety

    Source/text files can be edited through safe workspace copies. Compiled script binaries are read/exported but remain blocked from bytecode roundtrip until Windows compiler/decompiler proof exists.
    """).strip() + "\n"


def compile_proof_plan(root: Path) -> dict:
    folders = ensure_workspace(root)
    bat = folders["proof"] / "Run_Windows_Compile_Proof.bat"
    ps1 = folders["proof"] / "Run_Windows_Compile_Proof.ps1"
    sh = folders["proof"] / "run_linux_compile_prep_check.sh"
    write_text(bat, "@echo off\r\nsetlocal\r\ncd /d %~dp0\\..\\..\\..\\..\r\necho Code RED Script Workshop Windows Compile Proof\r\npy -3 related_apps\\CodeRED_Script_Workshop\\CodeRED_Script_Workshop.py scan --refresh\r\npy -3 tools\\codered_script_compile_validation.py\r\nif errorlevel 1 exit /b 1\r\necho Review workspace\\recompile_queue before enabling real compiler output promotion.\r\nendlocal\r\n")
    write_text(ps1, "$ErrorActionPreference = 'Stop'\nSet-Location (Resolve-Path "$PSScriptRoot\\..\\..\\..\\..")\npy -3 related_apps\\CodeRED_Script_Workshop\\CodeRED_Script_Workshop.py scan --refresh\npy -3 tools\\codered_script_compile_validation.py\nWrite-Host 'Review recompile queue before output promotion.'\n")
    write_text(sh, "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/../../../..\"\npython3 related_apps/CodeRED_Script_Workshop/CodeRED_Script_Workshop.py scan --refresh\npython3 -m py_compile related_apps/CodeRED_Script_Workshop/CodeRED_Script_Workshop.py\necho 'Linux prep check passed. Windows compiler proof still runs on Windows.'\n")
    try:
        sh.chmod(0o755)
    except Exception:
        pass
    plan = {"windows_bat": rel_to(bat, root), "windows_ps1": rel_to(ps1, root), "linux_sh": rel_to(sh, root)}
    write_json(folders["proof"] / "compile_proof_plan.json", plan)
    return plan


def run_all(root: Path, refresh: bool) -> dict:
    proof = scan_pipeline(root, refresh=refresh)
    proof["compile_proof_plan"] = compile_proof_plan(root)
    write_json(root / "logs" / "CodeRED_Script_Workshop_Extension_Report.json", proof)
    write_text(root / "logs" / "CodeRED_Script_Workshop_Extension_Report.md", report_markdown(proof))
    return proof


def build_gui(root: Path):
    import tkinter as tk
    from tkinter import messagebox, ttk

    win = tk.Tk()
    win.title("Code RED Script Workshop")
    win.geometry("980x640")
    folders = ensure_workspace(root)

    status = tk.StringVar(value="Ready. Run Scan Scripts to build the workspace.")
    text = tk.Text(win, wrap="word")
    text.pack(fill="both", expand=True, padx=10, pady=10)

    def log(msg: str) -> None:
        text.insert("end", msg.rstrip() + "\n")
        text.see("end")
        status.set(msg.rstrip())
        win.update_idletasks()

    def do_scan(refresh: bool = False) -> None:
        try:
            proof = run_all(root, refresh=refresh)
            log(report_markdown(proof))
        except Exception as exc:
            messagebox.showerror("Script Workshop", str(exc))
            log(f"ERROR: {exc}")

    def do_open(key: str) -> None:
        try:
            open_path(folders[key])
        except Exception as exc:
            messagebox.showerror("Open folder", str(exc))

    top = ttk.Frame(win)
    top.pack(fill="x", padx=10, pady=(10, 0))
    ttk.Button(top, text="Scan Scripts", command=lambda: do_scan(False)).pack(side="left", padx=3)
    ttk.Button(top, text="Refresh/Rebuild", command=lambda: do_scan(True)).pack(side="left", padx=3)
    ttk.Button(top, text="Open Edit", command=lambda: do_open("edit")).pack(side="left", padx=3)
    ttk.Button(top, text="Open Export", command=lambda: do_open("decompiled_export")).pack(side="left", padx=3)
    ttk.Button(top, text="Open Import Queue", command=lambda: do_open("import_queue")).pack(side="left", padx=3)
    ttk.Button(top, text="Open Recompile Queue", command=lambda: do_open("recompile_queue")).pack(side="left", padx=3)
    ttk.Button(top, text="Open Proof", command=lambda: do_open("proof")).pack(side="left", padx=3)
    ttk.Label(win, textvariable=status).pack(fill="x", padx=10, pady=(0, 10))
    text.insert("end", "Code RED Script Workshop\n\nWorkflow: scan -> read -> open -> edit -> export -> import queue -> recompile queue.\n\n")
    return win


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Code RED Script Workshop extension")
    p.add_argument("command", nargs="?", default="gui", choices=["gui", "scan", "refresh", "open-edit", "open-export", "open-import", "open-recompile", "open-proof", "compile-proof-plan"], help="Action to run")
    p.add_argument("--root", default=None, help="Code RED root")
    p.add_argument("--refresh", action="store_true", help="Rebuild generated workspace folders")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.root).resolve() if args.root else find_repo_root()
    folders = ensure_workspace(root)
    if args.command == "gui":
        app = build_gui(root)
        app.mainloop()
        return 0
    if args.command in {"scan", "refresh"}:
        proof = run_all(root, refresh=args.refresh or args.command == "refresh")
        print(report_markdown(proof))
        return 0
    if args.command == "compile-proof-plan":
        print(json.dumps(compile_proof_plan(root), indent=2))
        return 0
    open_map = {
        "open-edit": "edit",
        "open-export": "decompiled_export",
        "open-import": "import_queue",
        "open-recompile": "recompile_queue",
        "open-proof": "proof",
    }
    open_path(folders[open_map[args.command]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
