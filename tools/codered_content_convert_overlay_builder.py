#!/usr/bin/env python3
"""Build copied content.rpf variants from the local content convert zip.

The content convert zip contains an extracted content tree from a different
format/version. This tool uses it as reference material only. It can dry-run or
write copied RPF variants by appending selected payloads at EOF and rebuilding
the RPF6 TOC. It never installs into the game folder.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import struct
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import zstandard as zstd
except Exception:
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"
DEFAULT_ZIP = ROOT / "build" / "content convert.zip"
DEFAULT_SOURCE = ROOT / "build" / "content_mp_lan_fallback_test" / "content.rpf"
DEFAULT_OUT_DIR = ROOT / "build" / "content_convert_variants"
DEFAULT_LOG_DIR = ROOT / "logs" / "content_convert_overlay"
HEX_NAME_RE = re.compile(r"^0x([0-9a-fA-F]{8})$")


PROFILES: dict[str, dict[str, object]] = {
    "support_aliases": {
        "description": "Add missing convert UI aliases plus Social Club support scripts; keep same-hash LAN fallback files from the source RPF.",
        "include": [
            "content/ui/pausemenu/net/0x118473D0.xml",
            "content/ui/pausemenu/net/0x1374443B.xml",
            "content/release/scripting/DesignerDefined/socialclub/**",
        ],
        "replace": [],
    },
    "convert_ui": {
        "description": "Overlay convert networking/lanmenu/offline/play confirmation UI plus missing aliases/support scripts.",
        "include": [
            "content/ui/pausemenu/networking.sc.xml",
            "content/ui/pausemenu/net/lanmenu.sc.xml",
            "content/ui/pausemenu/net/0x118473D0.xml",
            "content/ui/pausemenu/net/0x1374443B.xml",
            "content/release/scripting/DesignerDefined/socialclub/**",
        ],
        "replace": [
            "content/ui/pausemenu/networking.sc.xml",
            "content/ui/pausemenu/net/lanmenu.sc.xml",
            "content/ui/pausemenu/net/0x118473D0.xml",
            "content/ui/pausemenu/net/0x1374443B.xml",
        ],
    },
    "force_freemode": {
        "description": "Start from the current LAN fallback source and add a direct LAN route plus support aliases. This is the strongest freeroam test candidate.",
        "include": [
            "content/ui/pausemenu/net/0x118473D0.xml",
            "content/ui/pausemenu/net/0x1374443B.xml",
            "content/release/scripting/DesignerDefined/socialclub/**",
        ],
        "replace": [],
        "requires_lan_fallback_source": True,
    },
}

MP_REQUIRED = [
    "root/content/release/multiplayer/freemode/freemode.csc",
    "root/content/release64/multiplayer/freemode/freemode.csc",
    "root/content/release/multiplayer/mp_idle.csc",
    "root/content/release64/multiplayer/mp_idle.csc",
]


@dataclass
class Node:
    name: str
    name_off: int
    kind: str
    original: dict | None = None
    archive_path: str = ""
    children: list["Node"] = field(default_factory=list)
    index: int = -1
    start: int = 0
    count: int = 0
    source_bytes: bytes | None = None
    decoded_size: int = 0
    stored_size: int = 0
    new_offset: int = 0
    force_compressed: bool = False
    operation: str = "preserve"

    def child_dir(self, name: str) -> "Node | None":
        low = name.lower()
        return next((child for child in self.children if child.kind == "dir" and child.name.lower() == low), None)

    def child_file(self, name: str) -> "Node | None":
        low = name.lower()
        return next((child for child in self.children if child.kind == "file" and child.name.lower() == low), None)


def load_backend():
    spec = importlib.util.spec_from_file_location("codered_workbench_backend", WORKBENCH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {WORKBENCH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def align(value: int, boundary: int = 8) -> int:
    return (value + boundary - 1) & ~(boundary - 1)


def name_hash(wb, name: str) -> int:
    if name == "root":
        return 0
    match = HEX_NAME_RE.match(name)
    if match:
        return int(match.group(1), 16)
    return int(wb.rdr_name_hash(name))


def build_existing_tree(info: dict) -> Node:
    nodes: dict[int, Node] = {}
    for ent in info["entries"]:
        nodes[int(ent["index"])] = Node(
            name=str(ent.get("name") or f"0x{int(ent['name_off']):08X}"),
            name_off=int(ent["name_off"]),
            kind=str(ent["type"]),
            original=ent,
            archive_path=str(ent.get("path") or ""),
        )
    root = nodes[0]
    for ent in info["entries"]:
        parent = ent.get("parent_index")
        if parent is not None:
            nodes[int(parent)].children.append(nodes[int(ent["index"])])
    return root


def ensure_dir(wb, parent: Node, name: str, archive_path: str) -> Node:
    found = parent.child_dir(name)
    if found is not None:
        return found
    node = Node(name=name, name_off=name_hash(wb, name), kind="dir", archive_path=archive_path)
    parent.children.append(node)
    return node


def should_zstd_archive_path(path: str) -> bool:
    low = path.lower()
    leaf = low.rsplit("/", 1)[-1]
    return low.startswith("root/content/ui/") and (
        low.endswith(".sc.xml")
        or low.endswith(".xml")
        or re.match(r"0x[0-9a-f]{8}$", leaf) is not None
    )


def payload_for_archive_path(path: str, data: bytes) -> tuple[bytes, int, bool]:
    if should_zstd_archive_path(path):
        if zstd is None:
            raise RuntimeError("Python zstandard is required for UI XML overlay entries")
        return zstd.ZstdCompressor(level=3).compress(data), len(data), True
    return data, len(data), False


def add_or_replace_file(wb, root: Node, archive_path: str, payload: bytes, operation: str) -> tuple[str, Node]:
    parts = [part for part in archive_path.replace("\\", "/").split("/") if part]
    if not parts or parts[0].lower() != "root":
        raise ValueError(f"Archive path must start with root/: {archive_path}")
    parent = root
    running = "root"
    for part in parts[1:-1]:
        running = f"{running}/{part}"
        parent = ensure_dir(wb, parent, part, running)
    leaf = parts[-1]
    existing = parent.child_file(leaf)
    leaf_hash = name_hash(wb, leaf)
    same_hash = next((child for child in parent.children if child.kind == "file" and child.name_off == leaf_hash), None)
    if existing is None and same_hash is not None:
        if operation != "replace":
            return "skip_existing", same_hash
        existing = same_hash
    stored, decoded_size, compressed = payload_for_archive_path(archive_path, payload)
    if existing is not None:
        if operation != "replace":
            return "skip_existing", existing
        if existing.original and existing.original.get("is_resource"):
            raise ValueError(f"Refusing to replace resource entry: {archive_path}")
        existing.source_bytes = stored
        existing.decoded_size = decoded_size
        existing.stored_size = len(stored)
        existing.force_compressed = compressed
        existing.operation = "replace"
        return "replace", existing
    node = Node(
        name=leaf,
        name_off=leaf_hash,
        kind="file",
        archive_path=archive_path,
        source_bytes=stored,
        decoded_size=decoded_size,
        stored_size=len(stored),
        force_compressed=compressed,
        operation="add",
    )
    parent.children.append(node)
    return "add", node


def flatten_tree(root: Node) -> list[Node]:
    ordered: list[Node] = []

    def append_node(node: Node) -> None:
        node.index = len(ordered)
        ordered.append(node)

    def emit_children(node: Node) -> None:
        if node.kind != "dir":
            return
        node.start = len(ordered)
        for child in node.children:
            append_node(child)
        node.count = len(node.children)
        for child in node.children:
            if child.kind == "dir":
                emit_children(child)

    append_node(root)
    emit_children(root)
    return ordered


def file_offset_raw(wb, node: Node) -> int:
    if node.original and node.original.get("is_resource"):
        return ((node.new_offset // 8) & 0x7FFFFF00) | (wb._rpf_resource_type(int(node.original["offset_raw"])) & 0xFF)
    return (node.new_offset // 8) & 0x7FFFFFFF


def pack_toc(wb, nodes: list[Node], encrypted: bool) -> bytes:
    toc = bytearray()
    for node in nodes:
        if node.kind == "dir":
            toc.extend(struct.pack(">5I", node.name_off, 0, 0x80000000 | node.start, node.count, 0))
            continue
        if node.operation in {"add", "replace"}:
            b = node.stored_size & 0x0FFFFFFF
            c = file_offset_raw(wb, node)
            compression_bit = 0x40000000 if node.force_compressed else 0
            d = compression_bit | (node.decoded_size & 0x3FFFFFFF)
            e = 0
        else:
            ent = node.original or {}
            b = int(ent.get("size_in_archive") or 0) & 0x0FFFFFFF
            c = file_offset_raw(wb, node)
            d = int(ent.get("flag1") or 0)
            e = int(ent.get("flag2") or 0)
        toc.extend(struct.pack(">5I", node.name_off, b, c, d, e))
    padded_size = align(len(toc), 16)
    toc.extend(b"\x00" * (padded_size - len(toc)))
    return wb._codered_rpf6_encrypt(bytes(toc)) if encrypted else bytes(toc)


def zip_match(name: str, patterns: list[str]) -> bool:
    low = name.lower()
    for pattern in patterns:
        p = pattern.lower().replace("\\", "/")
        if p.endswith("/**") and low.startswith(p[:-3]):
            return True
        if low == p:
            return True
    return False


def archive_path_from_zip_name(name: str) -> str:
    parts = name.replace("\\", "/").split("/")
    leaf = parts[-1]
    if re.match(r"0x[0-9A-Fa-f]{8}\.xml$", leaf):
        parts[-1] = leaf[:-4]
    return "root/" + "/".join(parts)


def select_zip_members(zip_path: Path, profile: str) -> list[dict]:
    config = PROFILES[profile]
    include = list(config.get("include", []))  # type: ignore[arg-type]
    replace = set(str(p).lower().replace("\\", "/") for p in config.get("replace", []))  # type: ignore[arg-type]
    rows: list[dict] = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if not zip_match(name, include):
                continue
            rows.append(
                {
                    "zip_name": name,
                    "archive_path": archive_path_from_zip_name(name),
                    "operation": "replace" if name.lower() in replace else "add",
                    "size": info.file_size,
                }
            )
    return sorted(rows, key=lambda r: r["archive_path"].lower())


def summarize_archive(info: dict) -> dict:
    paths = [str(ent.get("path") or "").replace("\\", "/").lower() for ent in info.get("entries", []) if ent.get("type") == "file"]
    return {
        "entry_count": info.get("entry_count"),
        "file_count": info.get("file_count"),
        "dir_count": info.get("dir_count"),
        "mp_csc_count": sum(1 for path in paths if "/multiplayer/" in path and path.endswith(".csc")),
        "required_mp_presence": {path: path.lower() in paths for path in MP_REQUIRED},
    }


def build_overlay(zip_path: Path, source: Path, output: Path, log_dir: Path, profile: str, write: bool) -> dict:
    wb = load_backend()
    info = wb.parse_rpf6(source)
    if info is None:
        raise ValueError(f"Not a readable RPF6 archive: {source}")
    root = build_existing_tree(info)
    selected = select_zip_members(zip_path, profile)
    if not selected:
        raise RuntimeError(f"No zip members selected for profile {profile}")
    operations: list[dict] = []
    with zipfile.ZipFile(zip_path) as z:
        for row in selected:
            action, node = add_or_replace_file(wb, root, row["archive_path"], z.read(row["zip_name"]), row["operation"])
            op = dict(row)
            op.update({"result": action, "compressed": node.force_compressed, "stored_size": node.stored_size, "decoded_size": node.decoded_size})
            operations.append(op)
    nodes = flatten_tree(root)
    new_toc_size = align(len(nodes) * 20, 16)
    original_payload_floor = min(int(ent["offset"]) for ent in info["entries"] if ent.get("type") == "file")
    if 16 + new_toc_size > original_payload_floor:
        raise RuntimeError(f"New TOC ({16 + new_toc_size}) would overlap first payload at {original_payload_floor}")
    encrypted = bool(info.get("enc_flag"))
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "profile": profile,
        "description": PROFILES[profile]["description"],
        "mode": "write" if write else "dry-run",
        "status": "pending",
        "zip": str(zip_path),
        "source": str(source),
        "output": str(output),
        "source_summary": summarize_archive(info),
        "selected_count": len(selected),
        "operation_counts": {
            "add": sum(1 for op in operations if op["result"] == "add"),
            "replace": sum(1 for op in operations if op["result"] == "replace"),
            "skip_existing": sum(1 for op in operations if op["result"] == "skip_existing"),
        },
        "new_entry_count": len(nodes),
        "new_toc_size": new_toc_size,
        "first_payload_offset": original_payload_floor,
        "operations": operations,
    }
    if not write:
        report["status"] = "pass"
        return report

    original = bytearray(source.read_bytes())
    write_pos = align(len(original), 8)
    if write_pos > len(original):
        original.extend(b"\x00" * (write_pos - len(original)))
    appended: list[dict] = []
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = align(len(original), 8)
        if node.new_offset > len(original):
            original.extend(b"\x00" * (node.new_offset - len(original)))
        payload = node.source_bytes or b""
        original.extend(payload)
        padded = align(len(original), 8)
        if padded > len(original):
            original.extend(b"\x00" * (padded - len(original)))
        appended.append(
            {
                "archive_path": node.archive_path,
                "operation": node.operation,
                "entry_index": node.index,
                "new_offset": node.new_offset,
                "stored_size": node.stored_size,
                "decoded_size": node.decoded_size,
                "compressed": node.force_compressed,
            }
        )
    toc = pack_toc(wb, nodes, encrypted)
    struct.pack_into(">4I", original, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    original[16:16 + len(toc)] = toc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(original)
    check = wb.parse_rpf6(output)
    if check is None:
        report["status"] = "fail"
        report["error"] = "output RPF did not parse"
    else:
        report["status"] = "pass"
        report["output_summary"] = summarize_archive(check)
        report["output_size"] = output.stat().st_size
        report["appended"] = appended
    return report


def write_reports(report: dict, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    profile = str(report["profile"])
    (log_dir / f"{profile}_overlay_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (log_dir / f"{profile}_operations.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["zip_name", "archive_path", "operation", "result", "compressed", "size", "stored_size", "decoded_size"]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report.get("operations", []))
    lines = [
        f"# Code RED Content Convert Overlay - {profile}",
        "",
        f"Status: `{report['status']}`",
        f"Mode: `{report['mode']}`",
        f"Description: {report['description']}",
        "",
        f"- source: `{report['source']}`",
        f"- output: `{report['output']}`",
        f"- selected: `{report['selected_count']}`",
        f"- adds: `{report['operation_counts']['add']}`",
        f"- replaces: `{report['operation_counts']['replace']}`",
        f"- skipped existing: `{report['operation_counts']['skip_existing']}`",
        "",
        "## Output Summary",
        "",
        f"- entry count: `{(report.get('output_summary') or {}).get('entry_count', report.get('new_entry_count'))}`",
        f"- MP CSC count: `{(report.get('output_summary') or report.get('source_summary') or {}).get('mp_csc_count')}`",
    ]
    (log_dir / f"{profile}_overlay_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build copied content.rpf overlays from content convert zip.")
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--write", action="store_true", help="Write copied RPF. Default is dry-run only.")
    args = parser.parse_args(argv)
    output = args.out_dir / args.profile / "content.rpf"
    report = build_overlay(args.zip, args.source, output, args.log_dir, args.profile, args.write)
    write_reports(report, args.log_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "operations"}, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
