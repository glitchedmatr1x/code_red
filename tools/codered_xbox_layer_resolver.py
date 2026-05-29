from __future__ import annotations

"""Code RED Xbox layer resolver and XSC/SCO detector.

Public-safe helper for Xbox/Xenia research. It indexes user-supplied folders, ZIPs,
and RPF name probes, builds an effective layered file tree, and exports compact
reports/GPT packets without bundling or redistributing game files.

This tool is intentionally read-only. It does not decrypt, unpack, or write RPFs.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

SCRIPT_EXTS = {".wsc", ".xsc", ".csc", ".sco", ".wsv"}
TEXT_EXTS = {".xml", ".xst", ".txt", ".json", ".csv", ".ini", ".cfg", ".md", ".yaml", ".yml"}
ARCHIVE_EXTS = {".rpf", ".zip"}
PROFILE_KEYWORDS = [
    "avatar", "profile", "lobby", "network", "netmachine", "signin", "sign-in",
    "hudsceneonline", "taskmachine", "playmp", "xprofile", "save", "stfs",
]
INIT_POP_KEYWORDS = ["rdr2init", "initpopulation", "/init/pop/", "population", "dlc_inventory", "zombie", "zombiepack"]
RPF_NAME_EXTENSIONS = sorted({
    "wsc", "xsc", "csc", "sco", "xst", "xml", "txt", "csv", "json", "ini",
    "rpf", "wtd", "wtx", "xtd", "xtx", "dds", "wft", "wfd", "wvd", "wsi",
    "dat", "bin", "cfg", "rel", "img", "awc", "wav", "mp3", "ogg",
})
RPF_NAME_PATTERN = re.compile(
    rb"[A-Za-z0-9_ ./\\\-$]{1,220}\.(?:" + b"|".join(re.escape(ext.encode("ascii")) for ext in RPF_NAME_EXTENSIONS) + rb")",
    re.IGNORECASE,
)
PRINTABLE_RE = re.compile(rb"[\x20-\x7E]{4,}")
MAX_PREVIEW_BYTES = 2 * 1024 * 1024


@dataclass
class LayerInput:
    name: str
    path: str
    priority: int


@dataclass
class LayerFile:
    norm_path: str
    display_path: str
    layer: str
    priority: int
    source: str
    kind: str
    ext: str
    size: int = 0
    sha256: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class EffectiveFile:
    norm_path: str
    effective_layer: str
    effective_priority: int
    kind: str
    ext: str
    size: int
    present_in_layers: list[str]
    layer_count: int
    status: str
    focus_tags: list[str] = field(default_factory=list)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def normalize_path(path: str) -> str:
    text = str(path).replace("\\", "/")
    if "::" in text:
        text = text.split("::", 1)[1]
    # Remove absolute drive-looking prefixes while preserving game-relative content paths.
    text = re.sub(r"^[A-Za-z]:/", "", text)
    text = text.strip("/ ")
    return re.sub(r"/+", "/", text).lower()


def kind_for_path(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in SCRIPT_EXTS:
        return "Script"
    if ext in TEXT_EXTS:
        return "Text"
    if ext in ARCHIVE_EXTS:
        return "Archive"
    if ext in {".wtd", ".wtx", ".xtd", ".xtx", ".dds", ".png", ".jpg", ".jpeg", ".bmp"}:
        return "Texture"
    if ext in {".wft", ".wfd", ".wvd", ".wsi"}:
        return "Mesh"
    if ext in {".awc", ".wav", ".mp3", ".ogg"}:
        return "Audio"
    return "Other"


def tags_for_path(norm_path: str) -> list[str]:
    tags: list[str] = []
    lower = norm_path.lower()
    if any(key in lower for key in PROFILE_KEYWORDS):
        tags.append("profile/avatar/network")
    if any(key in lower for key in INIT_POP_KEYWORDS):
        tags.append("init/pop/zombie")
    if lower.endswith(tuple(SCRIPT_EXTS)):
        tags.append("script")
    if lower.endswith(".xsc") or lower.endswith(".sco"):
        tags.append("xbox-script")
    return tags


def script_detector_bytes(data: bytes, display_path: str = "") -> dict:
    ext = Path(display_path).suffix.lower()
    head = data[:32]
    printable = []
    for match in PRINTABLE_RE.finditer(data[:MAX_PREVIEW_BYTES]):
        printable.append({
            "offset": match.start(),
            "offset_hex": f"0x{match.start():X}",
            "length": len(match.group()),
            "text": match.group().decode("ascii", errors="replace"),
        })
        if len(printable) >= 150:
            break
    keyword_hits: dict[str, int] = {}
    blob_lower = data[:MAX_PREVIEW_BYTES].lower()
    for key in PROFILE_KEYWORDS + INIT_POP_KEYWORDS + ["launchavatarpicker", "mp_avatarpicker", "rdr_mp_save", "blunderbuss"]:
        needle = key.encode("ascii", errors="ignore").lower()
        if needle:
            count = blob_lower.count(needle)
            if count:
                keyword_hits[key] = count
    return {
        "path": display_path,
        "ext": ext,
        "size": len(data),
        "sha256": sha256_bytes(data),
        "header_hex": head.hex(" ").upper(),
        "header_ascii": "".join(chr(b) if 32 <= b <= 126 else "." for b in head),
        "looks_like_script": ext in SCRIPT_EXTS,
        "candidate_family": ext[1:].upper() if ext in SCRIPT_EXTS else "unknown",
        "keyword_hits": keyword_hits,
        "strings_preview": printable,
        "notes": [
            "Read-only detector. It does not decrypt or compile scripts.",
            "Use same-size edits or a validated decoder/repacker before writing patches.",
        ],
    }


def scan_folder(path: Path, layer: LayerInput, max_files: int = 20000) -> list[LayerFile]:
    rows: list[LayerFile] = []
    base = path.resolve()
    count = 0
    for fp in sorted(base.rglob("*")):
        if not fp.is_file():
            continue
        if any(part in {".git", "__pycache__", "build", "logs", "CodeRED_Backups"} for part in fp.parts):
            continue
        rel = fp.relative_to(base).as_posix()
        try:
            stat = fp.stat()
            digest = ""
            if stat.st_size <= 1024 * 1024 and fp.suffix.lower() in SCRIPT_EXTS | TEXT_EXTS:
                digest = sha256_bytes(fp.read_bytes())
            rows.append(LayerFile(
                norm_path=normalize_path(rel),
                display_path=rel,
                layer=layer.name,
                priority=layer.priority,
                source="folder",
                kind=kind_for_path(rel),
                ext=fp.suffix.lower(),
                size=stat.st_size,
                sha256=digest,
            ))
        except OSError as exc:
            rows.append(LayerFile(normalize_path(rel), rel, layer.name, layer.priority, "folder", "Other", fp.suffix.lower(), 0, "", [str(exc)]))
        count += 1
        if count >= max_files:
            rows.append(LayerFile("<truncated>", "<truncated>", layer.name, layer.priority, "folder", "Other", "", 0, "", [f"max_files {max_files} reached"]))
            break
    return rows


def scan_zip(path: Path, layer: LayerInput, max_files: int = 30000) -> list[LayerFile]:
    rows: list[LayerFile] = []
    with zipfile.ZipFile(path, "r") as zf:
        for idx, info in enumerate(zf.infolist()):
            if idx >= max_files:
                rows.append(LayerFile("<truncated>", "<truncated>", layer.name, layer.priority, "zip", "Other", "", 0, "", [f"max_files {max_files} reached"]))
                break
            if info.is_dir():
                continue
            member = info.filename.replace("\\", "/")
            rows.append(LayerFile(
                norm_path=normalize_path(member),
                display_path=member,
                layer=layer.name,
                priority=layer.priority,
                source="zip",
                kind=kind_for_path(member),
                ext=Path(member).suffix.lower(),
                size=info.file_size,
                notes=["ZIP member indexed read-only"],
            ))
    return rows


def is_rpf(path: Path) -> bool:
    try:
        return path.suffix.lower() == ".rpf" and path.read_bytes()[:4].upper().startswith(b"RPF")
    except OSError:
        return False


def scan_rpf_names(path: Path, layer: LayerInput, max_names: int = 15000, read_limit: int = 128 * 1024 * 1024) -> list[LayerFile]:
    rows: list[LayerFile] = []
    try:
        with path.open("rb") as fh:
            blob = fh.read(min(path.stat().st_size, read_limit))
    except OSError as exc:
        return [LayerFile("<read-failed>", str(path), layer.name, layer.priority, "rpf", "Archive", ".rpf", 0, "", [str(exc)])]
    seen: set[str] = set()
    for match in RPF_NAME_PATTERN.finditer(blob):
        raw = match.group(0).decode("utf-8", errors="ignore").strip(" \t\r\n\x00").replace("\\", "/")
        norm = normalize_path(raw)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        rows.append(LayerFile(norm, raw, layer.name, layer.priority, "rpf-name-probe", kind_for_path(raw), Path(raw).suffix.lower(), 0, "", ["RPF name probe only; use MagicRDR/low-level extractor for exact contents"]))
        if len(rows) >= max_names:
            rows.append(LayerFile("<truncated>", "<truncated>", layer.name, layer.priority, "rpf-name-probe", "Other", "", 0, "", [f"max_names {max_names} reached"]))
            break
    if not rows:
        rows.append(LayerFile("<rpf-detected>", path.name, layer.name, layer.priority, "rpf-name-probe", "Archive", ".rpf", path.stat().st_size, "", ["RPF magic detected; no readable member names found in bounded scan"]))
    return rows


def scan_layer(layer: LayerInput) -> list[LayerFile]:
    path = Path(layer.path)
    if path.is_dir():
        return scan_folder(path, layer)
    if path.suffix.lower() == ".zip" or zipfile.is_zipfile(path):
        return scan_zip(path, layer)
    if path.suffix.lower() == ".rpf" or is_rpf(path):
        return scan_rpf_names(path, layer)
    if path.is_file():
        return [LayerFile(normalize_path(path.name), path.name, layer.name, layer.priority, "file", kind_for_path(path.name), path.suffix.lower(), path.stat().st_size)]
    return [LayerFile("<missing>", str(path), layer.name, layer.priority, "missing", "Other", "", 0, "", ["Path does not exist"])]


def build_effective(rows: Sequence[LayerFile]) -> list[EffectiveFile]:
    grouped: dict[str, list[LayerFile]] = {}
    for row in rows:
        if row.norm_path.startswith("<"):
            continue
        grouped.setdefault(row.norm_path, []).append(row)
    effective: list[EffectiveFile] = []
    for norm, items in grouped.items():
        sorted_items = sorted(items, key=lambda r: (r.priority, r.layer))
        winner = sorted_items[-1]
        layers = [item.layer for item in sorted_items]
        if len(items) == 1:
            status = "single-layer"
        else:
            # If all known hashes match, mark as duplicated same; otherwise assume override/different.
            hashes = {item.sha256 for item in sorted_items if item.sha256}
            status = "duplicated-same" if len(hashes) == 1 and hashes else "overridden-by-higher-layer"
        effective.append(EffectiveFile(
            norm_path=norm,
            effective_layer=winner.layer,
            effective_priority=winner.priority,
            kind=winner.kind,
            ext=winner.ext,
            size=winner.size,
            present_in_layers=layers,
            layer_count=len(items),
            status=status,
            focus_tags=tags_for_path(norm),
        ))
    return sorted(effective, key=lambda r: (r.kind, r.norm_path))


def analyze_layers(layers: Sequence[LayerInput]) -> dict:
    rows: list[LayerFile] = []
    for layer in layers:
        rows.extend(scan_layer(layer))
    effective = build_effective(rows)
    counts_by_kind: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    focus_rows: list[EffectiveFile] = []
    for item in effective:
        counts_by_kind[item.kind] = counts_by_kind.get(item.kind, 0) + 1
        counts_by_status[item.status] = counts_by_status.get(item.status, 0) + 1
        if item.focus_tags:
            focus_rows.append(item)
    return {
        "tool": "Code RED Xbox Layer Resolver",
        "version": "pass4-xbox-layer-resolver",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "public_safety": {
            "mode": "read-only index/report",
            "raw_game_files_embedded": False,
            "notes": "Reports contain paths, sizes, hashes for small user-supplied text/script files only; no file payloads are exported.",
        },
        "layers": [asdict(layer) for layer in layers],
        "source_file_count": len(rows),
        "effective_file_count": len(effective),
        "counts_by_kind": counts_by_kind,
        "counts_by_status": counts_by_status,
        "focus_file_count": len(focus_rows),
        "focus_files": [asdict(item) for item in focus_rows[:500]],
        "effective_files": [asdict(item) for item in effective],
        "source_rows": [asdict(row) for row in rows],
    }


def write_reports(report: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "xbox_layer_report.json"
    focus_path = out_dir / "xbox_layer_focus_files.csv"
    effective_path = out_dir / "xbox_layer_effective_tree.csv"
    packet_path = out_dir / "xbox_layer_gpt_packet.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with effective_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["norm_path", "effective_layer", "status", "kind", "ext", "size", "present_in_layers", "focus_tags"])
        writer.writeheader()
        for row in report.get("effective_files", []):
            writer.writerow({
                "norm_path": row.get("norm_path", ""),
                "effective_layer": row.get("effective_layer", ""),
                "status": row.get("status", ""),
                "kind": row.get("kind", ""),
                "ext": row.get("ext", ""),
                "size": row.get("size", 0),
                "present_in_layers": ";".join(row.get("present_in_layers", [])),
                "focus_tags": ";".join(row.get("focus_tags", [])),
            })
    with focus_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["norm_path", "effective_layer", "status", "kind", "ext", "size", "present_in_layers", "focus_tags"])
        writer.writeheader()
        for row in report.get("focus_files", []):
            writer.writerow({
                "norm_path": row.get("norm_path", ""),
                "effective_layer": row.get("effective_layer", ""),
                "status": row.get("status", ""),
                "kind": row.get("kind", ""),
                "ext": row.get("ext", ""),
                "size": row.get("size", 0),
                "present_in_layers": ";".join(row.get("present_in_layers", [])),
                "focus_tags": ";".join(row.get("focus_tags", [])),
            })
    packet = {
        "tool": report.get("tool"),
        "version": report.get("version"),
        "layers": report.get("layers", []),
        "counts_by_kind": report.get("counts_by_kind", {}),
        "counts_by_status": report.get("counts_by_status", {}),
        "focus_file_count": report.get("focus_file_count", 0),
        "focus_files_preview": report.get("focus_files", [])[:80],
        "recommended_next_prompt_for_gpt": "Analyze this Xbox layered effective tree. Identify which layer owns profile/avatar/networking/init/population scripts before proposing any patch.",
    }
    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return {"json": str(json_path), "effective_csv": str(effective_path), "focus_csv": str(focus_path), "gpt_packet": str(packet_path)}


def parse_layer_arg(text: str, priority: int) -> LayerInput:
    if "=" in text:
        name, path = text.split("=", 1)
        name = name.strip() or f"layer{priority}"
        path = path.strip()
    else:
        path = text.strip()
        name = Path(path).stem or f"layer{priority}"
    return LayerInput(name=name, path=path, priority=priority)


def inspect_script_file(path: Path) -> dict:
    data = path.read_bytes()
    return script_detector_bytes(data, str(path))


def self_test() -> dict:
    fake_rows = [
        LayerFile("content/init/rdr2init.xsc", "content/init/rdr2init.xsc", "base", 0, "folder", "Script", ".xsc", 10),
        LayerFile("content/init/rdr2init.xsc", "content/init/rdr2init.xsc", "layer_0", 1, "folder", "Script", ".xsc", 11),
        LayerFile("content/ui/net/profileeditor/main.sc.xml", "content/ui/net/profileeditor/main.sc.xml", "layer_0", 1, "folder", "Text", ".xml", 12),
    ]
    effective = build_effective(fake_rows)
    return {
        "ok": any(item.norm_path.endswith("rdr2init.xsc") and item.effective_layer == "layer_0" for item in effective),
        "effective_count": len(effective),
        "focus_count": sum(1 for item in effective if item.focus_tags),
        "script_detector_sample": script_detector_bytes(b"XSC\x00LaunchAvatarPicker\x00mp_avatarpicker\x00", "sample.xsc"),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED Xbox layer resolver and XSC/SCO detector.")
    parser.add_argument("--layer", action="append", default=[], help="Layer input as name=path or path. Repeat in priority order: base first, highest override last.")
    parser.add_argument("--out", default="reports/xbox_layer_resolver", help="Output report folder.")
    parser.add_argument("--inspect-script", help="Read-only XSC/SCO/WSC/CSC detector report for one script.")
    parser.add_argument("--self-test", action="store_true", help="Run built-in sanity test.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.self_test:
        payload = self_test()
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("ok") else 1
    if args.inspect_script:
        payload = inspect_script_file(Path(args.inspect_script))
        print(json.dumps(payload, indent=2))
        return 0
    if not args.layer:
        parser.error("At least one --layer is required unless using --inspect-script or --self-test.")
    layers = [parse_layer_arg(text, idx) for idx, text in enumerate(args.layer)]
    report = analyze_layers(layers)
    paths = write_reports(report, Path(args.out))
    print(json.dumps({"ok": True, "report_paths": paths, "summary": {k: report[k] for k in ["source_file_count", "effective_file_count", "counts_by_kind", "counts_by_status", "focus_file_count"]}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
