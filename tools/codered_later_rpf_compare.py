#!/usr/bin/env python3
"""Temporarily extract readable later-version RPF entries and compare them.

This is intentionally conservative:
- extracts only text/readable/string-bearing entries;
- writes payloads under the Red Dead game temp folder, outside the repo;
- writes comparison/remap indexes into Code_RED research/log folders.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import string
import sys
import zlib
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

try:
    import zstandard as zstd
except Exception:  # pragma: no cover - reported in output if unavailable
    zstd = None  # type: ignore


CODE_RED_ROOT = Path(__file__).resolve().parents[1]
RED_DEAD_ROOT = CODE_RED_ROOT.parent
GAME_ROOT = RED_DEAD_ROOT / "game"
OLD_ROOT = GAME_ROOT / "BACKUP BEFORE MODDING" / "rdr1" / "mods" / "root"
TEMP_EXTRACT_ROOT = GAME_ROOT / "_CodeRED_Temp_Later_RPF_Extract_20260502"
OUT_DIR = CODE_RED_ROOT / "research - Scan" / "IMPORTANT_later_rpf_compare_2026-05-02"
LOG_NOTE = CODE_RED_ROOT / "logs" / "IMPORTANT_CodeRED_Later_RPF_Compare_2026-05-02.md"

READABLE_EXTS = {
    ".xml", ".txt", ".tr", ".strtbl", ".stbl", ".cst", ".csv", ".cfg",
    ".ini", ".list", ".clist", ".xlist", ".mtl", ".fx", ".weap", ".tune",
    ".vehsim", ".vehinput", ".vehmodel", ".vehgyro", ".vehstuck", ".dat",
}
STRING_SCAN_EXTS = {
    ".wsc", ".csc", ".sco", ".cutbin", ".ctb", ".cft", ".cfd", ".ctd",
    ".cnm", ".csp", ".csg", ".cedt", ".cas", ".cvd", ".csf", ".wgd",
}
IMPORTANT_TERMS = (
    "vehicle", "spawn", "car01x", "truck01x", "wagon", "stagecoach",
    "faction", "law", "hostile", "enemy", "ally", "companion", "follow",
    "gringo", "cutscene", "cinvehicle", "camera", "multiplayer", "freemode",
    "session", "nav", "terrain", "locset", "template_vehicle",
    "string", "strings", "subtitle", "actor_names", "menu", "ui",
)
PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")


@dataclass
class ExtractRow:
    version_id: str
    archive_path: str
    entry_index: int
    internal_path: str
    guessed_name: str
    guessed_reference_paths: str
    extract_mode: str
    extracted_path: str
    size_in_archive: int
    payload_size: int
    payload_sha1: str
    old_match_status: str
    old_exact_path: str
    old_sha1_matches: str
    matched_terms: str
    error: str = ""


@dataclass
class ArchiveRow:
    version_id: str
    archive_path: str
    entry_count: int
    file_count: int
    extracted_count: int
    skipped_count: int
    error_count: int
    errors: str


@dataclass
class VersionDiffRow:
    internal_path: str
    versions_present: str
    sha1_count: int
    status: str
    version_sha1s: str
    version_sizes: str
    extracted_paths: str
    old_match_statuses: str
    matched_terms: str


def load_rpf_utils():
    path = CODE_RED_ROOT / "tools - Implement" / "rpf_patch_utils.py"
    spec = importlib.util.spec_from_file_location("codered_rpf_patch_utils", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["codered_rpf_patch_utils"] = module
    spec.loader.exec_module(module)
    return module


RPF = load_rpf_utils()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def safe_name(value: str) -> str:
    value = value.replace("\\", "_").replace("/", "_").replace(":", "_")
    return re.sub(r"[^A-Za-z0-9_. -]+", "_", value)[:180] or "entry"


def rel_to_game(path: Path) -> str:
    try:
        return str(path.relative_to(RED_DEAD_ROOT))
    except ValueError:
        return str(path)


def discover_archives() -> list[tuple[str, Path]]:
    candidates = [
        ("live_content", GAME_ROOT / "content.rpf"),
        ("live_2026_content", GAME_ROOT / "2026" / "content.rpf"),
        ("live_camera", GAME_ROOT / "camera.rpf"),
        ("live_tune", GAME_ROOT / "tune_d11generic.rpf"),
        ("live_gringores", GAME_ROOT / "gringores.rpf"),
        ("live_strings", GAME_ROOT / "strings_d11generic.rpf"),
        ("live_navres", GAME_ROOT / "navres.rpf"),
        ("live_psocache", GAME_ROOT / "psocache.rpf"),
        ("base_content", GAME_ROOT / "base" / "content.rpf"),
        ("base_cutscene", GAME_ROOT / "base" / "cutscene.rpf"),
        ("base_old_tune", GAME_ROOT / "base" / "OLDtune_d11generic.rpf"),
        ("putback_content", GAME_ROOT / "PUT BACK ASAP" / "content.rpf"),
        ("putback_camera", GAME_ROOT / "PUT BACK ASAP" / "camera.rpf"),
        ("putback_tune", GAME_ROOT / "PUT BACK ASAP" / "tune_d11generic.rpf"),
    ]
    return [(version, path) for version, path in candidates if path.exists()]


def build_reference_maps(root: Path) -> dict:
    by_rel: dict[str, dict] = {}
    by_leaf_hash: dict[int, list[dict]] = defaultdict(list)
    by_sha1: dict[str, list[dict]] = defaultdict(list)
    if not root.exists():
        return {"by_rel": by_rel, "by_leaf_hash": by_leaf_hash, "by_sha1": by_sha1}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        rel = str(path.relative_to(root)).replace("/", "\\")
        digest = sha1_bytes(data)
        info = {"path": str(path), "relative_path": rel, "sha1": digest, "size": len(data)}
        by_rel[rel.lower()] = info
        by_leaf_hash[RPF.rdr_name_hash(path.name)].append(info)
        by_sha1[digest].append(info)
    return {"by_rel": by_rel, "by_leaf_hash": by_leaf_hash, "by_sha1": by_sha1}


def decompress_slot(raw: bytes, ent: dict) -> bytes:
    if ent.get("is_resource"):
        return raw
    if not ent.get("is_compressed"):
        return raw
    if raw.startswith(b"\x28\xB5\x2F\xFD"):
        if zstd is None:
            raise RuntimeError("zstandard module unavailable")
        max_size = int(ent.get("total_size") or 0) or 64 * 1024 * 1024
        return zstd.ZstdDecompressor().decompress(raw, max_output_size=max_size)
    for wb in (-15, 15, 31):
        try:
            return zlib.decompress(raw, wb)
        except Exception:
            pass
    raise RuntimeError("unsupported compressed slot")


def is_probably_text(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:8192]
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    if b"\x00" in sample:
        return False
    printable = set(bytes(string.printable, "ascii"))
    score = sum(1 for b in sample if b in printable or b in b"\r\n\t")
    return score / max(1, len(sample)) > 0.82


def extract_strings(data: bytes, limit: int = 500) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for match in PRINTABLE_RE.finditer(data):
        text = match.group(0).decode("latin-1", "replace").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
        if len(out) >= limit:
            break
    return out


def matched_terms(text: str, path_text: str) -> list[str]:
    haystack = f"{path_text}\n{text[:300000]}".lower()
    return [term for term in IMPORTANT_TERMS if term in haystack]


def choose_reference(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    readable = [c for c in candidates if Path(c["relative_path"]).suffix.lower() in READABLE_EXTS]
    return readable[0] if readable else candidates[0]


def guess_entry_name(ent: dict, refs: dict) -> tuple[str, list[dict]]:
    name = ent.get("name") or ""
    if name and not name.startswith("0x"):
        return name, []
    candidates = refs["by_leaf_hash"].get(ent.get("name_off"), [])
    chosen = choose_reference(candidates)
    return (Path(chosen["relative_path"]).name if chosen else name), candidates


def internal_rel(ent: dict, guessed_name: str) -> str:
    path = (ent.get("path") or "").replace("/", "\\")
    if path.lower().startswith("root\\"):
        path = path[5:]
    parts = path.split("\\") if path else []
    if parts and parts[-1].startswith("0x") and guessed_name and not guessed_name.startswith("0x"):
        parts[-1] = guessed_name
    return "\\".join(parts) if parts else guessed_name


def should_try_extract(ent: dict, guessed_name: str, candidate_refs: list[dict], archive: Path) -> bool:
    ext = Path(guessed_name).suffix.lower()
    if ext in READABLE_EXTS or ext in STRING_SCAN_EXTS:
        return True
    if "strings" in archive.name.lower():
        return True
    if candidate_refs:
        return any(Path(ref["relative_path"]).suffix.lower() in READABLE_EXTS | STRING_SCAN_EXTS for ref in candidate_refs)
    name = (ent.get("path") or "").lower()
    return any(term in name for term in ("content", "camera", "string", "tune", "gringo"))


def compare_status(payload_sha1: str, rel: str, refs: dict, candidate_refs: list[dict]) -> tuple[str, str, str]:
    old_exact = refs["by_rel"].get(rel.lower())
    sha_matches = refs["by_sha1"].get(payload_sha1, [])
    sha_paths = "|".join(ref["relative_path"] for ref in sha_matches[:20])
    if old_exact:
        if old_exact["sha1"] == payload_sha1:
            return "exact_path_same", old_exact["relative_path"], sha_paths
        return "exact_path_changed", old_exact["relative_path"], sha_paths
    for ref in candidate_refs:
        if ref["sha1"] == payload_sha1:
            return "leaf_hash_same", ref["relative_path"], sha_paths
    if candidate_refs:
        return "leaf_hash_changed", "|".join(ref["relative_path"] for ref in candidate_refs[:20]), sha_paths
    if sha_matches:
        return "sha1_same_elsewhere", "", sha_paths
    return "no_reference", "", ""


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def scan_and_extract(archives: list[tuple[str, Path]], refs: dict, temp_root: Path) -> tuple[list[ExtractRow], list[ArchiveRow]]:
    rows: list[ExtractRow] = []
    archive_rows: list[ArchiveRow] = []
    temp_root.mkdir(parents=True, exist_ok=True)

    for version_id, archive in archives:
        errors: list[str] = []
        extracted_count = 0
        skipped_count = 0
        try:
            info = RPF.parse(archive, with_debug=True)
        except Exception as ex:
            archive_rows.append(ArchiveRow(version_id, str(archive), 0, 0, 0, 0, 1, repr(ex)))
            continue
        for ent in info["entries"]:
            if ent.get("type") != "file":
                continue
            guessed_name, candidate_refs = guess_entry_name(ent, refs)
            rel = internal_rel(ent, guessed_name)
            if not should_try_extract(ent, guessed_name, candidate_refs, archive):
                skipped_count += 1
                continue
            try:
                raw = RPF.read_slot(archive, ent)
                payload = decompress_slot(raw, ent)
                mode = "text" if Path(guessed_name).suffix.lower() in READABLE_EXTS or is_probably_text(payload) else "strings"
                if mode == "text":
                    try:
                        text = payload.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        text = payload.decode("latin-1", "replace")
                    out_data = text.encode("utf-8")
                    out_suffix = ""
                else:
                    strings = extract_strings(payload)
                    if not strings:
                        skipped_count += 1
                        continue
                    text = "\n".join(strings)
                    out_data = text.encode("utf-8")
                    out_suffix = ".strings.txt"
                terms = matched_terms(text, f"{archive.name}\\{rel}")
                if not terms and mode != "text":
                    skipped_count += 1
                    continue
                out_path = temp_root / safe_name(version_id) / safe_name(rel + out_suffix)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(out_data)
                digest = sha1_bytes(payload)
                status, old_exact, sha_paths = compare_status(digest, rel, refs, candidate_refs)
                rows.append(
                    ExtractRow(
                        version_id=version_id,
                        archive_path=str(archive),
                        entry_index=int(ent.get("index", -1)),
                        internal_path=rel,
                        guessed_name=guessed_name,
                        guessed_reference_paths="|".join(ref["relative_path"] for ref in candidate_refs[:20]),
                        extract_mode=mode,
                        extracted_path=str(out_path),
                        size_in_archive=int(ent.get("size_in_archive") or 0),
                        payload_size=len(payload),
                        payload_sha1=digest,
                        old_match_status=status,
                        old_exact_path=old_exact,
                        old_sha1_matches=sha_paths,
                        matched_terms=";".join(terms),
                    )
                )
                extracted_count += 1
            except Exception as ex:
                errors.append(f"{ent.get('index')}:{ent.get('path')}:{type(ex).__name__}:{ex}")
                if len(errors) > 40:
                    errors = errors[:40]
                skipped_count += 1
        archive_rows.append(
            ArchiveRow(
                version_id=version_id,
                archive_path=str(archive),
                entry_count=int(info.get("entry_count") or 0),
                file_count=int(info.get("file_count") or 0),
                extracted_count=extracted_count,
                skipped_count=skipped_count,
                error_count=len(errors),
                errors=" | ".join(errors[:20]),
            )
        )
    return rows, archive_rows


def render_markdown(rows: list[ExtractRow], archives: list[ArchiveRow], temp_root: Path) -> str:
    status_counts = defaultdict(int)
    version_counts = defaultdict(int)
    for row in rows:
        status_counts[row.old_match_status] += 1
        version_counts[row.version_id] += 1
    version_diffs = build_version_diffs(rows)
    changed_paths = [row for row in version_diffs if row.status == "different_between_versions"]
    lines = [
        "# IMPORTANT - Later RPF Temporary Extraction Compare",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "Temporarily extracted readable/text-bearing entries from later/live RPF archives in the Red Dead `game` folder for comparison against the extracted reference root.",
        "",
        f"Temporary extraction folder: `{temp_root}`",
        f"Reference root: `{OLD_ROOT}`",
        "",
        "## Archive Results",
        "",
    ]
    for archive in archives:
        lines.append(f"- `{archive.version_id}` files={archive.file_count} extracted={archive.extracted_count} skipped={archive.skipped_count} errors={archive.error_count} path=`{archive.archive_path}`")
    lines.extend([
        "",
        "## Compare Summary",
        "",
        f"- Extracted readable entries: {len(rows)}",
        f"- Match statuses: `{json.dumps(dict(status_counts), sort_keys=True)}`",
        f"- Version counts: `{json.dumps(dict(version_counts), sort_keys=True)}`",
        f"- Version-diff rows: {len(version_diffs)}",
        f"- Changed across versions: {len(changed_paths)}",
        "",
        "## Changed Across Versions",
        "",
    ])
    for row in changed_paths[:50]:
        lines.append(f"- `{row.internal_path}` versions={row.versions_present} sha1s={row.sha1_count} terms={row.matched_terms}")
    lines.extend([
        "",
        "## Best Remap Leads",
        "",
    ])
    for row in rows[:80]:
        lines.append(f"- `{row.version_id}:{row.internal_path}` -> `{row.old_match_status}` old=`{row.old_exact_path}` terms={row.matched_terms}")
    lines.extend([
        "",
        "## Output Files",
        "",
        "- `later_rpf_extract_manifest.csv` - every extracted readable entry.",
        "- `later_rpf_archive_summary.csv` - per-archive extraction/error counts.",
        "- `later_rpf_remap_candidates.csv` - rows with old-root comparison status for remapping.",
        "- `later_rpf_version_diffs.csv` - same internal paths grouped across later/live versions.",
        "- `later_rpf_changed_between_versions.csv` - only entries whose payload changed across versions.",
        "- `later_rpf_compare.json` - structured archive and extraction metadata.",
        "",
    ])
    return "\n".join(lines)


def build_version_diffs(rows: list[ExtractRow]) -> list[VersionDiffRow]:
    grouped: dict[str, list[ExtractRow]] = defaultdict(list)
    for row in rows:
        grouped[row.internal_path.lower()].append(row)
    out: list[VersionDiffRow] = []
    for _key, group in grouped.items():
        group = sorted(group, key=lambda r: r.version_id)
        versions = [r.version_id for r in group]
        sha1s = sorted({r.payload_sha1 for r in group})
        if len(group) == 1:
            status = "single_version"
        elif len(sha1s) == 1:
            status = "same_across_versions"
        else:
            status = "different_between_versions"
        out.append(
            VersionDiffRow(
                internal_path=group[0].internal_path,
                versions_present="|".join(versions),
                sha1_count=len(sha1s),
                status=status,
                version_sha1s="|".join(f"{r.version_id}:{r.payload_sha1}" for r in group),
                version_sizes="|".join(f"{r.version_id}:{r.payload_size}" for r in group),
                extracted_paths="|".join(r.extracted_path for r in group),
                old_match_statuses="|".join(sorted({r.old_match_status for r in group})),
                matched_terms=";".join(sorted({term for r in group for term in r.matched_terms.split(";") if term})),
            )
        )
    return sorted(out, key=lambda r: (r.status != "different_between_versions", r.internal_path.lower()))


def write_outputs(rows: list[ExtractRow], archive_rows: list[ArchiveRow], out_dir: Path, temp_root: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    row_dicts = [asdict(row) for row in rows]
    archive_dicts = [asdict(row) for row in archive_rows]
    fields = list(ExtractRow.__dataclass_fields__.keys())
    archive_fields = list(ArchiveRow.__dataclass_fields__.keys())
    diff_rows = build_version_diffs(rows)
    diff_fields = list(VersionDiffRow.__dataclass_fields__.keys())
    write_csv(out_dir / "later_rpf_extract_manifest.csv", row_dicts, fields)
    write_csv(out_dir / "later_rpf_remap_candidates.csv", row_dicts, fields)
    write_csv(out_dir / "later_rpf_archive_summary.csv", archive_dicts, archive_fields)
    write_csv(out_dir / "later_rpf_version_diffs.csv", [asdict(row) for row in diff_rows], diff_fields)
    write_csv(
        out_dir / "later_rpf_changed_between_versions.csv",
        [asdict(row) for row in diff_rows if row.status == "different_between_versions"],
        diff_fields,
    )
    (out_dir / "later_rpf_compare.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "temp_extract_root": str(temp_root),
                "reference_root": str(OLD_ROOT),
                "archives": archive_dicts,
                "extractions": row_dicts,
                "version_diffs": [asdict(row) for row in diff_rows],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "later_rpf_compare.md").write_text(render_markdown(rows, archive_rows, temp_root), encoding="utf-8")
    LOG_NOTE.parent.mkdir(parents=True, exist_ok=True)
    LOG_NOTE.write_text(render_markdown(rows, archive_rows, temp_root), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract readable later RPF entries and compare them with extracted root references.")
    parser.add_argument("--temp-root", type=Path, default=TEMP_EXTRACT_ROOT)
    parser.add_argument("--outdir", type=Path, default=OUT_DIR)
    parser.add_argument("--archive", action="append", type=Path, help="Specific archive to include. Can repeat.")
    args = parser.parse_args()

    if args.archive:
        archives = [(path.stem, path) for path in args.archive if path.exists()]
    else:
        archives = discover_archives()
    refs = build_reference_maps(OLD_ROOT)
    rows, archive_rows = scan_and_extract(archives, refs, args.temp_root)
    rows.sort(key=lambda r: (r.version_id, r.internal_path.lower()))
    write_outputs(rows, archive_rows, args.outdir, args.temp_root)
    print(f"Archives scanned: {len(archive_rows)}")
    print(f"Extracted readable entries: {len(rows)}")
    print(f"Temp extraction: {args.temp_root}")
    print(f"Output: {args.outdir}")
    print(f"Log note: {LOG_NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
