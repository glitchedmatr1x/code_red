#!/usr/bin/env python3
"""Create a copied content.rpf with reference multiplayer scripts added.

This is intentionally conservative:
- the source archive is never modified;
- existing file payload bytes and metadata are preserved;
- new reference files are stored as plain, uncompressed file entries;
- the rebuilt TOC is written into the existing pre-payload padding gap and new
  payloads are appended at the end of the copied archive.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "python_workbench.py"
HEX_NAME_RE = re.compile(r"^0x([0-9a-fA-F]{8})$")


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


@dataclass
class Node:
    name: str
    name_off: int
    kind: str
    original: dict | None = None
    source_file: Path | None = None
    archive_path: str = ""
    children: list["Node"] = field(default_factory=list)
    index: int = -1
    start: int = 0
    count: int = 0
    new_offset: int = 0
    size: int = 0

    def child_dir(self, name: str) -> "Node | None":
        low = name.lower()
        for child in self.children:
            if child.kind == "dir" and child.name.lower() == low:
                return child
        return None

    def child_file(self, name: str) -> "Node | None":
        low = name.lower()
        for child in self.children:
            if child.kind == "file" and child.name.lower() == low:
                return child
        return None


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
        if parent is None:
            continue
        nodes[int(parent)].children.append(nodes[int(ent["index"])])
    return root


def ensure_dir(wb, parent: Node, name: str, archive_path: str) -> Node:
    found = parent.child_dir(name)
    if found is not None:
        return found
    node = Node(name=name, name_off=name_hash(wb, name), kind="dir", archive_path=archive_path)
    parent.children.append(node)
    return node


def add_reference_file(wb, root: Node, target_path: str, source_file: Path) -> bool:
    parts = [part for part in target_path.replace("\\", "/").split("/") if part]
    if not parts or parts[0] != "root":
        raise ValueError(f"Archive path must start with root/: {target_path}")
    parent = root
    running = "root"
    for part in parts[1:-1]:
        running = f"{running}/{part}"
        parent = ensure_dir(wb, parent, part, running)
    leaf = parts[-1]
    if parent.child_file(leaf) is not None:
        return False
    node = Node(
        name=leaf,
        name_off=name_hash(wb, leaf),
        kind="file",
        source_file=source_file,
        archive_path=target_path,
        size=source_file.stat().st_size,
    )
    parent.children.append(node)
    return True


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
        if node.original:
            ent = node.original
            b = (int(ent.get("size_in_archive") or 0)) & 0x0FFFFFFF
            c = file_offset_raw(wb, node)
            d = int(ent.get("flag1") or 0)
            e = int(ent.get("flag2") or 0)
        else:
            b = node.size & 0x0FFFFFFF
            c = file_offset_raw(wb, node)
            d = node.size & 0x3FFFFFFF
            e = 0
        toc.extend(struct.pack(">5I", node.name_off, b, c, d, e))
    padded_size = align(len(toc), 16)
    toc.extend(b"\x00" * (padded_size - len(toc)))
    return wb._codered_rpf6_encrypt(bytes(toc)) if encrypted else bytes(toc)


def iter_reference_files(reference_mp_root: Path) -> list[Path]:
    files = [p for p in reference_mp_root.rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(reference_mp_root).as_posix().lower())


def inject_archive(source_archive: Path, reference_mp_root: Path, output_archive: Path, log_dir: Path, include_release64: bool) -> dict:
    wb = load_backend()
    info = wb.parse_rpf6(source_archive)
    if info is None:
        raise ValueError(f"Not a readable RPF6 archive: {source_archive}")

    root = build_existing_tree(info)
    reference_files = iter_reference_files(reference_mp_root)
    added: list[dict] = []
    skipped: list[dict] = []
    target_roots = ["root/content/release/multiplayer"]
    if include_release64:
        target_roots.append("root/content/release64/multiplayer")

    for source in reference_files:
        rel = source.relative_to(reference_mp_root).as_posix()
        for target_root in target_roots:
            target = f"{target_root}/{rel}"
            did_add = add_reference_file(wb, root, target, source)
            row = {"source": str(source), "archive_path": target, "size": source.stat().st_size}
            (added if did_add else skipped).append(row)

    nodes = flatten_tree(root)
    new_toc_size = align(len(nodes) * 20, 16)
    original_payload_floor = min(int(ent["offset"]) for ent in info["entries"] if ent.get("type") == "file")
    if 16 + new_toc_size > original_payload_floor:
        raise RuntimeError(
            f"New TOC ({16 + new_toc_size} bytes) would overlap first payload at {original_payload_floor}; "
            "refusing to build copied archive."
        )

    original = bytearray(source_archive.read_bytes())
    write_pos = align(len(original), 8)
    if write_pos > len(original):
        original.extend(b"\x00" * (write_pos - len(original)))

    for node in nodes:
        if node.kind != "file":
            continue
        if node.original:
            node.new_offset = int(node.original["offset"])
            node.size = int(node.original.get("size_in_archive") or 0)
            continue
        node.new_offset = write_pos
        payload = node.source_file.read_bytes() if node.source_file else b""
        original.extend(payload)
        write_pos += len(payload)
        aligned = align(write_pos, 8)
        if aligned > write_pos:
            original.extend(b"\x00" * (aligned - write_pos))
            write_pos = aligned

    encrypted = bool(info.get("enc_flag"))
    toc = pack_toc(wb, nodes, encrypted)
    struct.pack_into(">4I", original, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    original[16:16 + len(toc)] = toc

    output_archive.parent.mkdir(parents=True, exist_ok=True)
    output_archive.write_bytes(original)

    check = wb.parse_rpf6(output_archive)
    if check is None:
        raise RuntimeError(f"Built archive is not parseable: {output_archive}")
    mp_entries = [
        ent for ent in check["entries"]
        if ent.get("type") == "file" and "/multiplayer/" in str(ent.get("path") or "")
    ]
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source_archive": str(source_archive),
        "reference_mp_root": str(reference_mp_root),
        "output_archive": str(output_archive),
        "include_release64": include_release64,
        "original_entry_count": info.get("entry_count"),
        "new_entry_count": check.get("entry_count"),
        "added_file_entries": len(added),
        "skipped_existing_entries": len(skipped),
        "mp_file_entries_found_after_build": len(mp_entries),
        "new_toc_size": new_toc_size,
        "first_payload_offset": original_payload_floor,
        "encrypted_toc": encrypted,
        "added": added,
        "skipped": skipped,
        "mp_entries_sample": [ent.get("path") for ent in mp_entries[:80]],
    }
    (log_dir / "content_rpf_mp_inject_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (log_dir / "content_rpf_mp_inject_added.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["source", "archive_path", "size"])
        writer.writeheader()
        writer.writerows(added)
    (log_dir / "IMPORTANT_CodeRED_Content_RPF_MP_SinglePlayer_Injection.md").write_text(
        "# IMPORTANT: Code RED content.rpf Multiplayer Injection Pass\n\n"
        f"Source archive: `{source_archive}`\n\n"
        f"Reference multiplayer root: `{reference_mp_root}`\n\n"
        f"Copied output archive: `{output_archive}`\n\n"
        "This pass does not overwrite the live game archive. It rebuilds the RPF6 TOC in a copied archive, "
        "preserves existing payload bytes, and appends reference multiplayer script payloads as plain file entries.\n\n"
        f"- Original entries: `{info.get('entry_count')}`\n"
        f"- New entries: `{check.get('entry_count')}`\n"
        f"- Added file entries: `{len(added)}`\n"
        f"- Multiplayer file entries after build: `{len(mp_entries)}`\n"
        f"- Mirrored into release64: `{include_release64}`\n"
        f"- TOC bytes: `{new_toc_size}` of available pre-payload space ending at `{original_payload_floor}`\n\n"
        "Important limitation: adding the missing multiplayer content tree can make scripts addressable by path, "
        "but it may not expose multiplayer UI by itself. UI/start-menu exposure may still require flash/menu assets "
        "or emulator-side XLive/System Link gate emulation.\n\n"
        "Use `content_rpf_mp_inject_manifest.json` and `content_rpf_mp_inject_added.csv` for indexing.\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a copied content.rpf with reference MP scripts added.")
    parser.add_argument("--source", default=str(Path(r"D:\Games\Red Dead Redemption\game\content.rpf")))
    parser.add_argument("--reference-mp-root", default=str(Path(r"D:\Games\Red Dead Redemption\game\BACKUP BEFORE MODDING\rdr1\mods\root\content\release\multiplayer")))
    parser.add_argument("--output", default=str(ROOT / "build" / "content_mp_singleplayer" / "content_mp_singleplayer.rpf"))
    parser.add_argument("--log-dir", default=str(ROOT / "logs" / "content_rpf_mp_singleplayer_injection"))
    parser.add_argument("--no-release64-mirror", action="store_true", help="Only add root/content/release/multiplayer.")
    args = parser.parse_args(argv)
    manifest = inject_archive(
        source_archive=Path(args.source),
        reference_mp_root=Path(args.reference_mp_root),
        output_archive=Path(args.output),
        log_dir=Path(args.log_dir),
        include_release64=not args.no_release64_mirror,
    )
    print(json.dumps({k: v for k, v in manifest.items() if k not in {"added", "skipped", "mp_entries_sample"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
