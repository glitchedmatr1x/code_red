#!/usr/bin/env python3
"""Safe Code RED WSC edit workflow.

This is source-first on purpose:
- compiled .wsc files are preserved and inspected, not falsely decompiled;
- editable source lives in build/wsc_edit/<name>/src/main.c;
- SC-CL compiles source to XSC/XSA, then Code RED converts XSC to WSC;
- packing writes a copied RPF under build/, never the live game folder.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import string
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_RPF = ROOT.parent / "game" / "content.rpf"
DEFAULT_WORK_ROOT = ROOT / "build" / "wsc_edit"
DEFAULT_LOG_ROOT = ROOT / "logs" / "wsc_edit"
DEFAULT_INCLUDE = ROOT / "script_compiling" / "sccl" / "projects" / "vehicle_menu_probe" / "include"
WORKBENCH = ROOT / "python_workbench.py"
RPF_UTILS = ROOT / "tools" / "codered_rpf_utils.py"
OVERLAY_BUILDER = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
XSC_TO_WSC = ROOT / "tools" / "codered_xsc_to_wsc_candidate.py"
PROTECTED_WRITE_ROOTS = [
    ROOT.parent / "game",
    ROOT.parent / "RDR-SteamGG.NET",
]


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def sha1_file(path: Path) -> str:
    return sha1_bytes(path.read_bytes())


def safe_name(text: str) -> str:
    keep = string.ascii_letters + string.digits + "_.-"
    out = "".join(ch if ch in keep else "_" for ch in text.strip())
    return out.strip("._") or "wsc_edit"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def path_is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def assert_safe_pack_output(output: Path, source_rpf: Path) -> None:
    output_resolved = output.resolve()
    source_resolved = source_rpf.resolve()
    if output_resolved == source_resolved:
        raise ValueError(f"Refusing to overwrite source archive: {output_resolved}")
    for protected in PROTECTED_WRITE_ROOTS:
        if path_is_under(output_resolved, protected):
            raise ValueError(f"Refusing to write packed RPF inside protected game folder: {output_resolved}")


def find_sccl() -> Path:
    candidates = [
        Path(p) for p in [str(Path.cwd() / "SC-CL.exe"), str(Path.cwd() / "script_compiling" / "sccl" / "output" / "SC-CL.exe")]
    ]
    if "SCCL_EXE" in os.environ:
        candidates.insert(0, Path(os.environ["SCCL_EXE"]))
    candidates.extend(
        [
            ROOT / "script_compiling" / "sccl" / "output" / "SC-CL.exe",
            ROOT / "SC-CL-master" / "bin" / "SC-CL.exe",
            ROOT / "SC-CL-master" / "llvm-14.0.0.src" / "tools" / "clang" / "tools" / "extra" / "SC-CL" / "bin" / "SC-CL.exe",
            ROOT / "resources" / "SC-CL_DROP_HERE" / "SC-CL.exe",
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("SC-CL.exe not found. Set SCCL_EXE or stage SC-CL under SC-CL-master/bin.")


def swap32(data: bytes) -> bytes:
    out = bytearray()
    words = len(data) // 4
    for i in range(words):
        out.extend(data[i * 4 : i * 4 + 4][::-1])
    out.extend(data[words * 4 :])
    return bytes(out)


def inspect_blob(data: bytes) -> dict:
    strings = []
    current = bytearray()
    for byte in data:
        if 32 <= byte <= 126:
            current.append(byte)
        else:
            if len(current) >= 4:
                strings.append(current.decode("ascii", errors="ignore"))
            current.clear()
        if len(strings) >= 80:
            break
    return {
        "size": len(data),
        "sha1": sha1_bytes(data),
        "head_hex_32": data[:32].hex(" ").upper(),
        "looks_like_wsc_rsc85": data[:4] == b"RSC\x85",
        "looks_like_xsc_swapped": data[:4] == b"\x85CSR",
        "strings_preview": strings[:40],
        "boundary": "No proven bytecode-to-source decompiler is used. This is binary inspection only.",
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_manifest(workspace: Path) -> dict:
    manifest = workspace / "codered_wsc_workspace.json"
    if not manifest.exists():
        raise FileNotFoundError(f"Missing workspace manifest: {manifest}")
    return json.loads(manifest.read_text(encoding="utf-8"))


def write_manifest(workspace: Path, data: dict) -> None:
    write_json(workspace / "codered_wsc_workspace.json", data)


def make_source_template(name: str, archive_path: str) -> str:
    return f"""/*
   Code RED WSC edit source: {name}
   Target archive path: {archive_path}

   This source compiles through SC-CL into an RDR #SC script, then Code RED
   converts the compiled XSC bytes into a WSC/RSC85 resource blob.
*/

#include "../include/types.h"
#include "../include/constants.h"
#include "../include/intrinsics.h"
#include "../include/natives.h"
#include "../include/RDR/natives32.h"
#include "../include/RDR/consts32.h"

