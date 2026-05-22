#!/usr/bin/env python3
"""Build a non-destructive multiplayer readiness report for Code RED.

This pass correlates already-extracted PC files, decoded UI SCXML, update-thread
decode reports, and isolated Pass 2 import folders. It does not write RPFs,
convert script wrappers, or modify compiled script bytes.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

TERMS = [
    "Multiplayer",
    "LAN",
    "System Link",
    "Online",
    "Free Roam",
    "Public",
    "Private",
    "Posse",
    "Matchmaking",
    "NetConf",
    "NetConf_PlayLAN",
    "NetConf_StartGame",
    "NetworkingLayerOffline",
    "NetMachine",
    "Authenticate",
    "auth.success",
    "TriggerMultiplayerLoad",
    "SetGameWish",
    "StartGameWish",
    "MULTI_FREE_ROAM",
    "disabled",
    "hidden",
    "signin",
    "sign-in",
    "profile",
    "network unavailable",
    "offline",
    "gamer profile",
]

PRIORITY_UI_NAMES = {
    "root_content_ui_pausemenu_pausemenuscene.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_networking.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_net_offlinemenu.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_lobby_main.sc.xml.decoded.xml",
}

UPDATE_SCRIPT_NAMES = {
    "medium_update_thread.wsc",
    "long_update_thread.wsc",
    "short_update_thread.wsc",
    "medium_update_thread_z.wsc",
    "long_update_thread_z.wsc",
    "short_update_thread_z.wsc",
    "medium_update_thread_z.sco",
    "long_update_thread_z.sco",
    "short_update_thread_z.sco",
}

UPDATE_REPORT_NAMES = {
    "update_script_reference_report.md",
    "update_script_decode_status.csv",
    "update_script_reference_hits.csv",
    "update_script_reference_strings.csv",
}

TEXT_EXTS = {".xml", ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".diff", ".sc"}
SCRIPT_EXTS = {".wsc", ".sco", ".xsc", ".csc"}
IMPORTANT_RESTORED_NAMES = {
    "freemode.csc",
    "mp_idle.csc",
    "multiplayer_system_thread.csc",
    "multiplayer_update_thread.csc",
    "pr_multiplayer.csc",
    "deathmatch.csc",
    "ctf_base_game.csc",
    "freemode.xsc",
    "mp_idle.xsc",
    "multiplayer_system_thread.xsc",
    "multiplayer_update_thread.xsc",
    "pr_multiplayer.xsc",
    "deathmatch.xsc",
    "ctf_base_game.xsc",
}


@dataclass(frozen=True)
class SourceFile:
    kind: str
    path: Path
    root: Path
    scan_reason: str


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fieldnames = list(fields or [])
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fieldnames:
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def compact(text: str, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()[:limit]


def stable_rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def crc32(path: Path) -> str:
    value = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value = binascii.crc32(chunk, value)
    return f"{value & 0xFFFFFFFF:08X}"


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        sample = text[:4000]
        printable = sum(1 for char in sample if char.isprintable() or char in "\r\n\t")
        if printable / max(1, len(sample)) >= 0.65:
            return text
    return data.decode("utf-8", "replace")


def ascii_strings(data: bytes, min_len: int = 4) -> list[str]:
    return [match.group(0).decode("ascii", "ignore") for match in re.finditer(rb"[\x20-\x7E]{%d,}" % min_len, data)]


def term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    if term.isalpha() and len(term) <= 12:
        return re.compile(rf"\b{escaped}\b", re.I)
    return re.compile(escaped, re.I)


TERM_PATTERNS = {term: term_pattern(term) for term in TERMS}


def hit_category(term: str, excerpt: str) -> str:
    low = f"{term} {excerpt}".lower()
    if any(token in low for token in ("authenticate", "auth.", "signin", "sign-in", "gamer profile", "profile")):
        return "auth_or_profile_gate"
    if any(token in low for token in ("triggermultiplayerload", "setgamewish", "startgamewish", "netconf_startgame")):
        return "runtime_load_route"
    if any(token in low for token in ("netconf_playlan", "system link", " lan", "lan ", "multiplayer")):
        return "local_or_menu_route"
    if any(token in low for token in ("disabled", "hidden", "network unavailable", "offline")):
        return "visibility_or_offline_signal"
    if any(token in low for token in ("public", "private", "online", "matchmaking", "posse")):
        return "online_route_signal"
    return "mp_signal"


def text_scan_rows(source: SourceFile) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = source.path.read_bytes()
    relative = stable_rel(source.path, source.root)
    if source.path.suffix.lower() in TEXT_EXTS or source.path.name.lower().endswith(".decoded.xml"):
        mode = "decoded_text"
        lines = decode_text(data).splitlines()
    elif source.path.suffix.lower() in SCRIPT_EXTS:
        mode = "ascii_strings"
        lines = ascii_strings(data)
    else:
        mode = "filename_only"
        lines = [relative]
    hits: list[dict[str, Any]] = []
    for line_no, line in enumerate(lines, start=1):
        for term, pattern in TERM_PATTERNS.items():
            if pattern.search(line):
                excerpt = compact(line)
                hits.append(
                    {
                        "source_kind": source.kind,
                        "path": str(source.path),
                        "relative_path": relative,
                        "scan_mode": mode,
                        "line_or_string_index": line_no,
                        "term": term,
                        "category": hit_category(term, excerpt),
                        "excerpt": excerpt,
                    }
                )
    source_row = {
        "source_kind": source.kind,
        "path": str(source.path),
        "relative_path": relative,
        "scan_reason": source.scan_reason,
        "scan_mode": mode,
        "size": len(data),
        "suffix": source.path.suffix.lower(),
        "hit_count": len(hits),
        "sha1": sha1(source.path),
        "crc32": crc32(source.path),
    }
    return source_row, hits


def add_source(target: dict[str, SourceFile], kind: str, path: Path, root: Path, reason: str) -> None:
    if path.exists() and path.is_file():
        target[str(path.resolve()).lower()] = SourceFile(kind, path, root, reason)


def discover_sources(args: argparse.Namespace) -> list[SourceFile]:
    found: dict[str, SourceFile] = {}
    pc_root = Path(args.pc_content)
    decoded_ui = Path(args.decoded_ui)
    pass1 = Path(args.pass1_logs)
    route_blocks = Path(args.route_blocks) if args.route_blocks else None
    if decoded_ui.exists():
        for path in sorted(decoded_ui.glob("*.xml"), key=lambda item: item.name.lower()):
            reason = "priority decoded UI route" if path.name.lower() in PRIORITY_UI_NAMES else "decoded UI route corpus"
            add_source(found, "decoded_ui_scxml", path, decoded_ui, reason)
    if pc_root.exists():
        for path in sorted(pc_root.rglob("*"), key=lambda item: item.as_posix().lower()):
            if path.is_file() and path.name.lower() in UPDATE_SCRIPT_NAMES:
                add_source(found, "pc_update_script", path, pc_root, "current PC update-thread resource")
            elif path.is_file() and "boot" in path.name.lower() and path.suffix.lower() in TEXT_EXTS:
                add_source(found, "pc_boot_or_menu", path, pc_root, "current PC boot/menu text resource")
    if pass1.exists():
        for name in UPDATE_REPORT_NAMES:
            add_source(found, "pass1_update_decode_report", pass1 / name, pass1, "Pass 1 update-thread decode evidence")
    if route_blocks and route_blocks.exists():
        for path in sorted(route_blocks.glob("*.md"), key=lambda item: item.name.lower()):
            if any(token in path.name.lower() for token in ("networking", "lanmenu", "plaympconf", "pausemenu")):
                add_source(found, "decoded_route_block_report", path, route_blocks, "existing focused decoded-SCXML route block report")
    for raw_root in args.extra_scan_root:
        root = Path(raw_root)
        if root.exists():
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
                if path.is_file() and (path.suffix.lower() in TEXT_EXTS or path.name.lower() in UPDATE_SCRIPT_NAMES):
                    add_source(found, "extra_scan_root", path, root, "explicit extra scan root")
    for export_root in exported_roots(args):
        if export_root.exists():
            for path in sorted(export_root.rglob("*"), key=lambda item: item.as_posix().lower()):
                if path.is_file():
                    add_source(found, "magic_rdr_export_back", path, export_root, "exported-back Magic RDR verification file")
    return sorted(found.values(), key=lambda item: (item.kind, str(item.path).lower()))


def exported_roots(args: argparse.Namespace) -> list[Path]:
    roots = [Path(value) for value in args.exported_back]
    roots.extend(
        [
            ROOT / "reports" / "mp_content_restore_pass3" / "exported_back",
            ROOT / "logs" / "mp_content_restore_pass3" / "exported_back",
            ROOT / "build" / "mp_content_restore_pass3" / "exported_back",
        ]
    )
    unique: dict[str, Path] = {}
    for root in roots:
        unique[str(root.resolve()).lower()] = root
    return list(unique.values())


def package_rows(pass2_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not pass2_root.exists():
        return rows
    for package in sorted((path for path in pass2_root.iterdir() if path.is_dir()), key=lambda item: item.name.lower()):
        for path in sorted(package.rglob("*"), key=lambda item: item.as_posix().lower()):
            if not path.is_file():
                continue
            rel = stable_rel(path, package)
            rows.append(
                {
                    "package": package.name,
                    "path": str(path),
                    "content_path": rel,
                    "extension": path.suffix.lower(),
                    "size": path.stat().st_size,
                    "important_restored_resource": path.name.lower() in IMPORTANT_RESTORED_NAMES,
                    "sha1": sha1(path),
                    "crc32": crc32(path),
                }
            )
    return rows


def rows_by_key(rows: list[dict[str, Any]], key: str) -> Counter[str]:
    return Counter(str(row.get(key, "")) for row in rows)


def markdown_table(rows: list[list[str]], headers: list[str]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in row) + " |")
    return lines


def first_hits(hits: list[dict[str, Any]], terms: Iterable[str], limit: int = 4) -> list[dict[str, Any]]:
    wanted = {term.lower() for term in terms}
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    source_priority = {
        "decoded_ui_scxml": 0,
        "pc_boot_or_menu": 1,
        "pass1_update_decode_report": 2,
        "pc_update_script": 3,
        "decoded_route_block_report": 4,
    }
    name_priority = {
        "pausemenuscene": 0,
        "networking": 1,
        "plaympconf": 2,
        "lanmenu": 3,
        "lobby_main": 4,
    }

    def rank(hit: dict[str, Any]) -> tuple[int, int, str, int]:
        relative = str(hit["relative_path"]).lower()
        filename_rank = min((value for key, value in name_priority.items() if key in relative), default=9)
        return (
            source_priority.get(str(hit["source_kind"]), 9),
            filename_rank,
            relative,
            int(hit["line_or_string_index"]),
        )

    for hit in sorted(hits, key=rank):
        if str(hit["term"]).lower() not in wanted:
            continue
        marker = (str(hit["relative_path"]), str(hit["line_or_string_index"]))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(hit)
        if len(result) >= limit:
            break
    return result


def evidence_lines(hits: list[dict[str, Any]], terms: Iterable[str], limit: int = 4) -> list[str]:
    matches = first_hits(hits, terms, limit)
    if not matches:
        return ["- No selected-source hit found."]
    return [
        f"- `{hit['relative_path']}:{hit['line_or_string_index']}` `{hit['term']}` - {hit['excerpt']}"
        for hit in matches
    ]


def package_summary_markdown(packages: list[dict[str, Any]]) -> list[str]:
    by_package = defaultdict(list)
    for row in packages:
        by_package[str(row["package"])].append(row)
    rows: list[list[str]] = []
    for package, entries in sorted(by_package.items()):
        important = sorted({Path(str(row["content_path"])).name for row in entries if row["important_restored_resource"]})
        rows.append([package, str(len(entries)), ", ".join(important[:8]) or "none"])
    return markdown_table(rows, ["Package", "Files", "Key MP resources seen"])


def manual_test_matrix() -> str:
    lane_rows = [
        ["A", "baseline_no_mp_restore", "None", "Clean backup / no MP restore", "Baseline UI and error path"],
        ["B", "release64_csc_only", "import_test_release64_csc", "content/release64/multiplayer/", "PC-comparable path family"],
        ["C", "release_csc_only", "import_test_release_csc", "content/release/multiplayer/", "Legacy release path visibility"],
        ["D", "both_release_and_release64_csc", "import_test_both_csc", "both CSC path families", "Path ambiguity isolation"],
        ["E", "xsc_review_only", "import_test_xsc_review", "Do not import without explicit approval", "Wrapper review lane"],
    ]
    tracking = [
        "content.rpf backup used",
        "imported package",
        "Magic RDR reopen/export verification result",
        "byte compare result",
        "launch result",
        "menu change",
        "new option visible",
        "old option unlocked",
        "different error message",
        "loading screen change",
        "crash/hang/return-to-menu behavior",
        "log/crash/report evidence",
        "screenshot/video note",
        "next action",
    ]
    lines = [
        "# Code RED MP Manual Test Matrix",
        "",
        "Run one copied `content.rpf` lane at a time. Do not compare runtime results until Magic RDR reopen/export verification passes for that lane.",
        "",
        *markdown_table(lane_rows, ["Lane", "Name", "Package", "Import target", "Purpose"]),
        "",
        "## Per-lane Worksheet",
        "",
    ]
    for lane, name, package, target, purpose in lane_rows:
        lines.extend([f"### Lane {lane}: {name}", "", f"- Package: `{package}`", f"- Target: `{target}`", f"- Purpose: {purpose}", ""])
        lines.extend(markdown_table([[field, ""] for field in tracking], ["Field", "Result"]))
        lines.append("")
    return "\n".join(lines) + "\n"


def import_export_worksheet() -> str:
    samples = [
        "freemode/freemode.csc",
        "mp_idle.csc",
        "multiplayer_system_thread.csc",
        "multiplayer_update_thread.csc",
        "deathmatch/deathmatch.csc",
    ]
    return "\n".join(
        [
            "# Code RED Magic RDR Import Export Verification Worksheet",
            "",
            "Use this before every runtime launch in the Pass 3 matrix.",
            "",
            "1. Copy the lane backup of `content.rpf`; do not edit the only clean archive.",
            "2. Import one package only and keep its internal `content/release.../multiplayer/` path unchanged.",
            "3. Save and reopen the copied RPF in Magic RDR.",
            "4. Verify the expected imported paths still exist after reopen.",
            "5. Export representative imported files back out.",
            "6. Compare exported SHA1 and CRC32 to the staged package file and `reports/raw_byte_preservation_report.csv`.",
            "7. Launch only when reopen and exported-byte checks pass.",
            "",
            *markdown_table([[sample, "", "", "", ""] for sample in samples], ["Sample file", "Imported path verified", "Export SHA1", "Export CRC32", "Matches staged donor"]),
            "",
            "Record any Magic RDR payload rewrite, missing path, import warning, export failure, or size change as a lane failure before game launch.",
            "",
        ]
    ) + "\n"


def flow_report(hits: list[dict[str, Any]], packages: list[dict[str, Any]], update_status: list[dict[str, str]]) -> str:
    update_decoded = sum(1 for row in update_status if row.get("decode_status") == "decoded")
    update_direct_hits = sum(1 for row in update_status if int(row.get("decoded_string_count") or 0) >= 0)
    package_names = sorted({str(row["package"]) for row in packages})
    boot_hits = [hit for hit in hits if str(hit["relative_path"]).lower().endswith("ui/boot.sc.xml")]
    pause_scene_hits = [hit for hit in hits if "pausemenuscene" in str(hit["relative_path"]).lower()]
    lines = [
        "# Code RED MP Bootstrap Flow Map",
        "",
        "This is a source-evidence flow map, not a runtime success claim.",
        "",
        "```mermaid",
        'flowchart TD',
        '  A["Pause / boot menu evidence"] --> B["NetworkingLayerOffline"]',
        '  B --> C["NetConf_PlayLAN / System Link confirmation"]',
        '  C --> D["net/PlayMpConf.sc"]',
        '  D --> E["NetMachine.Authenticate(arg1)"]',
        '  E --> F["auth.success"]',
        '  F --> G["NetMachine.TriggerMultiplayerLoad(arg2)"]',
        '  G --> H["NetConf_StartGame / GameWish lane"]',
        '  H --> I["Update threads and restored MP scripts"]',
        "```",
        "",
        "## 1. Pause or boot entry",
        "",
        "Current extracted `ui/boot.sc.xml` and decoded pause-menu sources are scanned independently when present.",
        "",
        "Boot/menu evidence:",
        *evidence_lines(boot_hits, ["offline", "NetConf", "Multiplayer", "auth.success"], 4),
        "",
        "Pause-menu scene evidence:",
        *evidence_lines(pause_scene_hits, ["NetworkingLayerOffline", "offline", "NetConf", "Multiplayer"], 4),
        "",
        "## 2. LAN or System Link route",
        "",
        *evidence_lines(hits, ["NetConf_PlayLAN", "System Link", "LAN"], 6),
        "",
        "## 3. Confirmation and auth gate",
        "",
        *evidence_lines(hits, ["Authenticate", "auth.success", "signin", "profile"], 6),
        "",
        "## 4. Multiplayer load transition",
        "",
        *evidence_lines(hits, ["TriggerMultiplayerLoad", "NetConf_StartGame", "SetGameWish", "StartGameWish", "MULTI_FREE_ROAM"], 8),
        "",
        "## 5. Update-thread and restored content correlation",
        "",
        f"- Pass 1 update-thread decode status rows: `{len(update_status)}`; decoded rows: `{update_decoded}`.",
        f"- Update-thread string rows considered for direct donor references: `{update_direct_hits}`. Pass 1 reported zero direct donor filename-token hits in printable update-thread strings.",
        f"- Pass 2 package lanes indexed here: `{', '.join(package_names) if package_names else 'none'}`.",
        "- Restored package files provide MP script dependencies for import testing; source evidence alone does not prove the PC runtime loads CSC or XSC wrappers.",
        "",
    ]
    return "\n".join(lines) + "\n"


def crosscheck_report(hits: list[dict[str, Any]], sources: list[dict[str, Any]]) -> str:
    categories = rows_by_key(hits, "category")
    by_path = defaultdict(list)
    for hit in hits:
        by_path[str(hit["relative_path"])].append(hit)
    ranked = sorted(by_path.items(), key=lambda item: (-len(item[1]), item[0].lower()))[:18]
    lines = [
        "# Code RED MP UI Networking Crosscheck",
        "",
        "The crosscheck scans decoded UI resources, current PC update-thread resources, and existing update-thread decode reports for MP route terms.",
        "",
        "## Hit categories",
        "",
        *markdown_table([[key, str(value)] for key, value in sorted(categories.items())], ["Category", "Hits"]),
        "",
        "## Highest-signal files",
        "",
    ]
    rows: list[list[str]] = []
    source_reason = {str(row["relative_path"]): str(row["scan_reason"]) for row in sources}
    for path, path_hits in ranked:
        rows.append([path, str(len(path_hits)), ", ".join(sorted({str(hit["term"]) for hit in path_hits})[:10]), source_reason.get(path, "")])
    lines.extend(markdown_table(rows, ["Relative source", "Hits", "Terms", "Reason"]))
    lines.extend(
        [
            "",
            "## Priority route evidence",
            "",
            "### NetConf_PlayLAN",
            "",
            *evidence_lines(hits, ["NetConf_PlayLAN"], 8),
            "",
            "### Authentication and auth.success",
            "",
            *evidence_lines(hits, ["Authenticate", "auth.success"], 10),
            "",
            "### Multiplayer load / game wish",
            "",
            *evidence_lines(hits, ["TriggerMultiplayerLoad", "SetGameWish", "StartGameWish", "MULTI_FREE_ROAM"], 10),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def observable_indicators_report() -> str:
    rows = [
        ["Menu reachability", "Pause menu opens Networking/LAN/System Link route", "baseline vs CSC package lane screenshot"],
        ["UI visibility", "LAN tab or MP confirmation appears, disappears, or changes label", "menu screenshot and lane"],
        ["Auth/profile gate", "sign-in/profile alert text changes or auth failure moves later", "exact alert text and log"],
        ["Load transition", "fade/loading screen starts after NetConf_PlayLAN confirmation", "video timestamp and hang/return result"],
        ["Resource effect", "release vs release64 vs both changes result", "matrix lane comparison"],
        ["Crash boundary", "start screen, pause menu, confirmation, load, or return-to-menu crash point", "crash log and last visible screen"],
        ["Export integrity", "Magic RDR export bytes still match imported package bytes", "SHA1/CRC worksheet"],
    ]
    return "\n".join(
        [
            "# Code RED MP Observable Indicators",
            "",
            "Pass 3 needs signs of life, not a broad patch. Record the first observable change per lane.",
            "",
            *markdown_table(rows, ["Indicator", "What to observe", "Evidence to keep"]),
            "",
        ]
    ) + "\n"


def blockers_report(hits: list[dict[str, Any]], packages: list[dict[str, Any]]) -> str:
    has_playlan = bool(first_hits(hits, ["NetConf_PlayLAN"], 1))
    has_auth = bool(first_hits(hits, ["Authenticate", "auth.success"], 1))
    has_load = bool(first_hits(hits, ["TriggerMultiplayerLoad"], 1))
    has_packages = bool(packages)
    rows = [
        [
            "LAN route is conditionally visible",
            "decoded `networking.sc.xml` excludes tabs first, then includes LAN from net-mode events",
            "UI can remain unreachable even when route definitions exist",
            "small local UI reachability review",
        ],
        [
            "Auth/profile gate before load",
            "PlayMpConf path contains `Authenticate`, auth failure transitions, and `auth.success` before `TriggerMultiplayerLoad`",
            "report-only in this pass",
            "local/LAN candidate only after matrix evidence",
        ],
        [
            "Wrapper/path compatibility unresolved",
            "PC examples are WSC RSC85; PSN CSC is swapped RSC86; XENON XSC is swapped RSC85",
            "restored files may import yet be ignored by loader",
            "release/release64 matrix and export-byte proof",
        ],
        [
            "Update-thread linkage not directly named",
            "Pass 1 decoded update-thread strings found zero direct donor filename-token hits",
            "dependency may be hashed/runtime-table driven",
            "do not infer missing or loaded scripts from strings alone",
        ],
    ]
    lines = [
        "# Code RED MP Blockers",
        "",
        f"- Route evidence present: NetConf_PlayLAN=`{has_playlan}`, auth route=`{has_auth}`, TriggerMultiplayerLoad=`{has_load}`.",
        f"- Pass 2 import package files indexed: `{len(packages)}`.",
        "",
        *markdown_table(rows, ["Blocker", "Evidence", "Consequence", "Allowed next move"]),
        "",
        "Public matchmaking and external platform authentication remain report-only. Pass 3 does not spoof them or bypass them.",
        "",
    ]
    return "\n".join(lines) + "\n"


def patch_candidates_report() -> str:
    rows = [
        [
            "safe_ui_unhide_candidate",
            "NetTab_LAN include/exclude and offline networking entry",
            "Only if matrix proves LAN route exists in files but never becomes visible",
            "UI visibility review only before any edit",
        ],
        [
            "local_lan_route_candidate",
            "NetConf_PlayLAN -> net/PlayMpConf.sc -> LAN arg2 route",
            "Local/System Link reachability evidence exists",
            "Keep LAN-only scope and preserve arg2",
        ],
        [
            "resource_path_candidate",
            "release CSC vs release64 CSC vs both package lanes",
            "Need observable runtime difference first",
            "Use matrix before changing paths",
        ],
        [
            "auth_gate_candidate_report_only",
            "NetMachine.Authenticate and auth.success/fail transitions",
            "Auth blocks occur before TriggerMultiplayerLoad",
            "Report only in this pass",
        ],
        [
            "conversion_candidate",
            "XENON swapped RSC85 XSC vs PSN swapped RSC86 CSC",
            "Wrapper compatibility remains unproven",
            "No conversion until import/loader evidence",
        ],
        [
            "do_not_patch_yet",
            "public/private online, matchmaking, profile, service routes",
            "External-auth/public-server behavior",
            "Do not spoof public services",
        ],
    ]
    return "\n".join(
        [
            "# Code RED MP Next Patch Candidates",
            "",
            "Candidate classes are ordered around the smallest observable blocker.",
            "",
            *markdown_table(rows, ["Class", "Target", "Why it matters", "Pass 3 action"]),
            "",
        ]
    ) + "\n"


def readiness_report(
    sources: list[dict[str, Any]],
    hits: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    exported: list[Path],
    update_status: list[dict[str, str]],
) -> str:
    source_counts = rows_by_key(sources, "source_kind")
    hit_counts = rows_by_key(hits, "category")
    has_export_back = [path for path in exported if path.exists()]
    lines = [
        "# Code RED Multiplayer Content Restore Pass 3 Readiness Report",
        "",
        "## Scope and safety",
        "",
        "- Report-only source inspection and manual-test planning.",
        "- No `content.rpf` writes.",
        "- No bytecode patching or script wrapper conversion.",
        "- No public-server spoofing or external-auth bypass.",
        "",
        "## Source inventory",
        "",
        *markdown_table([[key, str(value)] for key, value in sorted(source_counts.items())], ["Source kind", "Files scanned"]),
        "",
        f"- Update-thread decode status rows available from Pass 1: `{len(update_status)}`.",
        f"- Exported-back roots with files present: `{len(has_export_back)}`.",
        "",
        "## Pass 2 import packages",
        "",
        *package_summary_markdown(packages),
        "",
        "## MP route evidence",
        "",
        *markdown_table([[key, str(value)] for key, value in sorted(hit_counts.items())], ["Evidence category", "Hits"]),
        "",
        "- Decoded UI sources contain LAN/System Link route definitions, NetConf confirmation flow, auth transitions, and the multiplayer load handoff.",
        "- Restored MP scripts are staged for isolated import tests, but their presence alone does not prove the PC loader accepts CSC or XSC donor wrappers.",
        "- The manual matrix should answer whether restored content changes visibility, error text, or loading behavior before any patch is selected.",
        "",
        "## Highest-priority evidence",
        "",
        "### Local LAN route",
        "",
        *evidence_lines(hits, ["NetConf_PlayLAN", "System Link", "LAN"], 6),
        "",
        "### Auth gate",
        "",
        *evidence_lines(hits, ["Authenticate", "auth.success", "signin", "profile"], 6),
        "",
        "### Runtime load handoff",
        "",
        *evidence_lines(hits, ["TriggerMultiplayerLoad", "NetConf_StartGame", "SetGameWish", "StartGameWish", "MULTI_FREE_ROAM"], 8),
        "",
        "## Readiness conclusion",
        "",
        "The content-restore tree is ready for controlled import-matrix testing. Current evidence points at menu/net-mode/auth/load routing as the first observable blocker boundary, while format/path acceptance remains the content-compatibility question to isolate with the release, release64, and both CSC lanes.",
        "",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    reports = Path(args.reports)
    sources = discover_sources(args)
    source_rows: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    for source in sources:
        source_row, source_hits = text_scan_rows(source)
        source_rows.append(source_row)
        hits.extend(source_hits)
    packages = package_rows(Path(args.pass2_packages))
    update_status = read_csv(Path(args.pass1_logs) / "update_script_decode_status.csv")
    exports = exported_roots(args)
    write_csv(reports / "mp_readiness_sources.csv", source_rows)
    write_csv(reports / "mp_readiness_hits.csv", hits)
    write_csv(reports / "mp_readiness_pass2_package_inventory.csv", packages)
    write_text(reports / "mp_readiness_report.md", readiness_report(source_rows, hits, packages, exports, update_status))
    write_text(reports / "mp_bootstrap_flow_map.md", flow_report(hits, packages, update_status))
    write_text(reports / "mp_ui_networking_crosscheck.md", crosscheck_report(hits, source_rows))
    write_text(reports / "mp_observable_indicators.md", observable_indicators_report())
    write_text(reports / "mp_blockers.md", blockers_report(hits, packages))
    write_text(reports / "mp_next_patch_candidates.md", patch_candidates_report())
    write_text(reports / "mp_manual_test_matrix.md", manual_test_matrix())
    write_text(reports / "mp_magic_rdr_import_export_worksheet.md", import_export_worksheet())
    summary = {
        "tool": "codered_mp_readiness_probe",
        "source_files_scanned": len(source_rows),
        "readiness_hits": len(hits),
        "hit_categories": dict(rows_by_key(hits, "category")),
        "pass2_package_files": len(packages),
        "pass2_packages": dict(rows_by_key(packages, "package")),
        "exported_back_roots_present": [str(path) for path in exports if path.exists()],
        "reports": str(reports),
        "no_content_rpf_write": True,
        "no_script_bytecode_patch": True,
        "no_conversion": True,
        "no_public_server_spoofing": True,
    }
    write_text(reports / "mp_readiness_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe restored MP content readiness without writing RPFs.")
    parser.add_argument("--pc-content", default=str(ROOT / "game" / "content_extracted"))
    parser.add_argument("--decoded-ui", default=str(ROOT / "logs" / "content_mp_scxml_zstd_probe" / "decoded"))
    parser.add_argument("--pass1-logs", default=str(ROOT / "logs" / "mp_content_restore_pass1"))
    parser.add_argument("--route-blocks", default="", help="Optional focused decoded-SCXML route-block report directory.")
    parser.add_argument("--pass2-packages", default=str(ROOT / "build" / "mp_content_restore_pass2"))
    parser.add_argument("--reports", default=str(ROOT / "reports"))
    parser.add_argument("--extra-scan-root", action="append", default=[], help="Optional extra text/script root to scan.")
    parser.add_argument("--exported-back", action="append", default=[], help="Optional Magic RDR exported-back verification root.")
    args = parser.parse_args(argv)
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
