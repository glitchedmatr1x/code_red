#!/usr/bin/env python3
"""Stage a conservative multiplayer content restore folder from donor scripts.

Pass 1 is intentionally non-destructive:
- inventory donor and PC script resources;
- correlate decoded PC update-thread strings with donor script names;
- recover hash-named donor aliases only when JOOAT evidence matches;
- copy selected raw donor files into an import-ready restore folder;
- keep unresolved or conversion-needed files separate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codered_wsc.analysis import extract_strings  # noqa: E402
from codered_wsc.resource import KeyOptions, ResourceError, open_script  # noqa: E402


TOOL = "codered_mp_content_restore_pass1"
VERSION = 1
SCRIPT_EXTS = {".xsc", ".csc", ".sco", ".wsc"}
DONOR_SCRIPT_EXTS = {".xsc", ".csc", ".sco"}
HASH_NAME_RE = re.compile(r"^(?:0x)?([0-9a-fA-F]{8})$")
UPDATE_THREAD_RE = re.compile(r"(?:short|medium|long)_update_thread(?:_z)?\.(?:wsc|sco|xsc|csc)$", re.I)


@dataclass(frozen=True)
class Scope:
    name: str
    root: Path
    source_kind: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def joaat(value: str) -> int:
    acc = 0
    for byte in value.lower().encode("utf-8"):
        acc = (acc + byte) & 0xFFFFFFFF
        acc = (acc + (acc << 10)) & 0xFFFFFFFF
        acc ^= acc >> 6
    acc = (acc + (acc << 3)) & 0xFFFFFFFF
    acc ^= acc >> 11
    acc = (acc + (acc << 15)) & 0xFFFFFFFF
    return acc & 0xFFFFFFFF


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fields or [])
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def normalized_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def multiplayer_rel(rel: str) -> str:
    low = rel.lower()
    marker = "/multiplayer/"
    if marker in low:
        index = low.index(marker)
        return rel[index + len(marker) :]
    return ""


def logical_key(rel: str) -> str:
    mp_rel = multiplayer_rel(rel)
    candidate = mp_rel or rel
    path = Path(candidate)
    if path.suffix.lower() in SCRIPT_EXTS:
        candidate = path.with_suffix("").as_posix()
    return candidate.lower()


def classify_file(path: Path) -> tuple[bool, bool]:
    suffix = path.suffix.lower()
    hash_named = bool(HASH_NAME_RE.match(path.name) or HASH_NAME_RE.match(path.stem))
    return suffix in SCRIPT_EXTS or hash_named, hash_named


def manifest_scope(scope: Scope) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not scope.root.exists():
        return rows
    for path in sorted((p for p in scope.root.rglob("*") if p.is_file()), key=lambda item: item.as_posix().lower()):
        selected, hash_named = classify_file(path)
        if not selected:
            continue
        rel = normalized_rel(path, scope.root)
        rows.append(
            {
                "scope": scope.name,
                "source_kind": scope.source_kind,
                "source_root": str(scope.root),
                "source_path": str(path),
                "relative_path": rel,
                "multiplayer_relative_path": multiplayer_rel(rel),
                "logical_key": logical_key(rel),
                "name": path.name,
                "stem": path.stem,
                "extension": path.suffix.lower(),
                "is_hash_named": hash_named,
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return rows


def update_scripts(pc_root: Path) -> list[Path]:
    if not pc_root.exists():
        return []
    return sorted(
        (path for path in pc_root.rglob("*") if path.is_file() and UPDATE_THREAD_RE.search(path.name)),
        key=lambda path: path.as_posix().lower(),
    )


def decode_strings(path: Path, rdr_exe: Path | None) -> tuple[list[dict[str, Any]], str]:
    if path.suffix.lower() not in SCRIPT_EXTS:
        return [], "not a supported script extension"
    try:
        resource = open_script(path, KeyOptions(rdr_exe=str(rdr_exe) if rdr_exe else ""))
    except (FileNotFoundError, ResourceError, ValueError) as exc:
        return [], str(exc)
    if resource.decode_error:
        return [], resource.decode_error
    return extract_strings(resource.decoded), ""


def reference_tokens(row: dict[str, Any]) -> set[str]:
    path = Path(str(row["multiplayer_relative_path"] or row["relative_path"]))
    values = {
        str(row["name"]).lower(),
        str(row["stem"]).lower(),
        str(row["logical_key"]).lower(),
        path.as_posix().lower(),
        path.with_suffix("").as_posix().lower() if path.suffix else path.as_posix().lower(),
    }
    return {value for value in values if value and not HASH_NAME_RE.match(Path(value).name)}


def match_update_references(
    script_paths: list[Path],
    donor_rows: list[dict[str, Any]],
    rdr_exe: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tokens: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in donor_rows:
        if row["extension"] not in DONOR_SCRIPT_EXTS or row["is_hash_named"]:
            continue
        for token in reference_tokens(row):
            tokens[token].append(row)

    string_rows: list[dict[str, Any]] = []
    hit_rows: list[dict[str, Any]] = []
    decode_rows: list[dict[str, Any]] = []
    seen_hits: set[tuple[str, int, str, str]] = set()
    for script in script_paths:
        strings, error = decode_strings(script, rdr_exe)
        decode_rows.append(
            {
                "update_script": str(script),
                "decoded_string_count": len(strings),
                "decode_status": "decoded" if not error else "decode_failed",
                "decode_error": error,
            }
        )
        for string in strings:
            text = str(string["text"])
            low = text.lower()
            record = {
                "update_script": str(script),
                "string_offset": string["offset"],
                "string_offset_hex": string["offset_hex"],
                "text": text,
                "contains_multiplayer_term": any(term in low for term in ("multiplayer", "freemode", "mp_", "/mp", "net")),
                "contains_extension_term": any(term in low for term in (".xsc", ".csc", ".sco", ".wsc")),
            }
            if record["contains_multiplayer_term"] or record["contains_extension_term"]:
                string_rows.append(record)
            for token, rows in tokens.items():
                if token not in low:
                    continue
                for row in rows:
                    hit_key = (str(script), int(string["offset"]), token, str(row["source_path"]))
                    if hit_key in seen_hits:
                        continue
                    seen_hits.add(hit_key)
                    explicit_extension = row["extension"] in low
                    hit_rows.append(
                        {
                            "update_script": str(script),
                            "string_offset": string["offset"],
                            "string_offset_hex": string["offset_hex"],
                            "matched_token": token,
                            "string_text": text,
                            "donor_scope": row["scope"],
                            "donor_relative_path": row["relative_path"],
                            "donor_extension": row["extension"],
                            "logical_key": row["logical_key"],
                            "explicit_extension_match": explicit_extension,
                            "evidence": "decoded update-thread printable string contains donor script token",
                        }
                    )
    return string_rows, hit_rows, decode_rows


def name_candidates(donor_rows: list[dict[str, Any]], reference_hits: list[dict[str, Any]]) -> list[dict[str, str]]:
    candidates: dict[str, str] = {}
    for row in donor_rows:
        if row["is_hash_named"]:
            continue
        name = str(row["name"])
        mp_rel = str(row["multiplayer_relative_path"])
        for value, origin in (
            (name, "donor leaf name"),
            (str(row["stem"]), "donor leaf stem"),
            (mp_rel, "donor multiplayer relative path"),
            (Path(mp_rel).with_suffix("").as_posix() if mp_rel else "", "donor multiplayer relative path without extension"),
        ):
            if value:
                candidates.setdefault(value.lower(), origin)
    for hit in reference_hits:
        token = str(hit["matched_token"])
        if token:
            candidates.setdefault(token.lower(), "decoded update-thread token")
    return [{"candidate": candidate, "origin": origin} for candidate, origin in sorted(candidates.items())]


def hash_recovery_rows(donor_rows: list[dict[str, Any]], candidates: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_hash: dict[int, list[dict[str, str]]] = defaultdict(list)
    for candidate in candidates:
        by_hash[joaat(candidate["candidate"])].append(candidate)
    rows: list[dict[str, Any]] = []
    for row in donor_rows:
        if not row["is_hash_named"]:
            continue
        match = HASH_NAME_RE.match(str(row["name"])) or HASH_NAME_RE.match(str(row["stem"]))
        value = int(match.group(1), 16) if match else -1
        matches = by_hash.get(value, [])
        rows.append(
            {
                "scope": row["scope"],
                "source_path": row["source_path"],
                "relative_path": row["relative_path"],
                "hash_name": row["name"],
                "hash_hex": f"0x{value:08X}" if value >= 0 else "",
                "match_status": "proven_joaat_candidate" if matches else "unresolved",
                "candidate_names": " | ".join(match_row["candidate"] for match_row in matches[:12]),
                "candidate_origins": " | ".join(match_row["origin"] for match_row in matches[:12]),
                "rule": "hash aliases stay unresolved unless filename candidate JOOAT equals hash name",
            }
        )
    return rows


def choose_rows(donor_rows: list[dict[str, Any]], reference_hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    explicit_xsc = {
        str(hit["logical_key"])
        for hit in reference_hits
        if hit["explicit_extension_match"] and hit["donor_extension"] == ".xsc"
    }

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unresolved: list[dict[str, Any]] = []
    for row in donor_rows:
        if row["source_kind"] != "donor":
            continue
        if row["is_hash_named"]:
            unresolved.append({**row, "status": "unresolved_hash_name", "reason": "hash-named donor file is not renamed or imported in Pass 1"})
            continue
        if row["extension"] not in DONOR_SCRIPT_EXTS or not row["multiplayer_relative_path"]:
            unresolved.append({**row, "status": "unresolved_non_script", "reason": "outside donor multiplayer compiled-script lane"})
            continue
        groups[str(row["logical_key"])].append(row)

    chosen: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        extensions = {str(row["extension"]) for row in rows}
        choice: dict[str, Any] | None = None
        reason = ""
        if key in explicit_xsc:
            xsc_rows = [row for row in rows if row["extension"] == ".xsc"]
            choice = xsc_rows[0] if xsc_rows else None
            reason = "decoded PC update-thread evidence explicitly matched XSC extension"
        if choice is None:
            csc_rows = [row for row in rows if row["extension"] == ".csc"]
            if csc_rows:
                choice = csc_rows[0]
                reason = "CSC raw donor chosen when no explicit PC XSC extension call was found; prior PC content restore lane uses CSC MP references"
        if choice is None and len(extensions) == 1 and ".xsc" in extensions:
            row = rows[0]
            unresolved.append(
                {
                    **row,
                    "status": "conversion_needed_or_manual_raw_xsc_review",
                    "reason": "XSC-only donor path has no explicit PC update-thread XSC extension evidence in Pass 1",
                }
            )
        if choice is None and ".sco" in extensions:
            row = rows[0]
            unresolved.append({**row, "status": "conversion_needed", "reason": "SCO-only donor path is not forced into CSC/XSC path"})
        if choice is None:
            continue
        alternatives = [row for row in rows if row is not choice]
        chosen.append(
            {
                **choice,
                "status": "selected_raw_restore",
                "selection_reason": reason,
                "alternative_extensions": " | ".join(sorted(extensions - {str(choice["extension"])})),
                "alternative_sha256": " | ".join(str(row["sha256"]) for row in alternatives),
                "same_logical_candidate_count": len(rows),
            }
        )
    return chosen, unresolved


def comparison_rows(donor_rows: list[dict[str, Any]], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_paths = {str(row["source_path"]) for row in selected}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in donor_rows:
        if row["source_kind"] == "donor" and row["multiplayer_relative_path"] and not row["is_hash_named"]:
            groups[str(row["logical_key"])].append(row)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        hashes = {str(row["sha256"]) for row in rows}
        sizes = {int(row["size"]) for row in rows}
        for row in rows:
            output.append(
                {
                    "logical_key": key,
                    "scope": row["scope"],
                    "relative_path": row["relative_path"],
                    "extension": row["extension"],
                    "size": row["size"],
                    "sha256": row["sha256"],
                    "selected": str(row["source_path"]) in selected_paths,
                    "same_logical_candidate_count": len(rows),
                    "same_sha256_across_logical_candidates": len(hashes) == 1,
                    "same_size_across_logical_candidates": len(sizes) == 1,
                }
            )
    return output


def copy_selected(chosen: list[dict[str, Any]], restore_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in chosen:
        mp_rel = Path(str(row["multiplayer_relative_path"]))
        source = Path(str(row["source_path"]))
        for release_name in ("release", "release64"):
            target = restore_root / "content" / release_name / "multiplayer" / mp_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            rows.append(
                {
                    "source_path": str(source),
                    "target_path": str(target),
                    "target_content_path": target.relative_to(restore_root).as_posix(),
                    "logical_key": row["logical_key"],
                    "extension": row["extension"],
                    "size": target.stat().st_size,
                    "sha256": sha256(target),
                    "selection_reason": row["selection_reason"],
                }
            )
    (restore_root / "content" / "release" / "multiplayer").mkdir(parents=True, exist_ok=True)
    (restore_root / "content" / "release64" / "multiplayer").mkdir(parents=True, exist_ok=True)
    return rows


def copy_unresolved(unresolved: list[dict[str, Any]], unresolved_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in unresolved:
        source = Path(str(row["source_path"]))
        relative = Path(str(row["scope"])) / Path(str(row["relative_path"]))
        target = unresolved_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rows.append({**row, "unresolved_copy": str(target)})
    return rows


def write_reports(
    out_dir: Path,
    build_dir: Path,
    manifest: list[dict[str, Any]],
    update_strings: list[dict[str, Any]],
    reference_hits: list[dict[str, Any]],
    decode_rows: list[dict[str, Any]],
    hash_rows: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    copied: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "mp_content_script_manifest.csv", manifest)
    write_json(out_dir / "mp_content_script_manifest.json", manifest)
    write_csv(out_dir / "update_script_decode_status.csv", decode_rows)
    write_csv(out_dir / "update_script_reference_strings.csv", update_strings)
    write_csv(
        out_dir / "update_script_reference_hits.csv",
        reference_hits,
        [
            "update_script",
            "string_offset",
            "string_offset_hex",
            "matched_token",
            "string_text",
            "donor_scope",
            "donor_relative_path",
            "donor_extension",
            "logical_key",
            "explicit_extension_match",
            "evidence",
        ],
    )
    write_json(out_dir / "update_script_reference_hits.json", {"decode_status": decode_rows, "hits": reference_hits})
    hits_by_update: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for hit in reference_hits:
        hits_by_update[str(hit["update_script"])].append(hit)
    update_report = [
        "# PC Update Script Multiplayer Reference Report",
        "",
        "This report compares decoded printable update-thread strings to donor multiplayer script filename/path candidates.",
        "A zero count means no direct donor filename token was found in printable strings; it does not rule out hashed or runtime-table references.",
        "",
    ]
    for row in decode_rows:
        hits = hits_by_update.get(str(row["update_script"]), [])
        update_report.extend(
            [
                f"## {Path(str(row['update_script'])).name}",
                "",
                f"- Path: `{row['update_script']}`",
                f"- Decode status: `{row['decode_status']}`",
                f"- Decoded printable strings: `{row['decoded_string_count']}`",
                f"- Direct donor script token hits: `{len(hits)}`",
            ]
        )
        if row["decode_error"]:
            update_report.append(f"- Decode error: `{row['decode_error']}`")
        for hit in hits[:24]:
            update_report.append(f"- `{hit['donor_relative_path']}` via `{hit['matched_token']}` at `{hit['string_offset_hex']}`")
        update_report.append("")
    (out_dir / "update_script_reference_report.md").write_text("\n".join(update_report) + "\n", encoding="utf-8")
    write_csv(out_dir / "hash_name_recovery.csv", hash_rows)
    write_json(out_dir / "hash_name_recovery.json", hash_rows)
    write_csv(out_dir / "donor_logical_candidate_comparison.csv", comparisons)
    write_json(out_dir / "donor_logical_candidate_comparison.json", comparisons)
    write_csv(out_dir / "restore_selection_manifest.csv", selected)
    write_csv(out_dir / "restore_copied_files.csv", copied)
    write_json(out_dir / "restore_selection_manifest.json", {"selected": selected, "copied": copied})
    write_csv(out_dir / "unresolved_files.csv", unresolved)
    write_json(out_dir / "unresolved_files.json", unresolved)

    summary = {
        "tool": TOOL,
        "version": VERSION,
        "manifest_rows": len(manifest),
        "donor_manifest_rows": sum(1 for row in manifest if row["source_kind"] == "donor"),
        "pc_manifest_rows": sum(1 for row in manifest if row["source_kind"] == "pc_current"),
        "update_scripts_checked": len(decode_rows),
        "update_script_reference_hits": len(reference_hits),
        "hash_named_rows": len(hash_rows),
        "hash_names_recovered": sum(1 for row in hash_rows if row["match_status"] != "unresolved"),
        "selected_logical_files": len(selected),
        "copied_restore_files": len(copied),
        "unresolved_files": len(unresolved),
        "restore_root": str(build_dir / "restore"),
        "unresolved_root": str(build_dir / "unresolved"),
        "notes": [
            "No content.rpf was modified.",
            "No script bytes were patched or converted.",
            "CSC is preferred for dual CSC/XSC logical donor paths unless update-thread evidence explicitly names XSC.",
            "XSC-only, SCO-only, and hash-named donor files stay unresolved for manual review in Pass 1.",
        ],
    }
    write_json(out_dir / "mp_content_restore_pass1_summary.json", summary)
    (out_dir / "mp_content_restore_pass1_report.md").write_text(
        "\n".join(
            [
                "# Code RED Multiplayer Content Restore Pass 1",
                "",
                "This is a raw-file inventory and staging pass. It does not overwrite an RPF and it does not patch compiled scripts.",
                "",
                f"- Manifest rows: `{summary['manifest_rows']}`",
                f"- Donor rows: `{summary['donor_manifest_rows']}`",
                f"- PC current rows: `{summary['pc_manifest_rows']}`",
                f"- Update scripts checked: `{summary['update_scripts_checked']}`",
                f"- Update-thread donor-reference hits: `{summary['update_script_reference_hits']}`",
                f"- Hash-name rows: `{summary['hash_named_rows']}`",
                f"- Hash names recovered by candidate JOOAT: `{summary['hash_names_recovered']}`",
                f"- Selected logical raw files: `{summary['selected_logical_files']}`",
                f"- Restore copies written: `{summary['copied_restore_files']}`",
                f"- Unresolved files copied aside: `{summary['unresolved_files']}`",
                "",
                "## Staging",
                "",
                f"- Import-ready raw restore root: `{summary['restore_root']}`",
                f"- Unresolved/manual-review root: `{summary['unresolved_root']}`",
                "",
                "Both `content/release/multiplayer/` and `content/release64/multiplayer/` are staged so Magic RDR import can be tested against the path family the target archive exposes. The source bytes remain donor bytes.",
                "",
                "## Evidence limits",
                "",
                "Printable update-thread strings are used as reference evidence. A missing hit does not prove the script is unused because compiled scripts can refer through hashes or runtime tables.",
                "Hash-named files are not renamed or staged as resolved imports unless a candidate JOOAT match is documented.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "IMPORT_MAGIC_RDR.md").write_text(
        "\n".join(
            [
                "# Magic RDR Import Guide: Multiplayer Restore Pass 1",
                "",
                "Use a backup or a copied `content.rpf`. Do not import into the only live archive.",
                "",
                "1. Open the target PC `content.rpf` in Magic RDR.",
                f"2. Use the staged files under `{build_dir / 'restore'}`.",
                "3. Import files into the matching archive folders. Start with `content/release64/multiplayer/` when that tree exists in the archive.",
                "4. If the archive loader or prior PC file-name list expects `content/release/multiplayer/`, import the matching release mirror instead of changing extensions.",
                "5. Do not import from `unresolved/` until the status report explains the format or hash-name choice.",
                "6. Keep original extensions. Pass 1 does not convert CSC, XSC, or SCO.",
                "7. Save to a copied archive and verify the imported paths before runtime testing.",
                "",
                "Review before import:",
                "",
                "- `restore_selection_manifest.csv` for selected raw donor files and alternatives.",
                "- `donor_logical_candidate_comparison.csv` for same-logical PSN/XENON size and SHA-256 comparison.",
                "- `update_script_reference_hits.csv` for PC update-thread string evidence.",
                "- `hash_name_recovery.csv` and `unresolved_files.csv` for files intentionally withheld.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    psn = Path(args.psn)
    xenon = Path(args.xenon)
    pc_root = Path(args.pc_content)
    out_dir = Path(args.out)
    build_dir = Path(args.build)
    restore_root = build_dir / "restore"
    unresolved_root = build_dir / "unresolved"

    scopes = [
        Scope("donor_psn", psn, "donor"),
        Scope("donor_xenon", xenon, "donor"),
        Scope("pc_current", pc_root, "pc_current"),
    ]
    manifest = [row for scope in scopes for row in manifest_scope(scope)]
    donor_rows = [row for row in manifest if row["source_kind"] == "donor"]
    script_paths = update_scripts(pc_root)
    rdr_exe = Path(args.rdr_exe) if args.rdr_exe else None
    update_strings, reference_hits, decode_rows = match_update_references(script_paths, donor_rows, rdr_exe)
    hash_rows = hash_recovery_rows(donor_rows, name_candidates(donor_rows, reference_hits))
    selected, unresolved = choose_rows(donor_rows, reference_hits)
    comparisons = comparison_rows(donor_rows, selected)
    copied = copy_selected(selected, restore_root)
    unresolved_copies = copy_unresolved(unresolved, unresolved_root)
    return write_reports(
        out_dir,
        build_dir,
        manifest,
        update_strings,
        reference_hits,
        decode_rows,
        hash_rows,
        selected,
        comparisons,
        copied,
        unresolved_copies,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a non-destructive MP donor manifest and raw restore folder.")
    parser.add_argument("--psn", default=str(ROOT / "imports" / "PSN MULTIPLAYER" / "content"))
    parser.add_argument("--xenon", default=str(ROOT / "imports" / "XENON MULTIPLAYER" / "content"))
    parser.add_argument("--pc-content", default=str(ROOT / "game" / "content_extracted"))
    parser.add_argument("--rdr-exe", default=str(ROOT.parent / "RDR.exe"))
    parser.add_argument("--out", default=str(ROOT / "logs" / "mp_content_restore_pass1"))
    parser.add_argument("--build", default=str(ROOT / "build" / "mp_content_restore_pass1"))
    args = parser.parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
