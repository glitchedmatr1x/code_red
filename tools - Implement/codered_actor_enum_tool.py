#!/usr/bin/env python3
"""Code RED actor enum no-recompile tool.

Purpose:
- rebuild data/codered/actor_enum_map.csv from local C++ enum or INI-style enum data
- validate npc_roster.txt before spawn testing
- export a spawn-safe roster containing only resolved entries
- keep actor/roster changes data-driven so the ASI/menu does not need recompiling
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

VERSION = "1.2.0-polish-pass"
DEFAULT_MAP = Path("data/codered/actor_enum_map.csv")
DEFAULT_ROSTER = Path("data/codered/npc_roster.txt")
DEFAULT_SAFE_ROSTER = Path("data/codered/npc_roster_safe_verified.txt")
DEFAULT_REPORT = Path("logs/CodeRED_Actor_Enum_Validation_Report.json")
HEADER = ["label", "actor_enum", "category", "source", "aliases", "notes"]

CPP_ENUM_START_RE = re.compile(r"^\s*enum\s+e_ActorModel\b", re.IGNORECASE)
CPP_ENTRY_RE = re.compile(r"^\s*(ACTOR_[A-Za-z0-9_]+)\s*(?:=\s*(-?\d+|0x[0-9A-Fa-f]+))?\s*,?")
INI_ENTRY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]+)\s*=\s*(-?\d+|0x[0-9A-Fa-f]+)\s*$")
SECTION_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")

KNOWN_EXPECTED: dict[str, int] = {
    "ACTOR_CAUCASIAN_ARMY_Easy01": 369,
    "AE_CAUCASIAN_ARMY_EASY01": 369,
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

SEED_LABELS = [
    ("ACTOR_CAUCASIAN_ARMY_Easy01", 369),
    ("ACTOR_RIDEABLE_ANIMAL_Horse01", 976),
    ("ACTOR_RIDEABLE_ANIMAL_MEX_Mule01", 1000),
    ("ACTOR_RIDEABLE_ANIMAL_Buffalo", 1004),
    ("ACTOR_VEHICLE_Stagecoach", 1177),
    ("ACTOR_VEHICLE_Cart01", 1183),
    ("ACTOR_VEHICLE_Canoe01", 1189),
    ("ACTOR_VEHICLE_Raft01", 1192),
    ("ACTOR_VEHICLE_Truck01", 1193),
    ("ACTOR_VEHICLE_Car01", 1194),
    ("ACTOR_VEHICLE_Wagon02", 1199),
    ("ACTOR_VEHICLE_Coach01", 1202),
]

SAFE_ROSTER_SEED = [label for label, _ in SEED_LABELS]


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


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def parse_int(value: str) -> int:
    text = value.strip()
    return int(text, 16) if text.lower().startswith("0x") else int(text)


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


def normalize_label(label: str) -> str:
    clean = label.strip()
    if clean.lower().startswith("actor_"):
        return "ACTOR_" + clean[6:]
    return clean


def category_for(label: str) -> str:
    up = label.upper()
    if "VEHICLE" in up:
        return "vehicle"
    if "RIDEABLE_ANIMAL" in up:
        return "rideable"
    if "ARMY" in up:
        return "army"
    if any(x in up for x in ("GANG", "CRIMINAL", "OUTLAW")):
        return "gang"
    if any(x in up for x in ("LAW", "SHERIFF", "MARSHAL", "DEPUTY", "POLICE")):
        return "law"
    if "COMPANION" in up:
        return "companion"
    if "PLAYER" in up:
        return "player_like"
    if "ZOMBIE" in up or "UN_" in up:
        return "zombie"
    return "actor"


def aliases_for(label: str) -> list[str]:
    canonical = normalize_label(label)
    aliases: list[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in aliases:
            aliases.append(value)

    add(canonical)
    add(canonical.upper())
    add(canonical.lower())
    if canonical.upper().startswith("ACTOR_"):
        short = canonical[6:]
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
        canonical = normalize_label(raw_label)
        if not canonical:
            continue
        aliases = aliases_for(canonical)
        for label in aliases:
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "label": label,
                "actor_enum": str(value),
                "category": category_for(canonical),
                "source": source,
                "aliases": "|".join(a for a in aliases if a != label),
                "notes": f"canonical={canonical}; hex=0x{value:08X}",
            })
    return rows


def parse_cpp_entries(lines: list[str]) -> list[tuple[str, int]]:
    inside = False
    current: int | None = None
    entries: list[tuple[str, int]] = []
    for raw in lines:
        clean = strip_comment(raw)
        if not inside:
            inside = bool(CPP_ENUM_START_RE.search(clean))
            continue
        if clean.startswith("};"):
            break
        match = CPP_ENTRY_RE.match(clean)
        if not match:
            continue
        label, explicit = match.groups()
        current = parse_int(explicit) if explicit is not None else (0 if current is None else current + 1)
        entries.append((label, current))
    return entries


def parse_ini_entries(lines: list[str]) -> list[tuple[str, int]]:
    saw_section = False
    active_enum = False
    entries: list[tuple[str, int]] = []
    for raw in lines:
        clean = strip_comment(raw)
        if not clean:
            continue
        if SECTION_RE.match(clean):
            saw_section = True
            active_enum = clean.lower() == "[enum]"
            continue
        if saw_section and not active_enum:
            continue
        match = INI_ENTRY_RE.match(clean)
        if not match:
            continue
        label, value = match.groups()
        if label.lower().startswith("actor_"):
            entries.append((label, parse_int(value)))
    return entries


def parse_enum_source(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Enum source not found: {path}")
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    cpp = parse_cpp_entries(lines)
    if cpp:
        return rows_from_entries(cpp, "C++ enum:e_ActorModel")
    ini = parse_ini_entries(lines)
    if ini:
        return rows_from_entries(ini, "INI-style [Enum] actor list")
    raise ValueError(f"No actor enum rows parsed from: {path}")


def write_map(path: Path, rows: Iterable[dict[str, str]], replace: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak_{stamp()}"))
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("# CodeRED actor enum map\n")
        f.write("# Generated/managed by tools/codered_actor_enum_tool.py\n")
        f.write("# Edit this CSV instead of recompiling the ASI.\n")
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in HEADER})
    return path


def read_map(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    lines = [line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return {}
    lookup: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(lines):
        label = (row.get("label") or "").strip()
        enum_value = (row.get("actor_enum") or "").strip()
        if label:
            lookup[label.lower()] = row
        if enum_value:
            lookup[enum_value.lower()] = row
        for alias in re.split(r"[|;]", row.get("aliases") or ""):
            alias = alias.strip()
            if alias:
                lookup[alias.lower()] = row
    return lookup


def display_label(raw: str) -> str:
    clean = strip_comment(raw)
    for marker in ("|", "=", ","):
        if marker in clean:
            return clean.split(marker, 1)[0].strip()
    return clean.strip()


def inline_enum(raw: str) -> int | None:
    clean = strip_comment(raw)
    for marker in ("|", "=", ","):
        if marker in clean:
            try:
                return parse_int(clean.split(marker, 1)[1])
            except ValueError:
                return None
    try:
        return parse_int(clean)
    except ValueError:
        return None


def roster_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if display_label(line)]


def sanity_errors(lookup: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for label, expected in KNOWN_EXPECTED.items():
        row = lookup.get(label.lower())
        if not row:
            continue
        try:
            actual = parse_int(row.get("actor_enum") or "")
        except ValueError:
            errors.append(f"{label} has invalid actor_enum={row.get('actor_enum')!r}; expected {expected}")
            continue
        if actual != expected:
            errors.append(f"{label} has actor_enum={actual}; expected {expected}")
    return errors


def validate_roster(enum_map: Path, roster: Path) -> ValidationReport:
    lookup = read_map(enum_map)
    entries: list[RosterEntry] = []
    for raw in roster_lines(roster):
        label = display_label(raw)
        direct = inline_enum(raw)
        row = lookup.get(label.lower())
        if direct is not None:
            entries.append(RosterEntry(raw, label, True, direct, f"0x{direct:08X}", "inline roster value"))
        elif row and (row.get("actor_enum") or "").strip():
            value = parse_int(row["actor_enum"])
            entries.append(RosterEntry(raw, label, True, value, f"0x{value:08X}", row.get("source") or "actor_enum_map.csv"))
        else:
            entries.append(RosterEntry(raw, label, False, warning="unresolved_actor_enum"))
    resolved = sum(1 for entry in entries if entry.resolved)
    return ValidationReport(VERSION, now_utc(), str(enum_map), str(roster), len(entries), resolved, len(entries) - resolved, sanity_errors(lookup), entries)


def write_report(report: ValidationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def write_seed_roster(path: Path, replace: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak_{stamp()}"))
    path.write_text(
        "# CodeRED NPC roster seed\n"
        "# Safe verified no-recompile seed. Add more entries after regenerating actor_enum_map.csv from enum source.\n"
        "# Format supports label, label|number, label=number, or CSV-style actor map lookup.\n\n"
        + "\n".join(SAFE_ROSTER_SEED) + "\n",
        encoding="utf-8",
    )
    return path


def write_safe_roster(report: ValidationReport, output: Path, replace: bool) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not replace:
        shutil.copy2(output, output.with_suffix(output.suffix + f".bak_{stamp()}"))
    lines = ["# CodeRED spawn-safe verified roster", "# Generated by tools/codered_actor_enum_tool.py", "# Only resolved entries are included.", ""]
    for entry in report.entries:
        if entry.resolved and entry.actor_enum is not None:
            lines.append(f"{entry.label}|{entry.actor_enum}  # {entry.actor_enum_hex} from {entry.source}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def add_replace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--replace", dest="sub_replace", action="store_true", default=False,
                        help="Replace outputs without timestamp backups. Works before or after the subcommand.")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate/validate Code RED actor enum data without recompiling the ASI.")
    p.add_argument("--enum-map", type=Path, default=DEFAULT_MAP)
    p.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    p.add_argument("--replace", action="store_true", help="Replace outputs without timestamp backups. Works before or after the subcommand.")
    sub = p.add_subparsers(dest="cmd")

    seed = sub.add_parser("seed", help="Write a small verified seed actor_enum_map.csv.")
    seed.add_argument("--safe-roster", action="store_true")
    add_replace(seed)

    rebuild = sub.add_parser("rebuild", help="Rebuild actor_enum_map.csv from C++ enum or INI-style [Enum] source.")
    rebuild.add_argument("--enums-h", type=Path)
    rebuild.add_argument("--source", type=Path)
    add_replace(rebuild)

    validate = sub.add_parser("validate", help="Validate npc_roster.txt against actor_enum_map.csv.")
    add_replace(validate)

    safe = sub.add_parser("safe-roster", help="Write npc_roster_safe_verified.txt from resolved roster entries.")
    safe.add_argument("--output", type=Path, default=DEFAULT_SAFE_ROSTER)
    add_replace(safe)

    summary = sub.add_parser("summary", help="Print a compact validation summary.")
    add_replace(summary)
    return p


def replace_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "replace", False) or getattr(args, "sub_replace", False))


def print_report(report: ValidationReport) -> None:
    print(f"Roster entries:  {report.total_roster_entries}")
    print(f"Resolved:        {report.resolved_entries}")
    print(f"Unresolved:      {report.unresolved_entries}")
    print(f"Sanity errors:   {len(report.sanity_errors)}")
    print(f"Report:          {report.enum_map if False else DEFAULT_REPORT}")


def main() -> int:
    args = parser().parse_args()
    cmd = args.cmd or "summary"
    replace = replace_enabled(args)

    if cmd == "seed":
        write_map(args.enum_map, rows_from_entries(SEED_LABELS, "CodeRED research sanity seed"), replace)
        if args.safe_roster:
            write_seed_roster(args.roster, replace)
        report = validate_roster(args.enum_map, args.roster)
        write_report(report, args.report)
        print(f"Seeded enum map: {args.enum_map}")
        if args.safe_roster:
            print(f"Seeded roster:   {args.roster}")
        print(f"Report:          {args.report}")
        return 0 if not report.sanity_errors else 2

    if cmd == "rebuild":
        source = args.source or args.enums_h
        if not source:
            raise SystemExit("rebuild requires --source or --enums-h")
        rows = parse_enum_source(source)
        write_map(args.enum_map, rows, replace)
        report = validate_roster(args.enum_map, args.roster)
        write_report(report, args.report)
        print(f"Parsed rows:     {len(rows)}")
        print(f"Enum source:     {source}")
        print(f"Enum map:        {args.enum_map}")
        print(f"Report:          {args.report}")
        for error in report.sanity_errors:
            print(" - " + error)
        return 0 if not report.sanity_errors else 2

    report = validate_roster(args.enum_map, args.roster)
    write_report(report, args.report)
    if cmd == "safe-roster":
        print(f"Safe roster:     {write_safe_roster(report, args.output, replace)}")
    print(f"Roster entries:  {report.total_roster_entries}")
    print(f"Resolved:        {report.resolved_entries}")
    print(f"Unresolved:      {report.unresolved_entries}")
    print(f"Sanity errors:   {len(report.sanity_errors)}")
    print(f"Report:          {args.report}")
    for error in report.sanity_errors:
        print(" - " + error)
    return 0 if not report.sanity_errors and report.unresolved_entries == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
