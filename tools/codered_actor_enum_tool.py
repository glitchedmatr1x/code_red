#!/usr/bin/env python3
"""Code RED actor enum no-recompile tool.

Keeps the ScriptHookRDR AI Menu data-driven:
- rebuild data/codered/actor_enum_map.csv from local C++ enum or INI-style enum data
- seed a minimal verified map from Code RED research notes
- validate npc_roster.txt before spawn testing
- export a spawn-safe roster containing only resolved entries
- write JSON proof reports for troubleshooting

The ASI/menu does not need to be recompiled when actor labels, aliases,
or roster entries change.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

VERSION = "1.1.1-flexible-replace-flag-pass"
DEFAULT_MAP = Path("data/codered/actor_enum_map.csv")
DEFAULT_ROSTER = Path("data/codered/npc_roster.txt")
DEFAULT_SAFE_ROSTER = Path("data/codered/npc_roster_safe_verified.txt")
DEFAULT_REPORT = Path("logs/CodeRED_Actor_Enum_Validation_Report.json")

HEADER = ["label", "actor_enum", "category", "source", "aliases", "notes"]
ENUM_START_RE = re.compile(r"^\s*enum\s+e_ActorModel\b", re.IGNORECASE)
CPP_ENTRY_RE = re.compile(r"^\s*(ACTOR_[A-Za-z0-9_]+)\s*(?:=\s*(-?\d+|0x[0-9A-Fa-f]+))?\s*,?")
INI_ENTRY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]+)\s*=\s*(-?\d+|0x[0-9A-Fa-f]+)\s*$")
SECTION_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")

# Research seeds are intentionally small. Use the local enum source for the full map.
KNOWN_EXPECTED: dict[str, int] = {
    "ACTOR_CAUCASIAN_ARMY_Easy01": 369,
    "AE_CAUCASIAN_ARMY_EASY01": 369,
    "AE_Caucasian_Army_Easy01": 369,
    "ACTOR_RIDEABLE_ANIMAL_Horse01": 976,
    "ACTOR_RIDEABLE_ANIMAL_MEX_Mule01": 1000,
    "ACTOR_RIDEABLE_ANIMAL_Buffalo": 1004,
    "ACTOR_VEHICLE_Stagecoach": 1177,
    "ACTOR_VEHICLE_Cart01": 1183,
    "ACTOR_VEHICLE_Canoe01": 1189,
    "ACTOR_VEHICLE_Raft01": 1192,
    "ACTOR_VEHICLE_Truck01": 1193,
    "ACTOR_VEHICLE_Car01": 1194,
    "ACTOR_VEHICLE_Wagon02": 1199,
    "ACTOR_VEHICLE_Coach01": 1202,
}

SEED_ROWS: list[dict[str, str]] = [
    {"label": "ACTOR_CAUCASIAN_ARMY_Easy01", "actor_enum": "369", "category": "army", "source": "CodeRED research sanity seed", "aliases": "AE_CAUCASIAN_ARMY_EASY01|AE_Caucasian_Army_Easy01|CAUCASIAN_ARMY_EASY01", "notes": "known crash-fix seed; rebuild from enum source for full map"},
    {"label": "AE_CAUCASIAN_ARMY_EASY01", "actor_enum": "369", "category": "army", "source": "CodeRED research sanity seed", "aliases": "ACTOR_CAUCASIAN_ARMY_Easy01|AE_Caucasian_Army_Easy01", "notes": "alias for Caucasian Army Easy01"},
    {"label": "ACTOR_RIDEABLE_ANIMAL_Horse01", "actor_enum": "976", "category": "rideable", "source": "CodeRED research sanity seed", "aliases": "HORSE01|RIDEABLE_ANIMAL_HORSE01", "notes": "safe first rideable test candidate"},
    {"label": "ACTOR_RIDEABLE_ANIMAL_MEX_Mule01", "actor_enum": "1000", "category": "rideable", "source": "CodeRED research sanity seed", "aliases": "MEX_Mule01|MULE01|RIDEABLE_ANIMAL_MEX_MULE01", "notes": "safe first mule test candidate"},
    {"label": "ACTOR_RIDEABLE_ANIMAL_Buffalo", "actor_enum": "1004", "category": "rideable", "source": "CodeRED research sanity seed", "aliases": "BUFFALO|RIDEABLE_ANIMAL_BUFFALO", "notes": "rideable/control research candidate"},
    {"label": "ACTOR_VEHICLE_Stagecoach", "actor_enum": "1177", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_STAGECOACH|STAGECOACH", "notes": "vehicle/control research candidate"},
    {"label": "ACTOR_VEHICLE_Cart01", "actor_enum": "1183", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_CART01|CART01", "notes": "vehicle/control research candidate"},
    {"label": "ACTOR_VEHICLE_Canoe01", "actor_enum": "1189", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_CANOE01|CANOE01", "notes": "vehicle/control research candidate"},
    {"label": "ACTOR_VEHICLE_Raft01", "actor_enum": "1192", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_RAFT01|RAFT01", "notes": "vehicle/control research candidate"},
    {"label": "ACTOR_VEHICLE_Truck01", "actor_enum": "1193", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_TRUCK01|TRUCK01", "notes": "important car/truck test candidate"},
    {"label": "ACTOR_VEHICLE_Car01", "actor_enum": "1194", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_CAR01|CAR01", "notes": "important car/truck test candidate"},
    {"label": "ACTOR_VEHICLE_Wagon02", "actor_enum": "1199", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_WAGON02|WAGON02", "notes": "vehicle/control research candidate"},
    {"label": "ACTOR_VEHICLE_Coach01", "actor_enum": "1202", "category": "vehicle", "source": "CodeRED research sanity seed", "aliases": "VEHICLE_COACH01|COACH01", "notes": "vehicle/control research candidate"},
]

SAFE_ROSTER_SEED = [
    "ACTOR_CAUCASIAN_ARMY_Easy01",
    "AE_CAUCASIAN_ARMY_EASY01",
    "ACTOR_RIDEABLE_ANIMAL_Horse01",
    "ACTOR_RIDEABLE_ANIMAL_MEX_Mule01",
    "ACTOR_RIDEABLE_ANIMAL_Buffalo",
    "ACTOR_VEHICLE_Car01",
    "ACTOR_VEHICLE_Truck01",
    "ACTOR_VEHICLE_Stagecoach",
    "ACTOR_VEHICLE_Cart01",
    "ACTOR_VEHICLE_Wagon02",
    "ACTOR_VEHICLE_Coach01",
    "ACTOR_VEHICLE_Canoe01",
    "ACTOR_VEHICLE_Raft01",
]


@dataclass
class RosterEntry:
    line: str
    label: str
    resolved: bool
    actor_enum: int | None = None
    actor_enum_hex: str | None = None
    source: str | None = None
    warning: str | None = None


@dataclass
class ValidationReport:
    version: str
    generated_utc: str
    enum_map: str
    roster: str
    total_roster_entries: int
    resolved_entries: int
    unresolved_entries: int
    sanity_errors: list[str]
    entries: list[RosterEntry]


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def parse_int(text: str) -> int:
    raw = text.strip()
    return int(raw, 16) if raw.lower().startswith("0x") else int(raw)


def strip_comment(raw: str) -> str:
    in_quotes = False
    out: list[str] = []
    for ch in raw:
        if ch == '"':
            in_quotes = not in_quotes
        if not in_quotes and ch in "#;":
            break
        out.append(ch)
    return "".join(out).strip()


def normalize_actor_label(label: str) -> str:
    clean = label.strip()
    if not clean:
        return ""
    if clean.lower().startswith("actor_"):
        tail = clean[6:]
        return "ACTOR_" + tail
    return clean


def category_for(canonical: str) -> str:
    name = canonical.upper()
    if "VEHICLE" in name:
        return "vehicle"
    if "RIDEABLE_ANIMAL" in name:
        return "rideable"
    if "ARMY" in name:
        return "army"
    if "GANG" in name or "CRIMINAL" in name or "OUTLAW" in name:
        return "gang"
    if "LAW" in name or "SHERIFF" in name or "MARSHAL" in name or "DEPUTY" in name or "POLICE" in name:
        return "law"
    if "ZOMBIE" in name or "UN_" in name:
        return "zombie"
    if "COMPANION" in name:
        return "companion"
    if "PLAYER" in name:
        return "player_like"
    return "actor"


def aliases_for(canonical: str) -> list[str]:
    aliases: list[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in aliases:
            aliases.append(value)

    normalized = normalize_actor_label(canonical)
    add(normalized)
    add(normalized.upper())
    add(normalized.lower())
    if normalized.upper().startswith("ACTOR_"):
        short = normalized[6:]
        add(short)
        add(short.upper())
        add(short.lower())
        add("AE_" + short)
        add(("AE_" + short).upper())
        add(("AE_" + short).lower())
    return aliases


def rows_from_entries(entries: Iterable[tuple[str, int]], source: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_label, value in entries:
        canonical = normalize_actor_label(raw_label)
        if not canonical:
            continue
        all_aliases = aliases_for(canonical)
        for label in all_aliases:
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "label": label,
                "actor_enum": str(value),
                "category": category_for(canonical),
                "source": source,
                "aliases": "|".join(a for a in all_aliases if a != label),
                "notes": f"canonical={canonical}; hex=0x{value:08X}",
            })
    return rows


def parse_cpp_enum_lines(lines: Iterable[str]) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    inside = False
    current_value: int | None = None
    for raw in lines:
        clean = strip_comment(raw)
        if not inside:
            if ENUM_START_RE.search(clean):
                inside = True
            continue
        if clean.startswith("};"):
            break
        match = CPP_ENTRY_RE.match(clean)
        if not match:
            continue
        canonical, explicit = match.groups()
        if explicit is not None:
            current_value = parse_int(explicit)
        else:
            current_value = 0 if current_value is None else current_value + 1
        entries.append((canonical, current_value))
    return entries


def parse_ini_enum_lines(lines: Iterable[str]) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    active_enum_section = False
    saw_section = False
    for raw in lines:
        clean = strip_comment(raw)
        if not clean:
            continue
        if SECTION_RE.match(clean):
            saw_section = True
            active_enum_section = clean.strip().lower() == "[enum]"
            continue
        if saw_section and not active_enum_section:
            continue
        match = INI_ENTRY_RE.match(clean)
        if not match:
            continue
        label, value = match.groups()
        if not label.lower().startswith("actor_"):
            continue
        entries.append((label, parse_int(value)))
    return entries


def parse_enum_source(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Enum source not found: {path}")
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    cpp_entries = parse_cpp_enum_lines(lines)
    if cpp_entries:
        return rows_from_entries(cpp_entries, "C++ enum:e_ActorModel")
    ini_entries = parse_ini_enum_lines(lines)
    if ini_entries:
        return rows_from_entries(ini_entries, "INI-style [Enum] actor list")
    raise ValueError(f"No actor enum rows parsed from: {path}")


def display_label(raw: str) -> str:
    text = strip_comment(raw)
    for marker in ("|", "=", ","):
        if marker in text:
            return text.split(marker, 1)[0].strip()
    return text.strip()


def parse_inline_enum(raw: str) -> int | None:
    text = strip_comment(raw)
    for marker in ("|", "=", ","):
        if marker in text:
            rhs = text.split(marker, 1)[1].strip()
            try:
                return parse_int(rhs)
            except ValueError:
                return None
    try:
        return parse_int(text)
    except ValueError:
        return None


def write_map(path: Path, rows: Iterable[dict[str, str]], replace: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        backup = path.with_suffix(path.suffix + f".bak_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(path, backup)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("# CodeRED actor enum map\n")
        f.write("# Generated/managed by tools/codered_actor_enum_tool.py\n")
        f.write("# Edit this CSV instead of recompiling the ASI.\n")
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in HEADER})
    return path


def read_map(path: Path) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    if not path.exists():
        return lookup
    lines = [line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return lookup
    for row in csv.DictReader(lines):
        label = (row.get("label") or "").strip()
        if not label:
            continue
        lookup[label.lower()] = row
        actor_enum = (row.get("actor_enum") or "").strip()
        if actor_enum:
            lookup[actor_enum.lower()] = row
        for alias in re.split(r"[|;]", row.get("aliases") or ""):
            alias = alias.strip()
            if alias:
                lookup[alias.lower()] = row
    return lookup


def validate_sanity(lookup: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for label, expected in KNOWN_EXPECTED.items():
        row = lookup.get(label.lower())
        if not row:
            continue
        raw = (row.get("actor_enum") or "").strip()
        if not raw:
            errors.append(f"{label} is present but actor_enum is blank; expected {expected}")
            continue
        try:
            actual = parse_int(raw)
        except ValueError:
            errors.append(f"{label} has non-numeric actor_enum={raw!r}; expected {expected}")
            continue
        if actual != expected:
            errors.append(f"{label} has actor_enum={actual}; expected {expected}")
    return errors


def iter_roster_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        label = display_label(raw)
        if not label:
            continue
        out.append(raw.strip())
    return out


def validate_roster(enum_map: Path, roster: Path) -> ValidationReport:
    lookup = read_map(enum_map)
    entries: list[RosterEntry] = []
    for raw in iter_roster_lines(roster):
        label = display_label(raw)
        inline = parse_inline_enum(raw)
        row = lookup.get(label.lower())
        if inline is not None:
            entries.append(RosterEntry(raw, label, True, inline, f"0x{inline:08X}", "inline roster value"))
        elif row and (row.get("actor_enum") or "").strip():
            value = parse_int(row["actor_enum"])
            entries.append(RosterEntry(raw, label, True, value, f"0x{value:08X}", row.get("source") or "actor_enum_map.csv"))
        else:
            entries.append(RosterEntry(raw, label, False, warning="unresolved_actor_enum"))
    resolved = sum(1 for item in entries if item.resolved)
    return ValidationReport(VERSION, utc_now(), str(enum_map), str(roster), len(entries), resolved, len(entries) - resolved, validate_sanity(lookup), entries)


def write_report(report: ValidationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def write_safe_roster(report: ValidationReport, path: Path, replace: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        backup = path.with_suffix(path.suffix + f".bak_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(path, backup)
    lines = ["# CodeRED spawn-safe verified roster", "# Generated by tools/codered_actor_enum_tool.py", "# Only resolved entries are included.", ""]
    for entry in report.entries:
        if entry.resolved and entry.actor_enum is not None:
            lines.append(f"{entry.label}|{entry.actor_enum}  # {entry.actor_enum_hex} from {entry.source}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_seed_roster(path: Path, replace: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        backup = path.with_suffix(path.suffix + f".bak_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(path, backup)
    path.write_text(
        "# CodeRED NPC roster seed\n"
        "# Safe verified no-recompile seed. Add more entries after regenerating actor_enum_map.csv from enum source.\n"
        "# Format supports label, label|number, label=number, or CSV-style actor map lookup.\n\n"
        + "\n".join(SAFE_ROSTER_SEED) + "\n",
        encoding="utf-8",
    )
    return path


def wants_replace(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "replace", False) or getattr(args, "sub_replace", False))


def add_sub_replace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--replace", dest="sub_replace", action="store_true", default=False,
                        help="Replace target files without making .bak timestamp backups. Can be used before or after the subcommand.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate/validate Code RED actor enum data without recompiling the ASI.")
    p.add_argument("--enum-map", type=Path, default=DEFAULT_MAP)
    p.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    p.add_argument("--replace", action="store_true", help="Replace target files without making .bak timestamp backups. Can be used before or after the subcommand.")
    sub = p.add_subparsers(dest="cmd")

    seed = sub.add_parser("seed", help="Write a small verified seed actor_enum_map.csv.")
    seed.add_argument("--safe-roster", action="store_true", help="Also replace/write a safe seed npc_roster.txt.")
    add_sub_replace(seed)

    rebuild = sub.add_parser("rebuild", help="Rebuild actor_enum_map.csv from a local enum source.")
    rebuild.add_argument("--enums-h", type=Path, help="Path to C++ Enums.h or INI-style [Enum] file.")
    rebuild.add_argument("--source", type=Path, help="Alias for --enums-h; accepts C++ enum or INI-style [Enum] file.")
    add_sub_replace(rebuild)

    validate = sub.add_parser("validate", help="Validate npc_roster.txt against actor_enum_map.csv and write JSON report.")
    add_sub_replace(validate)

    safe = sub.add_parser("safe-roster", help="Write npc_roster_safe_verified.txt from resolved roster entries.")
    safe.add_argument("--output", type=Path, default=DEFAULT_SAFE_ROSTER)
    add_sub_replace(safe)

    summary = sub.add_parser("summary", help="Print a compact validation summary.")
    add_sub_replace(summary)
    return p


def main() -> int:
    args = build_parser().parse_args()
    cmd = args.cmd or "summary"
    replace = wants_replace(args)

    if cmd == "seed":
        write_map(args.enum_map, SEED_ROWS, replace=replace)
        if args.safe_roster:
            write_seed_roster(args.roster, replace=replace)
        report = validate_roster(args.enum_map, args.roster)
        write_report(report, args.report)
        print(f"Seeded enum map: {args.enum_map}")
        if args.safe_roster:
            print(f"Seeded roster:   {args.roster}")
        print(f"Report:          {args.report}")
        return 0

    if cmd == "rebuild":
        source = args.source or args.enums_h
        if not source:
            raise SystemExit("rebuild requires --enums-h or --source")
        rows = parse_enum_source(source)
        write_map(args.enum_map, rows, replace=replace)
        report = validate_roster(args.enum_map, args.roster)
        write_report(report, args.report)
        print(f"Parsed rows:     {len(rows)}")
        print(f"Enum source:     {source}")
        print(f"Enum map:        {args.enum_map}")
        print(f"Report:          {args.report}")
        if report.sanity_errors:
            print("Sanity errors:")
            for item in report.sanity_errors:
                print(" - " + item)
            return 2
        return 0

    if cmd in {"validate", "summary", "safe-roster"}:
        report = validate_roster(args.enum_map, args.roster)
        write_report(report, args.report)
        if cmd == "safe-roster":
            out = write_safe_roster(report, args.output, replace=replace)
            print(f"Safe roster:     {out}")
        print(f"Roster entries:  {report.total_roster_entries}")
        print(f"Resolved:        {report.resolved_entries}")
        print(f"Unresolved:      {report.unresolved_entries}")
        print(f"Sanity errors:   {len(report.sanity_errors)}")
        print(f"Report:          {args.report}")
        if report.sanity_errors:
            for item in report.sanity_errors:
                print(" - " + item)
            return 2
        return 0 if report.unresolved_entries == 0 else 1

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
