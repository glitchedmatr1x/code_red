#!/usr/bin/env python3
"""Code RED VR / first-person / two-hand weapon research scanner.

Scans RDR1 RPF6 archives for camera, controls, NaturalMotion, body-part, IK,
weapon hand, and first-person clues. This is research-only: it does not patch
archives and it never writes back to source RPFs.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

KEYWORDS = {
    "camera": [
        "firstperson", "first person", "vehiclefirstperson", "fov", "lens", "nearclip", "near plane",
        "lookstick", "look stick", "pitch", "yaw", "roll", "zoom", "boom", "recenter", "constraint",
        "gamecamera", "camera", "camdynamic", "cameralens",
    ],
    "controls": [
        "input", "control", "controller", "look", "aim", "shoot", "fire", "trigger", "holster", "reload",
        "combat", "weapon", "drawweapon", "readyweapon", "playeraim", "lookatifpossible",
    ],
    "hands_weapons": [
        "lefthand", "rightHand", "righthand", "left hand", "right hand", "leftarm", "rightarm",
        "ikoffset", "ikoffsethold", "muzzleoffset", "animset", "actfilename", "actroot", "dualpistol",
        "pistol", "rifle", "repeater", "shotgun", "sniper", "canShootFromCamera", "weaponarcgroup",
    ],
    "body_naturalmotion": [
        "naturalmotion", "euphoria", "activepose", "bodyrelax", "forcetobodypart", "bodypart",
        "partindex", "ragdoll", "limb", "arm", "leg", "spine", "head", "torso", "pose", "brace",
        "bullet", "shot", "impulse", "balance", "stiffness",
    ],
    "vr_goal": [
        "openvr", "vr", "stereo", "hmd", "headpose", "head pose", "portal", "desktopdisplay", "displayportal",
    ],
}

TEXT_EXTENSIONS = {
    ".xml", ".txt", ".cmt", ".ccm", ".cm", ".camdynamicboomtunemanager", ".weap", ".tr", ".strtbl",
    ".dat", ".meta", ".ini", ".cfg", ".json",
}

ARCHIVE_LABELS = {
    "camera": "camera.rpf",
    "naturalmotion": "naturalmotion.rpf",
    "content": "content.rpf",
    "tune": "tune_d11generic.rpf",
}


@dataclass
class HitRow:
    archive_label: str
    archive_path: str
    entry_path: str
    entry_name: str
    extension: str
    category: str
    keyword: str
    line_number: int
    snippet: str


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "tools" / "codered_wsi_explorer.py").exists() or (candidate / "python_workbench.py").exists():
            return candidate
    return current


def load_rpf6(repo_root: Path):
    candidates = [
        repo_root / "tools" / "codered_wsi_explorer.py",
        repo_root / "codered_wsi_explorer.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            if str(candidate.parent) not in sys.path:
                sys.path.insert(0, str(candidate.parent))
            module = load_module(candidate, "codered_vr_motion_rpf6")
            rpf6 = getattr(module, "RPF6", None)
            if rpf6 is not None:
                return rpf6
    raise RuntimeError("RPF6 parser not found. Expected tools/codered_wsi_explorer.py")


def decode_text(raw: bytes) -> tuple[bool, str, str]:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            text = raw.decode(encoding)
            if text.count("\x00") > max(8, len(text) // 5):
                continue
            return True, text, encoding
        except Exception:
            pass
    return False, "", ""


def binary_strings(raw: bytes, limit: int = 600) -> str:
    found = []
    for match in re.finditer(rb"[\x20-\x7E]{4,}", raw):
        found.append(match.group(0).decode("latin-1", "replace"))
        if len(found) >= limit:
            break
    return "\n".join(found)


def line_snippet(line: str, max_len: int = 240) -> str:
    clean = " ".join(line.strip().split())
    if len(clean) > max_len:
        return clean[: max_len - 3] + "..."
    return clean


def scan_text(archive_label: str, archive_path: Path, entry: Any, text: str) -> list[HitRow]:
    rows: list[HitRow] = []
    lines = text.splitlines() or [text]
    lower_lines = [line.lower() for line in lines]
    for category, keywords in KEYWORDS.items():
        for keyword in keywords:
            needle = keyword.lower()
            for index, lower in enumerate(lower_lines, start=1):
                if needle in lower:
                    rows.append(
                        HitRow(
                            archive_label=archive_label,
                            archive_path=str(archive_path),
                            entry_path=getattr(entry, "path", ""),
                            entry_name=getattr(entry, "name", ""),
                            extension=getattr(entry, "ext", ""),
                            category=category,
                            keyword=keyword,
                            line_number=index,
                            snippet=line_snippet(lines[index - 1]),
                        )
                    )
                    break
    return rows


def safe_rel_path(path_text: str, fallback: str) -> Path:
    parts = [part for part in path_text.replace("\\", "/").split("/") if part not in {"", ".", ".."}]
    if not parts:
        parts = [fallback]
    return Path(*parts)


def should_try_text(entry: Any) -> bool:
    ext = getattr(entry, "ext", "").lower()
    name = getattr(entry, "name", "").lower()
    path = getattr(entry, "path", "").lower()
    if ext in TEXT_EXTENSIONS:
        return True
    return any(term in path or term in name for terms in KEYWORDS.values() for term in terms)


def scan_archive(label: str, archive: Path, rpf6_cls: Any, extract_root: Path | None = None) -> dict[str, Any]:
    rpf = rpf6_cls(archive)
    files = rpf.files() if callable(getattr(rpf, "files", None)) else []
    rows: list[HitRow] = []
    extracted: list[dict[str, Any]] = []
    extension_counts: dict[str, int] = {}
    for entry in files:
        ext = getattr(entry, "ext", "") or "<none>"
        extension_counts[ext] = extension_counts.get(ext, 0) + 1
        if not should_try_text(entry):
            continue
        try:
            raw = rpf.slot(entry)
            if isinstance(raw, str):
                raw_bytes = raw.encode("utf-8")
            else:
                raw_bytes = bytes(raw)
        except Exception:
            continue
        ok, text, encoding = decode_text(raw_bytes)
        if not ok:
            text = binary_strings(raw_bytes)
            encoding = "binary_strings"
        if not text.strip():
            continue
        entry_rows = scan_text(label, archive, entry, text)
        rows.extend(entry_rows)
        if extract_root is not None and (entry_rows or getattr(entry, "ext", "").lower() in TEXT_EXTENSIONS):
            out = extract_root / label / safe_rel_path(getattr(entry, "path", ""), getattr(entry, "name", "entry.txt"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8", errors="replace")
            extracted.append(
                {
                    "entry_path": getattr(entry, "path", ""),
                    "output": str(out),
                    "encoding": encoding,
                    "hit_count": len(entry_rows),
                }
            )
    return {
        "label": label,
        "archive": str(archive),
        "summary": rpf.summary() if callable(getattr(rpf, "summary", None)) else {},
        "extension_counts": dict(sorted(extension_counts.items())),
        "hits": [asdict(row) for row in rows],
        "extracted": extracted,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fields)
        if fields:
            writer.writeheader()
        writer.writerows(rows)


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Code RED VR Motion Research Scan",
        "",
        f"Generated: `{report.get('generated_at')}`",
        "",
        "## Purpose",
        "",
        "Research camera, first-person, controls, hand/weapon IK, and NaturalMotion/body-part clues for the future VR route.",
        "",
        "## Archives",
        "",
    ]
    for item in report.get("archives", []):
        lines.append(f"- `{item['label']}`: `{item['archive']}` — hits: `{len(item.get('hits') or [])}`")
    lines.extend(["", "## Top Findings", ""])
    all_hits = report.get("all_hits", [])
    if not all_hits:
        lines.append("No keyword hits were found in the scanned archives.")
    else:
        for row in all_hits[:150]:
            lines.append(
                f"- `{row['archive_label']}` `{row['entry_path']}` [{row['category']} / `{row['keyword']}`] line {row['line_number']}: {row['snippet']}"
            )
    lines.extend(
        [
            "",
            "## Recommended Next Experiments",
            "",
            "1. Camera: inspect first-person/FOV/lookstick constraints from `camera.rpf` and build a copied-archive camera test.",
            "2. Weapons: compare `base_dualpistol.weap` against rifle/repeater/shotgun IK and ACT/AnimSet fields.",
            "3. Body: map NaturalMotion `leftArm`, `rightArm`, `activePose`, `bodyRelax`, and `forceToBodyPart` fields before changing body reactions.",
            "4. Controls: use `content.rpf` task/UI findings to identify aim/draw/fire/holster control route candidates.",
            "5. VR bridge: keep OpenVR/Desktop portal display as a later route after first-person weapon/body presentation is stable.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan RDR1 archives for VR/first-person/body/weapon-control research clues")
    parser.add_argument("--repo-root", default="", help="Code RED repo root. Defaults to current tree search.")
    parser.add_argument("--camera", default="", help="Path to camera.rpf")
    parser.add_argument("--naturalmotion", default="", help="Path to naturalmotion.rpf")
    parser.add_argument("--content", default="", help="Path to content.rpf")
    parser.add_argument("--tune", default="", help="Path to tune_d11generic.rpf")
    parser.add_argument("--outdir", default="reports/vr_motion_research", help="Output report folder")
    parser.add_argument("--extract-text", action="store_true", help="Extract text/string previews for matching entries")
    args = parser.parse_args()

    repo_root = find_repo_root(Path(args.repo_root or Path.cwd()))
    rpf6_cls = load_rpf6(repo_root)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    extract_root = outdir / "extracted_text" if args.extract_text else None

    archive_args = {
        "camera": args.camera,
        "naturalmotion": args.naturalmotion,
        "content": args.content,
        "tune": args.tune,
    }
    archives = []
    all_hits: list[dict[str, Any]] = []
    for label, path_text in archive_args.items():
        if not path_text:
            continue
        archive = Path(path_text)
        if not archive.exists():
            archives.append({"label": label, "archive": str(archive), "missing": True, "hits": []})
            continue
        item = scan_archive(label, archive, rpf6_cls, extract_root=extract_root)
        archives.append(item)
        all_hits.extend(item.get("hits") or [])

    all_hits.sort(key=lambda row: (row.get("category", ""), row.get("archive_label", ""), row.get("entry_path", ""), row.get("line_number", 0)))
    report = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(repo_root),
        "archives": archives,
        "all_hits": all_hits,
        "keyword_categories": KEYWORDS,
    }
    (outdir / "vr_motion_research_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_csv(outdir / "vr_motion_research_hits.csv", all_hits)
    (outdir / "vr_motion_research_summary.md").write_text(build_markdown(report), encoding="utf-8")
    print(f"Wrote VR motion research reports to {outdir}")
    print(f"Hits: {len(all_hits)}")


if __name__ == "__main__":
    main()
