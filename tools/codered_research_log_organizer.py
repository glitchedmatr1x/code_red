#!/usr/bin/env python3
"""Build safe Code RED log/research indexes without moving tool outputs.

The logs folder is both a notebook and a stable output target for many tools.
This organizer creates an indexed reading layer in docs/research_index and
logs/_indexes so humans and AI agents can find related notes without breaking
hard-coded report paths.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
RESEARCH = ROOT / "research"
DOCS = ROOT / "docs"
OUT = DOCS / "research_index"
TOPICS_OUT = OUT / "topics"
LOG_INDEX_OUT = LOGS / "_indexes"


TOPICS: dict[str, dict[str, object]] = {
    "mp_ui_networking": {
        "title": "MP UI, LAN, Auth Gates, and Content RPF",
        "keywords": [
            "mp",
            "multiplayer",
            "freemode",
            "lan",
            "network",
            "auth",
            "content_mp",
            "scxml",
            "zstd",
            "lobby",
            "plaympconf",
        ],
        "summary": "Decoded UI route, LAN/System Link gates, content.rpf inventory, and MP load-path research.",
    },
    "ai_menu_native_bridge": {
        "title": "AI Menu, Actor Enums, and Native Bridge",
        "keywords": [
            "ai_menu",
            "actor_enum",
            "native_bridge",
            "npc",
            "trainer",
            "script_hook",
            "scripthookrdr",
            "creat_actor",
            "create_actor",
        ],
        "summary": "ScriptHookRDR ASI menu, actor enum resolution, native wrapper prep, and in-game NPC control notes.",
    },
    "scripts_decompile_compile": {
        "title": "Scripts, Decompile/Recompile, SC-CL, and CSC/WSC/SCO",
        "keywords": [
            "script",
            "decompile",
            "recompile",
            "sccl",
            "sc-cl",
            "csc",
            "wsc",
            "sco",
            "xsc",
            "xsv",
            "compiler",
        ],
        "summary": "Script workshop, compiler proof lanes, decompile attempts, and compiled-script format research.",
    },
    "rpf_archive_tooling": {
        "title": "RPF Archive, Magic-RDR, Terrainboundres, Psocache, and Resource Tooling",
        "keywords": [
            "rpf",
            "archive",
            "magic_rdr",
            "magic-rdr",
            "rpf6",
            "terrainboundres",
            "psocache",
            "navres",
            "extract",
            "patch",
        ],
        "summary": "Archive inventory/extraction, Magic-RDR parity, copied-archive patch planning, and resource probes.",
    },
    "vehicles_world_gringos": {
        "title": "Vehicles, Gringos, Camps, WSI, Models, and World Placement",
        "keywords": [
            "vehicle",
            "car",
            "truck",
            "camp",
            "gringo",
            "wsi",
            "wft",
            "wedt",
            "placement",
            "locset",
            "nav",
        ],
        "summary": "Car/truck metadata, camp vehicle workbench, gringo descriptors, WSI placement, and model/resource notes.",
    },
    "faction_wars_ai_behavior": {
        "title": "Faction Wars, Law/Gang Behavior, Hostility, and AI Tasks",
        "keywords": [
            "faction",
            "law",
            "gang",
            "posse",
            "hostile",
            "enemy",
            "companion",
            "behavior",
            "behaviour",
        ],
        "summary": "Faction/hostility research, lawman/gang behavior, companion AI, and control targets.",
    },
    "launchers_cleanup_milestones": {
        "title": "Launchers, Cleanup, Handoffs, Milestones, and Readmes",
        "keywords": [
            "launcher",
            "cleanup",
            "one_app",
            "handoff",
            "milestone",
            "read_first",
            "readme",
            "install",
            "maintenance",
            "build_assistant",
        ],
        "summary": "Project orientation notes, handoffs, public-test readmes, cleanup reports, and milestone records.",
    },
    "validation_reports": {
        "title": "Validation, Guards, Reports, and Proof Logs",
        "keywords": [
            "validation",
            "guard",
            "proof",
            "report",
            "selftest",
            "smoke",
            "doctor",
            "probe",
            "audit",
        ],
        "summary": "Validation reports, anti-regression guards, probe outputs, and proof artifacts.",
    },
}


EXTENSIONS = {".md", ".txt", ".json", ".csv", ".xml", ".diff", ".log"}
ROOT_NOTE_PATTERNS = (
    "README*",
    "READ_FIRST*",
    "MAINTENANCE.md",
    "FEATURE_AUDIT.md",
    "SCRIPTING.md",
    "MASTER_REPORT.json",
)


@dataclass
class Entry:
    path: str
    area: str
    name: str
    suffix: str
    size: int
    modified: str
    topic: str
    importance: int
    heading: str
    tool_sensitive: bool


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("/", "\\")


def read_heading(path: Path) -> str:
    if path.suffix.lower() not in {".md", ".txt", ".log"}:
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for _ in range(60):
                line = f.readline()
                if not line:
                    break
                clean = line.strip().lstrip("#").strip()
                if clean:
                    return clean[:140]
    except OSError:
        return ""
    return ""


def iter_root_notes() -> list[Path]:
    found: list[Path] = []
    for pattern in ROOT_NOTE_PATTERNS:
        found.extend(path for path in ROOT.glob(pattern) if path.is_file())
    return sorted(set(found))


def iter_files() -> list[Path]:
    paths: list[Path] = []
    for base in (LOGS, RESEARCH, DOCS):
        if base.exists():
            paths.extend(
                path
                for path in base.rglob("*")
                if path.is_file()
                and path.suffix.lower() in EXTENSIONS
                and OUT not in path.parents
                and LOG_INDEX_OUT not in path.parents
            )
    paths.extend(iter_root_notes())
    return sorted(set(paths), key=lambda p: rel(p).lower())


def classify(path: Path) -> str:
    text = rel(path).lower().replace("\\", " ")
    best_topic = "validation_reports"
    best_score = -1
    for topic, data in TOPICS.items():
        score = 0
        for keyword in data["keywords"]:  # type: ignore[index]
            if str(keyword).lower() in text:
                score += 1
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic


def importance(path: Path) -> int:
    name = path.name.lower()
    score = 0
    if name.startswith("important"):
        score += 50
    if name.startswith("read_first") or name.startswith("readme") or name == "readme.md":
        score += 35
    if name.startswith("milestone"):
        score += 30
    if name.startswith("handoff"):
        score += 28
    if "report.md" in name or "pass" in name:
        score += 10
    if path.suffix.lower() == ".md":
        score += 5
    return score


def area(path: Path) -> str:
    try:
        first = path.relative_to(ROOT).parts[0]
    except ValueError:
        return "external"
    return first


def is_tool_sensitive(path: Path) -> bool:
    r = rel(path).lower()
    if r.startswith("logs\\") and not r.startswith("logs\\_indexes\\"):
        return True
    if r.startswith("research\\") and path.suffix.lower() in {".json", ".csv", ".xml"}:
        return True
    if r.startswith("docs\\") and path.suffix.lower() in {".json", ".wsc"}:
        return True
    return False


def make_entries() -> list[Entry]:
    out: list[Entry] = []
    for path in iter_files():
        try:
            stat = path.stat()
        except OSError:
            continue
        out.append(
            Entry(
                path=rel(path),
                area=area(path),
                name=path.name,
                suffix=path.suffix.lower(),
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
                topic=classify(path),
                importance=importance(path),
                heading=read_heading(path),
                tool_sensitive=is_tool_sensitive(path),
            )
        )
    return out


def md_link(path: str, root_prefix: str) -> str:
    label = path.replace("\\", "/")
    return f"[{label}]({root_prefix}/{label})"


def write_topic(topic: str, entries: list[Entry]) -> None:
    data = TOPICS[topic]
    title = str(data["title"])
    lines = [
        f"# {title}",
        "",
        str(data["summary"]),
        "",
        "Generated by `tools/codered_research_log_organizer.py`. Original files stay in place.",
        "",
        "## Important Reads",
        "",
    ]
    ranked = sorted(entries, key=lambda e: (-e.importance, e.path.lower()))
    for entry in ranked[:30]:
        marker = "tool-output" if entry.tool_sensitive else "note"
        heading = f" - {entry.heading}" if entry.heading else ""
        lines.append(f"- {md_link(entry.path, '../../..')} `{marker}`{heading}")
    lines.extend(["", "## All Files", "", "| File | Kind | Size | Modified |", "|---|---:|---:|---|"])
    for entry in sorted(entries, key=lambda e: e.path.lower()):
        lines.append(f"| {md_link(entry.path, '../../..')} | `{entry.suffix or 'dir'}` | {entry.size} | {entry.modified} |")
    (TOPICS_OUT / f"{topic}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_master(entries: list[Entry]) -> None:
    by_topic = {topic: [e for e in entries if e.topic == topic] for topic in TOPICS}
    lines = [
        "# Code RED Research And Log Index",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "This is the organized reading layer for Code RED logs, research notes, readmes, handoffs, and milestones.",
        "",
        "## Safety Rule",
        "",
        "Do not move root `logs\\*.json`, `logs\\*.md`, or tool output folders unless the owning tool is updated. Many tools write fixed report paths there. Use this index to find related material without breaking those paths.",
        "",
        "## Topic Folders",
        "",
        "| Topic | Files | Start Here |",
        "|---|---:|---|",
    ]
    for topic, data in TOPICS.items():
        title = str(data["title"])
        lines.append(f"| {title} | {len(by_topic[topic])} | [topics/{topic}.md](topics/{topic}.md) |")
    lines.extend(
        [
            "",
            "## Highest Priority Notes",
            "",
        ]
    )
    for entry in sorted(entries, key=lambda e: (-e.importance, e.path.lower()))[:60]:
        heading = f" - {entry.heading}" if entry.heading else ""
        lines.append(f"- {md_link(entry.path, '../..')} (`{entry.topic}`){heading}")
    lines.extend(
        [
            "",
            "## Machine Index",
            "",
            "- [MACHINE_INDEX.json](MACHINE_INDEX.json)",
            "- [logs/_indexes/CODERED_LOG_RESEARCH_INDEX_2026-05-07.json](../../logs/_indexes/CODERED_LOG_RESEARCH_INDEX_2026-05-07.json)",
        ]
    )
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_log_index(entries: list[Entry]) -> None:
    log_entries = [e for e in entries if e.area == "logs"]
    lines = [
        "# Code RED Log Index",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "This index intentionally leaves original log files and folders untouched because many tools use fixed output paths.",
        "",
        "| Topic | Count |",
        "|---|---:|",
    ]
    for topic in TOPICS:
        lines.append(f"| {TOPICS[topic]['title']} | {sum(1 for e in log_entries if e.topic == topic)} |")
    lines.extend(["", "## Log Files", "", "| File | Topic | Size | Modified |", "|---|---|---:|---|"])
    for entry in sorted(log_entries, key=lambda e: (e.topic, e.path.lower())):
        lines.append(f"| {md_link(entry.path, '../..')} | `{entry.topic}` | {entry.size} | {entry.modified} |")
    (LOG_INDEX_OUT / "CODERED_LOG_RESEARCH_INDEX_2026-05-07.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TOPICS_OUT.mkdir(parents=True, exist_ok=True)
    LOG_INDEX_OUT.mkdir(parents=True, exist_ok=True)
    entries = make_entries()
    payload = {
        "generated_utc": utc_now(),
        "root": str(ROOT),
        "counts": {
            "entries": len(entries),
            "logs": sum(1 for e in entries if e.area == "logs"),
            "research": sum(1 for e in entries if e.area == "research"),
            "docs": sum(1 for e in entries if e.area == "docs"),
            "root_notes": sum(1 for e in entries if e.area not in {"logs", "research", "docs"}),
        },
        "topics": {topic: {"title": data["title"], "count": sum(1 for e in entries if e.topic == topic)} for topic, data in TOPICS.items()},
        "entries": [asdict(entry) for entry in entries],
    }
    (OUT / "MACHINE_INDEX.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (LOG_INDEX_OUT / "CODERED_LOG_RESEARCH_INDEX_2026-05-07.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_master(entries)
    write_log_index(entries)
    for topic in TOPICS:
        write_topic(topic, [e for e in entries if e.topic == topic])
    print(json.dumps(payload["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