void main(void)
{{
    while (true)
    {{
        WAIT(0);
    }}
}}
"""


def cmd_init(args: argparse.Namespace) -> int:
    name = safe_name(args.name)
    workspace = Path(args.workspace) if args.workspace else DEFAULT_WORK_ROOT / name
    source_rpf = Path(args.source_rpf)
    archive_path = args.archive_path.replace("\\", "/")
    workspace.mkdir(parents=True, exist_ok=True)

    utils = load_module("codered_rpf_utils_workflow", RPF_UTILS)
    info = utils.parse_archive(source_rpf)
    entry = utils.find_entry(info, archive_path)
    original = utils.extract_entry_payload(utils.load_backend(), source_rpf, entry)
    original_path = workspace / "original" / archive_path.removeprefix("root/")
    original_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(original)

    include_dir = workspace / "src" / "include"
    if include_dir.exists():
        shutil.rmtree(include_dir)
    shutil.copytree(DEFAULT_INCLUDE, include_dir)
    src = workspace / "src" / "main.c"
    src.write_text(make_source_template(name, archive_path), encoding="utf-8")

    report = inspect_blob(original)
    write_json(workspace / "original" / "binary_inspection.json", report)
    (workspace / "README_WSC_EDIT.md").write_text(
        f"# Code RED WSC Edit Workspace\n\n"
        f"- Name: `{name}`\n"
        f"- Source RPF: `{source_rpf}`\n"
        f"- Archive path: `{archive_path}`\n"
        f"- Edit source: `src/main.c`\n"
        f"- Original binary: `{original_path}`\n\n"
        "Commands:\n\n"
        "```bat\n"
        f"python tools\\codered_wsc_edit_workflow.py compile --workspace \"{workspace}\"\n"
        f"python tools\\codered_wsc_edit_workflow.py pack --workspace \"{workspace}\" --write\n"
        "```\n\n"
        "Boundary: this workspace does not pretend to decompile WSC bytecode into original source.\n",
        encoding="utf-8",
    )
    manifest = {
        "version": "1.0.0",
        "created_utc": utc_now(),
        "name": name,
        "workspace": str(workspace),
        "source_rpf": str(source_rpf),
        "archive_path": archive_path,
        "source": str(src),
        "original_wsc": str(original_path),
        "original_sha1": sha1_bytes(original),
        "include_dir": str(include_dir),
        "compiled_dir": str(workspace / "compiled"),
        "packed_rpf": str(workspace / "packed" / "content.rpf"),
        "status": "initialized",
    }
    write_manifest(workspace, manifest)
    print(json.dumps({"status": "initialized", "workspace": str(workspace), "source": str(src)}, indent=2))
    return 0


def cmd_decompile(args: argparse.Namespace) -> int:
    return cmd_init(args)


def newest_file(root: Path, suffix: str) -> Path:
    matches = list(root.rglob(f"*{suffix}"))
    if not matches:
        raise FileNotFoundError(f"No {suffix} output found under {root}")
    return max(matches, key=lambda p: p.stat().st_mtime)


def cmd_compile(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manifest = load_manifest(workspace)
    src = Path(args.source) if args.source else Path(manifest["source"])
    out_dir = workspace / "compiled"
    if out_dir.exists() and args.clean:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sccl = find_sccl()
    name = safe_name(args.name or manifest["name"])
    include_dir = Path(manifest["include_dir"])
    out_arg = str(out_dir) + "\\"
    command = [
        str(sccl),
        "-target=RDR_#SC",
        "-platform=X360",
        "-emit-asm",
        f"-out-dir={out_arg}",
        f"-name={name}",
        f"-extra-arg=-I{include_dir}",
        str(src),
    ]
    proc = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=180)
    log = {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout.splitlines(),
        "stderr": proc.stderr.splitlines(),
    }
    write_json(out_dir / "sccl_compile_log.json", log)
    if proc.returncode != 0:
        print(json.dumps({"status": "compile_failed", "log": str(out_dir / "sccl_compile_log.json")}, indent=2))
        return proc.returncode or 1

    xsc = newest_file(out_dir, ".xsc")
    xsa = newest_file(out_dir, ".xsa") if list(out_dir.rglob("*.xsa")) else None
    wsc = out_dir / f"{name}.wsc"
    converted = swap32(xsc.read_bytes())
    wsc.write_bytes(converted)
    if converted[:4] != b"RSC\x85":
        raise RuntimeError(f"Converted WSC does not have RSC85 header: {wsc}")
    report = {
        "status": "compiled",
        "source": str(src),
        "xsc": str(xsc),
        "xsa": str(xsa) if xsa else "",
        "wsc": str(wsc),
        "xsc_sha1": sha1_file(xsc),
        "wsc_sha1": sha1_file(wsc),
        "wsc_inspection": inspect_blob(converted),
    }
    write_json(out_dir / "wsc_compile_report.json", report)
    manifest.update({"compiled_wsc": str(wsc), "compiled_xsc": str(xsc), "compiled_xsa": str(xsa) if xsa else "", "status": "compiled"})
    write_manifest(workspace, manifest)
    print(json.dumps({"status": "compiled", "wsc": str(wsc), "report": str(out_dir / "wsc_compile_report.json")}, indent=2))
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manifest = load_manifest(workspace)
    wsc = Path(args.wsc) if args.wsc else Path(manifest.get("compiled_wsc") or "")
    if not wsc.exists():
        raise FileNotFoundError(f"Compiled WSC not found: {wsc}")
    if wsc.read_bytes()[:4] != b"RSC\x85":
        raise ValueError(f"Refusing to pack non-WSC/RSC85 payload: {wsc}")
    source_rpf = Path(args.source_rpf or manifest["source_rpf"])
    output = Path(args.out) if args.out else Path(manifest["packed_rpf"])
    assert_safe_pack_output(output, source_rpf)
    log_dir = DEFAULT_LOG_ROOT / safe_name(manifest["name"])
    empty_zip = workspace / "empty_overlay_source.zip"
    with zipfile.ZipFile(empty_zip, "w"):
        pass

    builder = load_module("codered_content_overlay_for_wsc", OVERLAY_BUILDER)
    profile = f"manual_wsc_{safe_name(manifest['name'])}"
    builder.PROFILES[profile] = {
        "description": "Manual Code RED WSC replacement from source-first WSC edit workflow.",
        "include": [],
        "replace": [],
        "overrides": [
            {
                "local_file": str(wsc),
                "archive_path": manifest["archive_path"],
                "operation": "replace",
                "allow_resource_replace": True,
            }
        ],
    }
    report = builder.build_overlay(empty_zip, source_rpf, output, log_dir, profile, bool(args.write))
    builder.write_reports(report, log_dir)
    manifest.update({"packed_rpf": str(output), "pack_report": str(log_dir / f"{profile}_overlay_report.json"), "status": "packed" if args.write else "pack_dry_run"})
    write_manifest(workspace, manifest)
    print(json.dumps({"status": report["status"], "mode": report["mode"], "output": str(output), "report": manifest["pack_report"]}, indent=2))
    return 0 if report["status"] == "pass" else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.input)
    report = inspect_blob(path.read_bytes())
    out = Path(args.out) if args.out else DEFAULT_LOG_ROOT / f"{safe_name(path.stem)}_inspection.json"
    write_json(out, {"input": str(path), **report})
    print(json.dumps({"status": "inspected", "report": str(out), "looks_like_wsc_rsc85": report["looks_like_wsc_rsc85"]}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe source-first Code RED WSC edit workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a safe WSC edit workspace from an RPF entry.")
    init.add_argument("--name", required=True)
    init.add_argument("--archive-path", required=True)
    init.add_argument("--source-rpf", default=str(DEFAULT_SOURCE_RPF))
    init.add_argument("--workspace", default="")
    init.set_defaults(func=cmd_init)

    decompile = sub.add_parser("decompile", help="Extract and inspect WSC, then create an editable source scaffold. Does not recover original source.")
    decompile.add_argument("--name", required=True)
    decompile.add_argument("--archive-path", required=True)
    decompile.add_argument("--source-rpf", default=str(DEFAULT_SOURCE_RPF))
    decompile.add_argument("--workspace", default="")
    decompile.set_defaults(func=cmd_decompile)

    compile_cmd = sub.add_parser("compile", help="Compile workspace src/main.c to XSC and WSC.")
    compile_cmd.add_argument("--workspace", required=True)
    compile_cmd.add_argument("--source", default="")
    compile_cmd.add_argument("--name", default="")
    compile_cmd.add_argument("--clean", action="store_true")
    compile_cmd.set_defaults(func=cmd_compile)

    recompile = sub.add_parser("recompile", help="Alias for compile: compile workspace source to XSC and WSC.")
    recompile.add_argument("--workspace", required=True)
    recompile.add_argument("--source", default="")
    recompile.add_argument("--name", default="")
    recompile.add_argument("--clean", action="store_true")
    recompile.set_defaults(func=cmd_compile)

    pack = sub.add_parser("pack", help="Pack compiled WSC into a copied RPF under build/.")
    pack.add_argument("--workspace", required=True)
    pack.add_argument("--wsc", default="")
    pack.add_argument("--source-rpf", default="")
    pack.add_argument("--out", default="")
    pack.add_argument("--write", action="store_true", help="Write copied RPF. Default is dry-run.")
    pack.set_defaults(func=cmd_pack)

    inspect = sub.add_parser("inspect", help="Inspect a WSC/XSC binary without pretending to decompile it.")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--out", default="")
    inspect.set_defaults(func=cmd_inspect)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc) or repr(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
