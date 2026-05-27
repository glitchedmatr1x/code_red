from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

try:
    import codered_rpf_utils as rpf
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"Could not import codered_rpf_utils.py from tools folder: {exc}")

KEYWORDS = [
    "cheat", "debug", "menu", "pause", "extras", "rdrExtrasLayer", "CheatsList",
    "UI_Cheat", "UI_OpenCheatsMsgBox", "GameCheat", "OnKeyboardActivate",
    "keyboard", "spawn", "actor", "travel", "teleport", "waypoint", "mission",
    "script", "marshal", "frontend", "ui_", "popup", "option",
]

UI_EXTS = {".xml", ".sc.xml", ".strtbl", ".txt"}
SCRIPT_EXTS = {".wsc", ".sco", ".csc", ".xsc"}


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def iter_inputs(input_path: Path, work: Path) -> list[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        out = work / input_path.stem
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(out)
        return sorted(out.rglob("*.rpf"))
    if input_path.is_file() and input_path.suffix.lower() == ".rpf":
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("*.rpf"))
    raise FileNotFoundError(input_path)


def parse_rsc_header(data: bytes) -> dict | None:
    if len(data) < 12:
        return None
    ident_be = int.from_bytes(data[:4], "big", signed=False)
    ident_le = int.from_bytes(data[:4], "little", signed=False)
    names = {
        1381188357: "RSC05_ASCII",
        1381188358: "RSC06_ASCII",
        1381188485: "RSC85_ASCII",
        1381188486: "RSC86_ASCII",
        88298322: "RSC05",
        105075538: "RSC06",
        2235781970: "RSC85",
        2252559186: "RSC86",
    }
    if ident_be in names and names[ident_be].endswith("ASCII"):
        ident = ident_be
        endian = "little"
    elif ident_le in names:
        ident = ident_le
        endian = "little"
    elif ident_be in names:
        ident = ident_be
        endian = "big"
    else:
        return None

    def u32(off: int) -> int:
        return int.from_bytes(data[off:off + 4], endian, signed=False) if off + 4 <= len(data) else 0

    name = names[ident].replace("_ASCII", "")
    is_extended = name in {"RSC85", "RSC86"}
    return {
        "name": name,
        "resource_type": u32(4),
        "flag1": u32(8),
        "flag2": u32(12) if is_extended else 0,
        "header_size": 16 if is_extended else 12,
    }


def searchable_payload(data: bytes) -> tuple[bytes, str]:
    """Return bytes suitable for string search plus a compact decode note.

    RPF resource entries often arrive as RSC85/RSC86 wrappers. This does not
    decompile scripts; it only removes the resource wrapper/decrypts the payload
    when Code RED already knows the standard RPF6 resource AES path.
    """
    res = parse_rsc_header(data)
    if not res:
        return data, "raw"
    payload = data[res["header_size"]:]
    note = f"{res['name']}:payload"
    if res["name"] in {"RSC85", "RSC86"} and res["resource_type"] == 2 and payload:
        try:
            dec = rpf.decrypt(payload)
            if dec != payload:
                payload = dec
                note += "+aes"
        except Exception:
            note += "+aes_failed"
    return payload, note


def safe_extract_text(blob: bytes) -> str:
    return blob.decode("utf-8", "ignore") or blob.decode("latin-1", "ignore")


def classify_entry(path: str, ext: str) -> str:
    p = path.lower()
    if "/ui/" in p or ext in UI_EXTS:
        return "ui_or_string"
    if ext in SCRIPT_EXTS or "/scripting/" in p or "/missions/" in p:
        return "script_or_mission"
    if "/cutscene/" in p or ext in {".cutbin", ".wcdt"}:
        return "cutscene"
    if "/fragments/" in p or ext in {".wft", ".wedt"}:
        return "fragment_model"
    if "/mapres/" in p or ext in {".wtd"}:
        return "map_texture"
    return "other"


