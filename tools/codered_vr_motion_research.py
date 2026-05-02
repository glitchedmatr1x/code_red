#!/usr/bin/env python3
"""Code RED VR motion/camera/body research scanner.

Scans RDR RPF6 archives for first-person, camera, weapon IK, NaturalMotion,
body-part, and control/task clues. This is a read-only research tool.

Typical use:

python tools/codered_vr_motion_research.py \
  --archive camera.rpf \
  --archive naturalmotion.rpf \
  --archive act.rpf \
  --archive tune_d11generic.rpf \
  --archive content.rpf \
  --outdir reports/vr_motion_research
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

RPF6_AES_KEY = bytes([
    0xB7, 0x62, 0xDF, 0xB6, 0xE2, 0xB2, 0xC6, 0xDE,
    0xAF, 0x72, 0x2A, 0x32, 0xD2, 0xFB, 0x6F, 0x0C,
    0x98, 0xA3, 0x21, 0x74, 0x62, 0xC9, 0xC4, 0xED,
    0xAD, 0xAA, 0x2E, 0xD0, 0xDD, 0xF9, 0x2F, 0x10,
])
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

CATEGORIES: dict[str, list[str]] = {
    "camera": [
        "firstperson", "first person", "vehiclefirstperson", "vehicle first person",
        "fov", "fovspline", "lens", "lookstick", "camera", "camdynamic",
        "boom", "shoulder", "nearplane", "near plane", "pitch", "yaw", "zoom",
        "head", "view", "vehicle",
    ],
    "weapon_ik": [
        "ikoffset", "ikoffsethold", "muzzleoffset", "actfilename", "actroot", "animset",
        "weaponarcgroupname", "canshootfromcamera", "cameraspeedscalar", "dual", "pistol",
        "rifle", "repeater", "shotgun", "sniper", "left hand", "right hand", "lefthand", "righthand",
    ],
    "body_motion": [
        "activepose", "forcetobodypart", "bodyrelax", "partindex", "leftarm", "rightarm",
        "left arm", "right arm", "spine", "pelvis", "clavicle", "ragdoll", "bullet",
        "shot", "impulse", "euphoria", "naturalmotion", "arm", "hand",
    ],
    "controls_tasks": [
        "combatreadyrangeweapon", "combatshootordrawweapon", "combatuseweaponsagainst",
        "combatweaponholster", "armsupbrace", "playeraimzoomedatme", "lookatifpossible",
        "aim", "draw", "holster", "shoot", "control", "input", "task", "movement",
    ],
}

TEXT_LIKE_EXTS = {
    ".xml", ".txt", ".weap", ".tr", ".strtbl", ".cmt", ".ccm", ".cm",
    ".camdynamicboomtunemanager", ".cinematiccamerashotcollection", ".wat", ".seq", ".art", ".prt",
}


def rdr_hash(name: str) -> int:
    h = 0
    for ch in name.lower():
        a = (h + ord(ch)) & 0xFFFFFFFF
        b = (a + ((a << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h = (b ^ (b >> 6)) & 0xFFFFFFFF
    a = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    b = (a ^ (a >> 11)) & 0xFFFFFFFF
    return (b + ((b << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def aes_blocks(data: bytes, decrypt: bool = True) -> bytes:
    n = len(data) & ~0xF
    if n <= 0:
        return data
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        cipher = Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
        block = data[:n]
        for _ in range(16):
            ctx = cipher.decryptor() if decrypt else cipher.encryptor()
            block = ctx.update(block) + ctx.finalize()
        return block + data[n:]
    except Exception:
        if not shutil.which("openssl"):
            raise RuntimeError("Encrypted RPF requires cryptography or openssl")
        block = data[:n]
        mode = "-d" if decrypt else "-e"
        for _ in range(16):
            proc = subprocess.run(
                ["openssl", "enc", "-aes-256-ecb", mode, "-K", RPF6_AES_KEY.hex(), "-nopad", "-nosalt"],
                input=block,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            block = proc.stdout
        return block + data[n:]


def is_resource(flag1: int) -> bool:
    return (flag1 & 0x80000000) != 0


def is_extended(flag2: int) -> bool:
    return (flag2 & 0x80000000) != 0


def is_compressed(flag1: int, flag2: int) -> bool:
    return (not is_extended(flag2)) and ((flag1 >> 30) & 1) == 1


def entry_offset(offset_raw: int, resource: bool) -> int:
    return ((offset_raw & 0x7FFFFF00) if resource else (offset_raw & 0x7FFFFFFF)) * 8


def total_size(flag1: int, flag2: int) -> int:
    if not is_resource(flag1):
        return flag1 & 0xBFFFFFFF
    if is_extended(flag2):
        return ((flag2 & 0x3FFF) << 12) + (((flag2 >> 14) & 0x3FFF) << 12)
    virtual_pages = ((flag1 >> 4) & 0x7F) + ((flag1 >> 3) & 1) + ((flag1 >> 2) & 1) + ((flag1 >> 1) & 1) + (flag1 & 1)
    virtual_shift = (flag1 >> 11) & 0xF
    physical_pages = ((flag1 >> 19) & 0x7F) + ((flag1 >> 18) & 1) + ((flag1 >> 17) & 1) + ((flag1 >> 16) & 1) + ((flag1 >> 15) & 1)
    physical_shift = (flag1 >> 26) & 0xF
    return (virtual_pages << (virtual_shift + 8)) + (physical_pages << (physical_shift + 8))


@dataclass
class RPFEntry:
    index: int
    name_hash: int
    name: str
    path: str
    type: str
    parent_index: int | None
    size: int = 0
    offset: int = 0
    resource: bool = False
    resource_type: int | None = None
    compressed: bool = False
    total: int = 0
    ext: str = ""


class RPF6:
    def __init__(self, path: Path, debug_names: bool = True):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:4] != b"RPF6":
            raise ValueError(f"Not RPF6: {self.path}")
        _, self.count, self.debug_word, self.enc = struct.unpack(">4I", self.data[:16])
        self.toc_size = ((self.count * 20) + 15) & ~15
        toc = self.data[16 : 16 + self.toc_size]
        self.toc = aes_blocks(toc, True) if self.enc else toc
        self.entries = self._entries(debug_names)
        self.exts = Counter(e.ext for e in self.entries if e.ext)

    def _debug_names(self) -> dict[int, list[str]]:
        offset = self.debug_word * 8
        if offset <= 0 or offset >= len(self.data):
            return {}
        try:
            blob = aes_blocks(self.data[offset:], True)[self.count * 8 :]
        except Exception:
            return {}
        out: dict[int, list[str]] = defaultdict(list)
        for item in blob.decode("latin-1", "ignore").split("\0"):
            item = item.strip()
            if item:
                out[rdr_hash(item)].append(item)
        return out

    def _entries(self, debug_names: bool) -> list[RPFEntry]:
        raw: list[dict[str, Any]] = []
        names = self._debug_names() if debug_names else {}
        for i in range(self.count):
            a, b, c, d, e = struct.unpack(">5I", self.toc[i * 20 : (i + 1) * 20])
            is_dir = ((c >> 24) & 0xFF) == 0x80
            if is_dir:
                raw.append({"index": i, "name_hash": a, "type": "dir", "start": c & 0x7FFFFFFF, "count": d & 0x0FFFFFFF})
            else:
                resource = is_resource(d)
                raw.append(
                    {
                        "index": i,
                        "name_hash": a,
                        "type": "file",
                        "size": b & 0x0FFFFFFF,
                        "offset": entry_offset(c, resource),
                        "resource": resource,
                        "resource_type": (c & 0xFF) if resource else None,
                        "compressed": is_compressed(d, e),
                        "total": total_size(d, e),
                    }
                )
        parents: list[int | None] = [None] * len(raw)
        for item in raw:
            if item["type"] == "dir":
                for child in range(item["start"], item["start"] + item["count"]):
                    if 0 <= child < len(raw):
                        parents[child] = item["index"]

        def name_for(item: dict[str, Any]) -> str:
            if item["type"] == "dir" and item["name_hash"] == 0:
                return "root"
            vals = names.get(item["name_hash"])
            return vals.pop(0) if vals else f"0x{item['name_hash']:08X}"

        for item in raw:
            item["name"] = name_for(item)
            item["parent_index"] = parents[item["index"]]

        entries: list[RPFEntry] = []
        for item in raw:
            parts = [item["name"]]
            parent = item["parent_index"]
            seen: set[int] = set()
            while parent is not None and parent not in seen and 0 <= parent < len(raw):
                seen.add(parent)
                parts.append(raw[parent]["name"])
                parent = raw[parent]["parent_index"]
            path = "/".join(reversed(parts))
            ext = "." + item["name"].lower().rsplit(".", 1)[-1] if item["type"] == "file" and "." in item["name"] else ""
            entries.append(
                RPFEntry(
                    index=item["index"],
                    name_hash=item["name_hash"],
                    name=item["name"],
                    path=path,
                    type=item["type"],
                    parent_index=item["parent_index"],
                    size=item.get("size", 0),
                    offset=item.get("offset", 0),
                    resource=bool(item.get("resource", False)),
                    resource_type=item.get("resource_type"),
                    compressed=bool(item.get("compressed", False)),
                    total=item.get("total", 0),
                    ext=ext,
                )
            )
        return entries

    def files(self) -> list[RPFEntry]:
        return [e for e in self.entries if e.type == "file"]

    def slot(self, entry: RPFEntry) -> bytes:
        return self.data[entry.offset : entry.offset + entry.size]

    def summary(self) -> dict[str, Any]:
        return {"archive": self.path.name, "entry_count": self.count, "file_count": len(self.files()), "extensions": dict(sorted(self.exts.items()))}


def zstd_decompress(data: bytes) -> bytes:
    if shutil.which("zstd") is None:
        raise RuntimeError("zstd CLI is required for this research scanner")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as fh:
        fh.write(data)
        temp_name = fh.name
    try:
        proc = subprocess.run(
            ["zstd", "-d", "-q", "--single-thread", "--stdout", temp_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("latin-1", "ignore")[:200] or f"zstd failed: {proc.returncode}")
        return proc.stdout
    finally:
        try:
            Path(temp_name).unlink()
        except OSError:
            pass


def decode_payload(raw: bytes) -> tuple[str, bytes, str]:
    try:
        if raw.startswith(b"RSC") and len(raw) > 12:
            return "rsc_zstd", zstd_decompress(raw[12:]), ""
        if raw.startswith(ZSTD_MAGIC):
            return "zstd", zstd_decompress(raw), ""
        return "raw", raw, ""
    except Exception as exc:
        return "decode_failed", b"", str(exc)


def text_from_bytes(data: bytes) -> str | None:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = data.decode(enc)
            sample = text[:2000]
            if sum(1 for c in sample if c.isprintable() or c in "\r\n\t") >= max(1, len(sample) * 0.70):
                return text
        except Exception:
            pass
    strings = [m.group(0).decode("latin-1", "replace") for m in re.finditer(rb"[\x20-\x7E]{4,}", data)][:100]
    return "\n".join(strings) if strings else None


def should_scan(archive_name: str, entry: RPFEntry, include_cutscenes: bool) -> bool:
    path = entry.path.lower()
    archive = archive_name.lower()
    if archive == "camera.rpf":
        if (path.startswith("root/camera/cutscenes/") or path.startswith("root/camera/cutscenesfinal/")) and not include_cutscenes:
            return False
        return path.startswith("root/camera/")
    if archive == "naturalmotion.rpf":
        return True
    if archive == "act.rpf":
        return any(x in path for x in ["list.txt", "actversion", "default_character.wat", "donothing.wat", "guntricks.wat", "rifle_1892win.wat"])
    if archive == "tune_d11generic.rpf":
        return any(
            x in path
            for x in [
                "weapons/base_pistol", "weapons/base_dualpistol", "weapons/base_rifle", "weapons/base_repeater",
                "weapons/base_shotgun", "weapons/base_sniperrifle", "weaponarcgroupcollection", "hrssimtune",
            ]
        )
    if archive == "content.rpf":
        return entry.ext in {".xml", ".tr", ".txt"} and any(
            x in path
            for x in ["ai/tasks.tr", "ai/game_main.tr", "movementtuning.xml", "ui/transitions/camera.sc.xml", "init/inventory/inventory.xml", "gringo"]
        )
    return entry.ext in TEXT_LIKE_EXTS


def hit_counts(text: str) -> tuple[int, dict[str, int]]:
    lower = text.lower()
    hits: dict[str, int] = {}
    total = 0
    for category, tokens in CATEGORIES.items():
        for token in tokens:
            count = lower.count(token.lower())
            if count:
                hits[f"{category}:{token}"] = count
                total += count
    return total, hits


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["archive", "entry_path", "ext", "stored_size", "resource", "resource_type", "decode_kind", "decoded_size", "text_chars", "priority", "hit_total", "hits", "error"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fields)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["hits"] = json.dumps(out.get("hits", {}), sort_keys=True)
            writer.writerow({field: out.get(field, "") for field in fields})


def scan_archive(path: Path, outdir: Path, include_cutscenes: bool, export_text: bool) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    rpf = RPF6(path)
    rows: list[dict[str, Any]] = []
    snippets: list[dict[str, Any]] = []
    export_root = outdir / "extracted_text" / path.stem
    for entry in rpf.files():
        if not should_scan(path.name, entry, include_cutscenes):
            continue
        kind, body, error = decode_payload(rpf.slot(entry))
        text = text_from_bytes(body)
        if text is None:
            continue
        total, hits = hit_counts(text)
        priority = total + (10 if hits else 0)
        row = {
            "archive": path.name,
            "entry_path": entry.path,
            "ext": entry.ext,
            "stored_size": entry.size,
            "resource": entry.resource,
            "resource_type": entry.resource_type,
            "decode_kind": kind,
            "decoded_size": len(body),
            "text_chars": len(text),
            "priority": priority,
            "hit_total": total,
            "hits": hits,
            "error": error,
        }
        rows.append(row)
        if len(snippets) < 100 and (priority > 0 or path.name.lower() in {"camera.rpf", "naturalmotion.rpf"}):
            snippets.append({"archive": path.name, "entry_path": entry.path, "snippet": text[:1200]})
        if export_text and priority > 0:
            safe = entry.path.replace("/", "__").replace("\\", "__")
            out = export_root / f"{safe}.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text[:500000], encoding="utf-8", errors="ignore")
    rows.sort(key=lambda item: (item["priority"], item["hit_total"], item["text_chars"]), reverse=True)
    return rpf.summary(), rows, snippets


def render_md(summaries: list[dict[str, Any]], rows: list[dict[str, Any]], snippets: list[dict[str, Any]]) -> str:
    lines = ["# Code RED VR Motion Research Report", "", "## Archives scanned", ""]
    for summary in summaries:
        lines.append(f"- `{summary['archive']}`: files={summary['file_count']} extensions={summary['extensions']}")
    lines.extend(["", "## High-value hits", ""])
    for row in rows[:60]:
        brief = ", ".join(f"{key.split(':', 1)[1]}={value}" for key, value in list(row.get("hits", {}).items())[:8])
        lines.append(f"- `{row['archive']}::{row['entry_path']}` priority={row['priority']} hits={row['hit_total']} kind={row['decode_kind']} :: {brief}")
    lines.extend(
        [
            "", "## Findings", "",
            "- `camera.rpf` is the first-person/VR camera lab target. Start with top-level camera config before broad cutscene cameras.",
            "- `tune_d11generic.rpf` is the first two-hand weapon data target because weapon base files expose ACT/AnimSet/IK/Muzzle/camera fields.",
            "- `naturalmotion.rpf` and `act.rpf` provide body/pose/arm reaction clues; use them after weapon presentation is stable.",
            "- `content.rpf` provides task/control flow clues for aim, draw, fire, holster, and camera transitions.",
            "", "## Text snippets", "",
        ]
    )
    for item in snippets[:40]:
        lines.append(f"### `{item['archive']}::{item['entry_path']}`")
        lines.append("```text")
        lines.append(item["snippet"].replace("`", "\\`")[:600])
        lines.append("```")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only VR motion/camera/body scanner for Code RED RPF archives")
    parser.add_argument("--archive", action="append", required=True, help="RPF archive to scan. Can be repeated.")
    parser.add_argument("--outdir", default="reports/vr_motion_research")
    parser.add_argument("--include-cutscenes", action="store_true", help="Also scan camera cutscene files. Slower and noisier.")
    parser.add_argument("--export-text", action="store_true", help="Export matched decoded text payloads alongside reports.")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    snippets: list[dict[str, Any]] = []
    for archive in args.archive:
        path = Path(archive)
        summary, rows, snips = scan_archive(path, outdir, args.include_cutscenes, args.export_text)
        summaries.append(summary)
        all_rows.extend(rows)
        snippets.extend(snips)
        write_csv(outdir / f"{path.stem}_hits.csv", rows)
    all_rows.sort(key=lambda item: (item["priority"], item["hit_total"], item["text_chars"]), reverse=True)
    write_csv(outdir / "vr_motion_research_hits.csv", all_rows)
    summary = {"archives": summaries, "hit_count": len(all_rows), "top_hits": all_rows[:100], "snippets": snippets[:80]}
    (outdir / "vr_motion_research_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (outdir / "vr_motion_research_report.md").write_text(render_md(summaries, all_rows, snippets), encoding="utf-8")
    print(f"Wrote VR motion research reports to {outdir}")


if __name__ == "__main__":
    main()
