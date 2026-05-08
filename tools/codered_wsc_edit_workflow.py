#!/usr/bin/env python3
"""Safe Code RED WSC edit workflow.

Default lane: existing-file binary edit.
- extract the original .wsc from an RPF;
- inspect header/body/string offsets without pretending to decompile source;
- apply controlled byte or length-preserving string patches to a copy;
- pack the edited original-derived WSC into a copied RPF.

Secondary lane: full replacement / source-built replacement.
- compile new source through SC-CL to XSC/WSC;
- replace a selected WSC entry with that newly built WSC.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
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
ADVANCED_SOURCE_REQUIREMENTS = [
    "WSC/RSC85 internal section table parser with validated offsets, lengths, alignment, and checksums",
    "RDR WSC bytecode decoder with opcode table, operand formats, jump/call targets, locals, globals, and native call metadata",
    "control-flow graph and function boundary recovery",
    "IR-to-C or pseudocode lifter that can round-trip enough structure for edits",
    "assembler/recompiler from edited IR/source back to valid WSC bytecode",
    "container rebuilder that can expand strings/code and update all affected section offsets, lengths, relocations, and resource metadata",
    "runtime validation corpus proving rebuilt WSCs boot and execute beyond trivial string/byte patches",
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


def parse_int(text: str) -> int:
    return int(text, 0)


def clean_hex(text: str) -> bytes:
    compact = re.sub(r"[^0-9a-fA-F]", "", text)
    if len(compact) % 2:
        raise ValueError(f"Hex string has an odd number of digits: {text}")
    return bytes.fromhex(compact)


def hex_bytes(data: bytes, limit: int | None = None) -> str:
    sample = data if limit is None else data[:limit]
    return sample.hex(" ").upper()


def extract_printable_strings(data: bytes, min_len: int = 4, limit: int = 0) -> list[dict]:
    strings = []
    current = bytearray()
    start = 0
    for idx, byte in enumerate(data):
        if 32 <= byte <= 126:
            if not current:
                start = idx
            current.append(byte)
        else:
            if len(current) >= min_len:
                text = current.decode("ascii", errors="ignore")
                strings.append({"offset": start, "offset_hex": f"0x{start:X}", "length": len(current), "text": text})
                if limit and len(strings) >= limit:
                    return strings
            current.clear()
    if len(current) >= min_len:
        text = current.decode("ascii", errors="ignore")
        strings.append({"offset": start, "offset_hex": f"0x{start:X}", "length": len(current), "text": text})
    return strings[:limit] if limit else strings


def section_candidates(data: bytes) -> list[dict]:
    candidates = []
    if not data:
        return candidates
    header_len = min(16, len(data))
    candidates.append({
        "name": "rsc85_header",
        "offset": 0,
        "offset_hex": "0x0",
        "size": header_len,
        "sha1": sha1_bytes(data[:header_len]),
        "note": "Known outer resource header bytes only; not a source-code section.",
    })
    if len(data) > header_len:
        body = data[header_len:]
        candidates.append({
            "name": "resource_body",
            "offset": header_len,
            "offset_hex": f"0x{header_len:X}",
            "size": len(body),
            "sha1": sha1_bytes(body),
            "note": "Remaining WSC payload. Internal bytecode layout is not rebuilt by this tool.",
        })
    page = 0x1000
    for offset in range(0, len(data), page):
        chunk = data[offset:offset + page]
        if any(chunk):
            candidates.append({
                "name": f"page_{offset // page:04d}",
                "offset": offset,
                "offset_hex": f"0x{offset:X}",
                "size": len(chunk),
                "sha1": sha1_bytes(chunk),
                "nonzero_bytes": sum(1 for b in chunk if b),
                "note": "4KB page candidate for navigation and diffs; not a proven script section.",
            })
    return candidates


def inspect_blob(data: bytes, string_limit: int = 80) -> dict:
    header = data[:16]
    strings = []
    for row in extract_printable_strings(data, min_len=4, limit=string_limit):
        strings.append(row["text"])
    return {
        "size": len(data),
        "sha1": sha1_bytes(data),
        "head_hex_32": hex_bytes(data, 32),
        "looks_like_wsc_rsc85": data[:4] == b"RSC\x85",
        "looks_like_xsc_swapped": data[:4] == b"\x85CSR",
        "header": {
            "magic_hex": hex_bytes(header[:4]),
            "magic_ascii": header[:3].decode("ascii", errors="ignore") if len(header) >= 3 else "",
            "u32_be": [int.from_bytes(header[i:i + 4], "big") for i in range(0, len(header), 4) if len(header[i:i + 4]) == 4],
            "u32_le": [int.from_bytes(header[i:i + 4], "little") for i in range(0, len(header), 4) if len(header[i:i + 4]) == 4],
        },
        "body": {
            "offset": min(16, len(data)),
            "offset_hex": f"0x{min(16, len(data)):X}",
            "size": max(0, len(data) - 16),
            "sha1": sha1_bytes(data[16:]) if len(data) > 16 else "",
        },
        "section_candidates": section_candidates(data)[:32],
        "strings": extract_printable_strings(data, min_len=4, limit=string_limit),
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


def extract_original_from_rpf(source_rpf: Path, archive_path: str) -> bytes:
    utils = load_module("codered_rpf_utils_workflow", RPF_UTILS)
    info = utils.parse_archive(source_rpf)
    entry = utils.find_entry(info, archive_path)
    return utils.extract_entry_payload(utils.load_backend(), source_rpf, entry)


def cmd_init(args: argparse.Namespace) -> int:
    name = safe_name(args.name)
    workspace = Path(args.workspace) if args.workspace else DEFAULT_WORK_ROOT / name
    source_rpf = Path(args.source_rpf)
    archive_path = args.archive_path.replace("\\", "/")
    workspace.mkdir(parents=True, exist_ok=True)

    original = extract_original_from_rpf(source_rpf, archive_path)
    if original[:4] != b"RSC\x85":
        raise ValueError(f"Extracted entry is not a WSC/RSC85 payload: {archive_path}")

    original_path = workspace / "original" / archive_path.removeprefix("root/")
    edited_path = workspace / "edited" / original_path.name
    original_path.parent.mkdir(parents=True, exist_ok=True)
    edited_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(original)
    edited_path.write_bytes(original)

    report = inspect_blob(original)
    write_json(workspace / "original" / "binary_inspection.json", report)
    write_json(workspace / "strings.json", {"source": str(original_path), "strings": report["strings"]})
    write_json(workspace / "patches.json", {"patches": [], "note": "Use replace-string or patch-bytes to add controlled edits."})
    (workspace / "README_WSC_BINARY_EDIT.md").write_text(
        f"# Code RED WSC Binary Edit Workspace\n\n"
        f"- Name: `{name}`\n"
        f"- Source RPF: `{source_rpf}`\n"
        f"- Archive path: `{archive_path}`\n"
        f"- Original WSC: `{original_path}`\n"
        f"- Edited WSC: `{edited_path}`\n\n"
        "This workspace edits a copy of the original WSC. It does not generate `src/main.c` and does not replace the script with a blank source-built payload.\n\n"
        "Useful commands:\n\n"
        "```bat\n"
        f"python tools\\codered_wsc_edit_workflow.py strings --workspace \"{workspace}\"\n"
        f"python tools\\codered_wsc_edit_workflow.py replace-string --workspace \"{workspace}\" --find OLD --replace NEW\n"
        f"python tools\\codered_wsc_edit_workflow.py patch-bytes --workspace \"{workspace}\" --offset 0x20 --expected-hex AA --hex BB\n"
        f"python tools\\codered_wsc_edit_workflow.py pack --workspace \"{workspace}\" --write\n"
        "```\n\n"
        "Expanded string replacement is refused unless a future container rebuilder is implemented.\n",
        encoding="utf-8",
    )
    manifest = {
        "version": "2.0.0",
        "mode": "binary_edit",
        "created_utc": utc_now(),
        "name": name,
        "workspace": str(workspace),
        "source_rpf": str(source_rpf),
        "archive_path": archive_path,
        "original_wsc": str(original_path),
        "edited_wsc": str(edited_path),
        "active_wsc": str(edited_path),
        "original_sha1": sha1_bytes(original),
        "edited_sha1": sha1_bytes(original),
        "packed_rpf": str(workspace / "packed" / "content.rpf"),
        "status": "binary_edit_initialized",
    }
    write_manifest(workspace, manifest)
    print(json.dumps({"status": "binary_edit_initialized", "workspace": str(workspace), "edited_wsc": str(edited_path)}, indent=2))
    return 0


def cmd_full_replace_init(args: argparse.Namespace) -> int:
    name = safe_name(args.name)
    workspace = Path(args.workspace) if args.workspace else DEFAULT_WORK_ROOT / name
    source_rpf = Path(args.source_rpf)
    archive_path = args.archive_path.replace("\\", "/")
    workspace.mkdir(parents=True, exist_ok=True)

    original = extract_original_from_rpf(source_rpf, archive_path)
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
        "mode": "source_built_replacement",
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
    print(json.dumps({"status": "source_replacement_initialized", "workspace": str(workspace), "source": str(src)}, indent=2))
    return 0


def cmd_decompile(args: argparse.Namespace) -> int:
    return cmd_init(args)


def workspace_wsc_path(manifest: dict, explicit: str = "") -> Path:
    if explicit:
        return Path(explicit)
    for key in ("active_wsc", "edited_wsc", "compiled_wsc", "original_wsc"):
        value = manifest.get(key)
        if value:
            return Path(value)
    raise FileNotFoundError("No WSC path is available in the workspace manifest.")


def append_patch_record(workspace: Path, record: dict) -> None:
    patches_path = workspace / "patches.json"
    data = {"patches": []}
    if patches_path.exists():
        data = json.loads(patches_path.read_text(encoding="utf-8"))
    data.setdefault("patches", []).append(record)
    write_json(patches_path, data)


def write_edited_workspace_wsc(workspace: Path, manifest: dict, data: bytes, record: dict) -> Path:
    edited = Path(manifest["edited_wsc"])
    if data[:4] != b"RSC\x85":
        raise ValueError("Refusing to write edited WSC because the RSC85 header was not preserved.")
    edited.parent.mkdir(parents=True, exist_ok=True)
    edited.write_bytes(data)
    manifest.update({
        "active_wsc": str(edited),
        "edited_sha1": sha1_bytes(data),
        "edited_size": len(data),
        "status": "binary_edited",
    })
    write_manifest(workspace, manifest)
    append_patch_record(workspace, {**record, "edited_wsc": str(edited), "edited_sha1": sha1_bytes(data), "utc": utc_now()})
    write_json(workspace / "edited" / "binary_inspection.json", inspect_blob(data))
    return edited


def cmd_strings(args: argparse.Namespace) -> int:
    if args.workspace:
        workspace = Path(args.workspace)
        manifest = load_manifest(workspace)
        source = workspace_wsc_path(manifest, args.input)
        default_out = workspace / "strings.json"
    else:
        if not args.input:
            raise ValueError("strings requires --workspace or --input")
        source = Path(args.input)
        default_out = DEFAULT_LOG_ROOT / f"{safe_name(source.stem)}_strings.json"
    data = source.read_bytes()
    rows = extract_printable_strings(data, min_len=args.min_len, limit=args.limit)
    out = Path(args.out) if args.out else default_out
    write_json(out, {"input": str(source), "count": len(rows), "strings": rows})
    print(json.dumps({"status": "strings_extracted", "count": len(rows), "out": str(out)}, indent=2))
    return 0


def cmd_replace_string(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manifest = load_manifest(workspace)
    if manifest.get("mode") != "binary_edit":
        raise ValueError("replace-string requires a binary_edit workspace. Use init/decompile to create one.")
    source = workspace_wsc_path(manifest, args.input)
    data = bytearray(source.read_bytes())
    find = args.find.encode(args.encoding)
    replace = args.replace.encode(args.encoding)
    if len(replace) > len(find):
        if args.allow_expanded:
            raise ValueError("Expanded WSC replacement is not supported yet because the RSC85/script container rebuilder is not implemented.")
        raise ValueError(f"Replacement is longer than search bytes ({len(replace)} > {len(find)}). Use a same-length value.")
    if len(replace) < len(find):
        if args.pad == "none":
            raise ValueError(f"Replacement is shorter than search bytes ({len(replace)} < {len(find)}). Use --pad nul or --pad space to preserve file size.")
        pad_byte = b"\x00" if args.pad == "nul" else b" "
        replace = replace + (pad_byte * (len(find) - len(replace)))
    if not find:
        raise ValueError("--find cannot be empty")

    offsets = []
    start = 0
    while True:
        idx = data.find(find, start)
        if idx < 0:
            break
        offsets.append(idx)
        start = idx + max(1, len(find))
    if not offsets:
        raise ValueError("Search string was not found in the WSC.")
    if args.occurrence != "all":
        ordinal = int(args.occurrence)
        if ordinal < 1 or ordinal > len(offsets):
            raise ValueError(f"Occurrence {ordinal} is outside found range 1..{len(offsets)}")
        offsets = [offsets[ordinal - 1]]
    for idx in offsets:
        data[idx:idx + len(find)] = replace
    edited = write_edited_workspace_wsc(
        workspace,
        manifest,
        bytes(data),
        {
            "type": "replace_string",
            "find": args.find,
            "replace": args.replace,
            "encoding": args.encoding,
            "pad": args.pad,
            "offsets": offsets,
            "offsets_hex": [f"0x{x:X}" for x in offsets],
            "length_preserved": True,
        },
    )
    print(json.dumps({"status": "string_replaced", "count": len(offsets), "edited_wsc": str(edited)}, indent=2))
    return 0


def cmd_patch_bytes(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manifest = load_manifest(workspace)
    if manifest.get("mode") != "binary_edit":
        raise ValueError("patch-bytes requires a binary_edit workspace. Use init/decompile to create one.")
    source = workspace_wsc_path(manifest, args.input)
    data = bytearray(source.read_bytes())
    offset = parse_int(args.offset)
    patch = clean_hex(args.hex)
    if offset < 0 or offset + len(patch) > len(data):
        raise ValueError(f"Patch range 0x{offset:X}..0x{offset + len(patch):X} is outside WSC size {len(data)}")
    before = bytes(data[offset:offset + len(patch)])
    if args.expected_hex:
        expected = clean_hex(args.expected_hex)
        if before != expected:
            raise ValueError(f"Expected bytes mismatch at 0x{offset:X}: found {hex_bytes(before)}, expected {hex_bytes(expected)}")
    data[offset:offset + len(patch)] = patch
    edited = write_edited_workspace_wsc(
        workspace,
        manifest,
        bytes(data),
        {
            "type": "patch_bytes",
            "offset": offset,
            "offset_hex": f"0x{offset:X}",
            "before_hex": hex_bytes(before),
            "after_hex": hex_bytes(patch),
            "length_preserved": True,
        },
    )
    print(json.dumps({"status": "bytes_patched", "offset": f"0x{offset:X}", "edited_wsc": str(edited)}, indent=2))
    return 0


def cmd_source_edit_status(args: argparse.Namespace) -> int:
    source = ""
    inspection = {}
    if args.workspace:
        manifest = load_manifest(Path(args.workspace))
        source_path = workspace_wsc_path(manifest, args.input)
        source = str(source_path)
        inspection = inspect_blob(source_path.read_bytes(), string_limit=20)
    elif args.input:
        source_path = Path(args.input)
        source = str(source_path)
        inspection = inspect_blob(source_path.read_bytes(), string_limit=20)

    report = {
        "status": "blocked",
        "lane": "wsc_source_decompile_rebuild",
        "input": source,
        "requested_capabilities": [
            "open WSC as C/source",
            "change functions",
            "add new code into an existing WSC",
            "expand strings freely",
            "rebuild internal WSC sections",
            "understand bytecode automatically",
        ],
        "available_today": [
            "existing-WSC binary inspection",
            "printable string extraction with offsets",
            "length-preserving string patches",
            "controlled byte patches",
            "full source-built replacement through SC-CL",
            "copied-RPF packing",
        ],
        "missing_requirements": ADVANCED_SOURCE_REQUIREMENTS,
        "boundary": "This tool will not present binary patching or source-built replacement as original WSC source editing.",
        "inspection": inspection,
    }
    out = Path(args.out) if args.out else DEFAULT_LOG_ROOT / "wsc_source_decompile_rebuild_blocked.json"
    write_json(out, report)
    print(json.dumps({"status": "blocked", "lane": report["lane"], "report": str(out)}, indent=2))
    return 2


def newest_file(root: Path, suffix: str) -> Path:
    matches = list(root.rglob(f"*{suffix}"))
    if not matches:
        raise FileNotFoundError(f"No {suffix} output found under {root}")
    return max(matches, key=lambda p: p.stat().st_mtime)


def cmd_compile(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manifest = load_manifest(workspace)
    if manifest.get("mode") == "binary_edit":
        raise ValueError("This is a binary_edit workspace. Use replace-string/patch-bytes, or create a full-replacement workspace with full-replace-init.")
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
    manifest.update({"compiled_wsc": str(wsc), "compiled_xsc": str(xsc), "compiled_xsa": str(xsa) if xsa else "", "active_wsc": str(wsc), "status": "compiled"})
    write_manifest(workspace, manifest)
    print(json.dumps({"status": "compiled", "wsc": str(wsc), "report": str(out_dir / "wsc_compile_report.json")}, indent=2))
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    manifest = load_manifest(workspace)
    wsc = Path(args.wsc) if args.wsc else workspace_wsc_path(manifest)
    if not wsc.exists():
        raise FileNotFoundError(f"WSC not found: {wsc}")
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
    mode = manifest.get("mode") or "unknown"
    builder.PROFILES[profile] = {
        "description": f"Manual Code RED WSC replacement from {mode} workflow.",
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
    if args.workspace:
        manifest = load_manifest(Path(args.workspace))
        path = workspace_wsc_path(manifest, args.input)
    else:
        if not args.input:
            raise ValueError("inspect requires --workspace or --input")
        path = Path(args.input)
    report = inspect_blob(path.read_bytes())
    out = Path(args.out) if args.out else DEFAULT_LOG_ROOT / f"{safe_name(path.stem)}_inspection.json"
    write_json(out, {"input": str(path), **report})
    print(json.dumps({"status": "inspected", "report": str(out), "looks_like_wsc_rsc85": report["looks_like_wsc_rsc85"]}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe Code RED WSC workflow: binary edit, explicit full replacement, and honest source-edit capability status")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create an existing-WSC binary edit workspace from an RPF entry.")
    init.add_argument("--name", required=True)
    init.add_argument("--archive-path", required=True)
    init.add_argument("--source-rpf", default=str(DEFAULT_SOURCE_RPF))
    init.add_argument("--workspace", default="")
    init.set_defaults(func=cmd_init)

    decompile = sub.add_parser("decompile", help="Alias for init: extract and inspect WSC for existing-file binary editing. Does not recover source.")
    decompile.add_argument("--name", required=True)
    decompile.add_argument("--archive-path", required=True)
    decompile.add_argument("--source-rpf", default=str(DEFAULT_SOURCE_RPF))
    decompile.add_argument("--workspace", default="")
    decompile.set_defaults(func=cmd_decompile)

    full_init = sub.add_parser("full-replace-init", help="Create a source-built full replacement workspace with src/main.c.")
    full_init.add_argument("--name", required=True)
    full_init.add_argument("--archive-path", required=True)
    full_init.add_argument("--source-rpf", default=str(DEFAULT_SOURCE_RPF))
    full_init.add_argument("--workspace", default="")
    full_init.set_defaults(func=cmd_full_replace_init)

    source_init = sub.add_parser("source-init", help="Alias for full-replace-init.")
    source_init.add_argument("--name", required=True)
    source_init.add_argument("--archive-path", required=True)
    source_init.add_argument("--source-rpf", default=str(DEFAULT_SOURCE_RPF))
    source_init.add_argument("--workspace", default="")
    source_init.set_defaults(func=cmd_full_replace_init)

    strings = sub.add_parser("strings", help="Extract printable strings and offsets from a WSC or workspace.")
    strings.add_argument("--workspace", default="")
    strings.add_argument("--input", default="")
    strings.add_argument("--out", default="")
    strings.add_argument("--min-len", type=int, default=4)
    strings.add_argument("--limit", type=int, default=0)
    strings.set_defaults(func=cmd_strings)

    replace_string = sub.add_parser("replace-string", help="Length-preserving string search/replace in an existing-WSC binary edit workspace.")
    replace_string.add_argument("--workspace", required=True)
    replace_string.add_argument("--find", required=True)
    replace_string.add_argument("--replace", required=True)
    replace_string.add_argument("--input", default="")
    replace_string.add_argument("--encoding", default="ascii")
    replace_string.add_argument("--occurrence", default="1", help="1-based occurrence number, or all.")
    replace_string.add_argument("--pad", choices=["none", "nul", "space"], default="none")
    replace_string.add_argument("--allow-expanded", action="store_true", help="Reserved for future container rebuild support; currently refused.")
    replace_string.set_defaults(func=cmd_replace_string)

    patch_bytes = sub.add_parser("patch-bytes", help="Patch exact bytes at an offset in an existing-WSC binary edit workspace.")
    patch_bytes.add_argument("--workspace", required=True)
    patch_bytes.add_argument("--offset", required=True)
    patch_bytes.add_argument("--hex", required=True)
    patch_bytes.add_argument("--expected-hex", default="")
    patch_bytes.add_argument("--input", default="")
    patch_bytes.set_defaults(func=cmd_patch_bytes)

    source_status = sub.add_parser("source-edit-status", help="Report why WSC-as-C/source editing is blocked until a real bytecode decompiler/rebuilder exists.")
    source_status.add_argument("--workspace", default="")
    source_status.add_argument("--input", default="")
    source_status.add_argument("--out", default="")
    source_status.set_defaults(func=cmd_source_edit_status)

    open_source = sub.add_parser("open-source", help="Alias for source-edit-status. Does not fake WSC-to-C decompilation.")
    open_source.add_argument("--workspace", default="")
    open_source.add_argument("--input", default="")
    open_source.add_argument("--out", default="")
    open_source.set_defaults(func=cmd_source_edit_status)

    compile_cmd = sub.add_parser("compile", help="Compile a full replacement workspace src/main.c to XSC and WSC.")
    compile_cmd.add_argument("--workspace", required=True)
    compile_cmd.add_argument("--source", default="")
    compile_cmd.add_argument("--name", default="")
    compile_cmd.add_argument("--clean", action="store_true")
    compile_cmd.set_defaults(func=cmd_compile)

    full_compile = sub.add_parser("full-replace-compile", help="Alias for compile: compile a source-built full replacement WSC.")
    full_compile.add_argument("--workspace", required=True)
    full_compile.add_argument("--source", default="")
    full_compile.add_argument("--name", default="")
    full_compile.add_argument("--clean", action="store_true")
    full_compile.set_defaults(func=cmd_compile)

    recompile = sub.add_parser("recompile", help="Alias for compile, retained for source-built replacement workspaces.")
    recompile.add_argument("--workspace", required=True)
    recompile.add_argument("--source", default="")
    recompile.add_argument("--name", default="")
    recompile.add_argument("--clean", action="store_true")
    recompile.set_defaults(func=cmd_compile)

    pack = sub.add_parser("pack", help="Pack the workspace active WSC into a copied RPF under build/.")
    pack.add_argument("--workspace", required=True)
    pack.add_argument("--wsc", default="")
    pack.add_argument("--source-rpf", default="")
    pack.add_argument("--out", default="")
    pack.add_argument("--write", action="store_true", help="Write copied RPF. Default is dry-run.")
    pack.set_defaults(func=cmd_pack)

    inspect = sub.add_parser("inspect", help="Inspect WSC/XSC header, body, section candidates, and strings without pretending to decompile it.")
    inspect.add_argument("--input", default="")
    inspect.add_argument("--workspace", default="")
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