def scan_archive(archive: Path, out_dir: Path, *, extract_hits: bool = False) -> dict:
    info = rpf.parse(archive, with_debug=True)
    rows = []
    hits = []
    extract_dir = out_dir / "extracted_hits" / archive.stem

    for ent in info["entries"]:
        if ent.get("type") != "file":
            continue
        path = ent.get("path", "")
        ext = ent.get("extension", "")
        row = {
            "archive": archive.name,
            "path": path,
            "name": ent.get("name", ""),
            "extension": ext,
            "class": classify_entry(path, ext),
            "size_in_archive": ent.get("size_in_archive", ""),
            "total_size": ent.get("total_size", ""),
            "is_resource": ent.get("is_resource", False),
            "is_compressed": ent.get("is_compressed", False),
            "keywords": "",
            "sha1": "",
            "extract_error": "",
            "decode_note": "",
        }
        try:
            data = rpf.extract(archive, ent)
            row["sha1"] = sha1_bytes(data)
            search_blob, decode_note = searchable_payload(data)
            row["decode_note"] = decode_note
            searchable = (path + "\n" + safe_extract_text(search_blob)).lower()
            found = [k for k in KEYWORDS if k.lower() in searchable]
            row["keywords"] = ";".join(found)
            if found or row["class"] in {"ui_or_string", "script_or_mission"}:
                hits.append(row.copy())
                if extract_hits and (found or row["class"] == "ui_or_string"):
                    dest = extract_dir / path.replace("root/", "")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
        except Exception as exc:
            row["extract_error"] = str(exc)[:300]
            if row["class"] in {"ui_or_string", "script_or_mission"}:
                hits.append(row.copy())
        rows.append(row)

    summary = {
        "archive": archive.name,
        "path": str(archive),
        "entry_count": info["entry_count"],
        "file_count": info["file_count"],
        "dir_count": info["dir_count"],
        "resolved_count": info["resolved_count"],
        "debug_offset": info["debug_offset"],
        "enc_flag": info["enc_flag"],
        "extensions": dict(info["ext_counts"]),
        "script_or_mission_count": sum(1 for r in rows if r["class"] == "script_or_mission"),
        "ui_or_string_count": sum(1 for r in rows if r["class"] == "ui_or_string"),
        "keyword_hit_count": sum(1 for r in rows if r["keywords"]),
    }
    return {"summary": summary, "rows": rows, "hits": hits}


def write_csv(path: Path, rows: Iterable[dict]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan base/override RPF folders for debug, cheat, menu, UI, and script candidates.")
    ap.add_argument("input", help="base folder, base.zip, or one .rpf")
    ap.add_argument("--out", default="reports/override_menu_finder", help="output report folder")
    ap.add_argument("--extract-hits", action="store_true", help="extract UI/text hit payloads for review")
    args = ap.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="codered_override_menu_finder_") as td:
        rpfs = iter_inputs(input_path, Path(td))
        all_rows = []
        all_hits = []
        summaries = []
        for archive in rpfs:
            result = scan_archive(archive, out_dir, extract_hits=args.extract_hits)
            summaries.append(result["summary"])
            all_rows.extend(result["rows"])
            all_hits.extend(result["hits"])

    report = {
        "input": str(input_path),
        "archive_count": len(summaries),
        "summaries": summaries,
        "top_findings": [
            "Override archives are install-position-sensitive; treat a folder named base/ as a game-folder override, not a full root dump.",
            "UI option XML files only define visible menu shell/route behavior; actual code may live in mission scripts, native UI classes, executable/DLL code, Flash/WSF, or opaque bytecode.",
            "Do not promote candidate script hits into Code RED menu code until the native/wrapper signature or script behavior is proven.",
        ],
    }
    (out_dir / "override_menu_finder_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_csv(out_dir / "override_rpf_entries.csv", all_rows)
    write_csv(out_dir / "override_menu_script_hits.csv", all_hits)

    md = [
        "# Code RED Override Menu Finder Report",
        "",
        f"Input: `{input_path}`",
        f"Archives scanned: {len(summaries)}",
        "",
        "## Archive summaries",
        "",
    ]
    for s in summaries:
        md.extend([
            f"### {s['archive']}",
            "",
            f"- entries: {s['entry_count']}",
            f"- files: {s['file_count']}",
            f"- resolved names: {s['resolved_count']}",
            f"- extensions: `{s['extensions']}`",
            f"- script/mission candidates: {s['script_or_mission_count']}",
            f"- UI/string candidates: {s['ui_or_string_count']}",
            f"- keyword hits: {s['keyword_hit_count']}",
            "",
        ])
    md.extend([
        "## Output files",
        "",
        "- `override_menu_finder_summary.json`",
        "- `override_rpf_entries.csv`",
        "- `override_menu_script_hits.csv`",
        "",
        "## Rule",
        "",
        "This finder is read-only. It reports candidates only; it does not patch, move, or rewrite archives.",
    ])
    (out_dir / "override_menu_finder_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
