#!/usr/bin/env python3
"""Rebuild Code RED actor enum data for the AI trainer/menu.

This is the conservative enum repair path:
- prefers a user-supplied Enums.h/enums.h source when present
- otherwise uses the bundled SC-CL RDR consts32.h source in related_apps
- supports classic C/C++ enum bodies and INI-style [Enum] lists
- writes actor_enum_map.csv plus optional inline rosters
- fails when known sanity values are wrong instead of silently producing bad spawns
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

VERSION = "1.0.0-ai-trainer-enum-repair"
DEFAULT_SOURCE_CANDIDATES = [
    Path("enums.h"),
    Path("Enums.h"),
    Path("related_apps/code_red_sccl_attempt_bundle_v1/code_red_script_compile_lab_v1/include/RDR/consts32.h"),
]
DEFAULT_MAP = Path("data/codered/actor_enum_map.csv")
DEFAULT_ROSTER = Path("data/codered/npc_roster.txt")
DEFAULT_REPORT = Path("logs/CodeRED_Actor_Enum_Rebuild_Report.json")
HEADER = ["label", "actor_enum", "category", "source", "aliases", "notes"]

ENUM_START_RE = re.compile(r"^\s*(?:typedef\s+)?enum\s+(?:e_ActorModel|eActor|e_Actor)\b", re.IGNORECASE)
ENTRY_RE = re.compile(r"^\s*(ACTOR_[A-Za-z0-9_]+)\s*(?:=\s*(-?\d+|0x[0-9A-Fa-f]+))?\s*,?")
INI_ENTRY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]+)\s*=\s*(-?\d+|0x[0-9A-Fa-f]+)\s*$")
SECTION_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")

KNOWN_EXPECTED = {
    "ACTOR_PLAYER": 0,
    "ACTOR_PLAYER_JACK": 1,
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

SAFE_ROSTER = [
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
class Report:
    version: str
    generated_utc: str
    source: str
    actor_entries: int
    csv_rows: int
    roster_entries: int
    sanity_errors: list[str]
    outputs: list[str]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_int(value: str) -> int:
    text = value.strip()
    return int(text, 16) if text.lower().startswith("0x") else int(text)


def strip_comment(raw: str) -> str:
    in_quotes = False
    out = []
    for ch in raw:
        if ch == '"':
            in_quotes = not in_quotes
        if not in_quotes and (ch == "#" or ch == ";" or (ch == "/" and "".join(out).endswith("/"))):
            if ch == "/" and out:
                out.pop()
            break
        out.append(ch)
    return "".join(out).strip()


def normalize_actor(label: str) -> str:
    clean = label.strip()
    if clean.lower().startswith("actor_"):
        return "ACTOR_" + clean[6:]
    return clean


def category_for(label: str) -> str:
    up = label.upper()
    if "INVALID" in up:
        return "invalid"
    if "VEHICLE" in up:
        return "vehicle"
    if "RIDEABLE_ANIMAL" in up:
        return "rideable"
    if "ARMY" in up:
        return "army"
    if any(x in up for x in ("LAW", "SHERIFF", "MARSHAL", "DEPUTY", "POLICE")):
        return "law"
    if any(x in up for x in ("GANG", "CRIMINAL", "OUTLAW", "BANDITO")):
        return "gang"
    if "PLAYER" in up:
        return "player_like"
    if "ZOMBIE" in up or "UN_" in up:
        return "zombie"
    return "actor"


def aliases_for(canonical: str) -> list[str]:
    aliases: list[str] = []
    def add(value: str) -> None:
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


def parse_enum_source(path: Path) -> list[tuple[str, int]]:
    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    entries: list[tuple[str, int]] = []

    # INI-style source: [Enum]\nactor_name = value
    section = ""
    for raw in text:
        clean = strip_comment(raw)
        if not clean:
            continue
        if SECTION_RE.match(clean):
            section = clean.strip()[1:-1].lower()
            continue
        if section == "enum":
            match = INI_ENTRY_RE.match(clean)
            if match and match.group(1).lower().startswith("actor_"):
                entries.append((normalize_actor(match.group(1)), parse_int(match.group(2))))
    if entries:
        return entries

    # C/C++ enum body source.
    inside = False
    current: int | None = None
    for raw in text:
        clean = strip_comment(raw)
        if not inside:
            inside = bool(ENUM_START_RE.search(clean))
            continue
        if clean.startswith("};") or clean.startswith("}"):
            break
        match = ENTRY_RE.match(clean)
        if not match:
            continue
        label, explicit = match.groups()
        current = parse_int(explicit) if explicit is not None else (0 if current is None else current + 1)
        entries.append((normalize_actor(label), current))
    return entries


def build_rows(entries: list[tuple[str, int]], source_label: str) -> list[dict[str, str]]:
    rows = []
    seen = set()
    for canonical, value in entries:
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
                "source": source_label,
                "aliases": "|".join(a for a in aliases if a != label),
                "notes": f"canonical={canonical}; hex=0x{value:08X}",
            })
    return rows


def read_lookup(rows: list[dict[str, str]]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for row in rows:
        try:
            value = parse_int(row["actor_enum"])
        except Exception:
            continue
        for label in [row.get("label", ""), *re.split(r"[|;]", row.get("aliases", ""))]:
            label = label.strip()
            if label:
                lookup[label.lower()] = value
    return lookup


def sanity_errors(rows: list[dict[str, str]]) -> list[str]:
    lookup = read_lookup(rows)
    errors = []
    for label, expected in KNOWN_EXPECTED.items():
        actual = lookup.get(label.lower())
        if actual is None:
            errors.append(f"missing {label}; expected {expected}")
        elif actual != expected:
            errors.append(f"{label}={actual}; expected {expected}")
    return errors


def backup_if_needed(path: Path, replace: bool) -> None:
    if path.exists() and not replace:
        suffix = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak_{suffix}"))


def write_csv(path: Path, rows: list[dict[str, str]], replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_if_needed(path, replace)
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write("# CodeRED actor enum map\n")
        f.write("# Generated by tools/codered_rebuild_actor_enum_map.py\n")
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


def canonical_entries(rows: list[dict[str, str]]) -> list[tuple[str, int, str]]:
    chosen: dict[int, tuple[str, int, str]] = {}
    for row in rows:
        label = row.get("label", "")
        if not label.upper().startswith("ACTOR_"):
            continue
        value = parse_int(row["actor_enum"])
        if value < 0:
            continue
        existing = chosen.get(value)
        if existing is None or (existing[0].isupper() and not label.isupper()) or (existing[0].islower() and not label.islower()):
            chosen[value] = (label, value, row.get("category", category_for(label)))
    return [chosen[k] for k in sorted(chosen)]


def write_roster(path: Path, rows: list[dict[str, str]], *, replace: bool, safe_only: bool) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_if_needed(path, replace)
    lookup = read_lookup(rows)
    lines = [
        "# CodeRED NPC roster",
        "# Generated by tools/codered_rebuild_actor_enum_map.py",
        "# Format: ACTOR_NAME|actor_enum",
        "",
    ]
    count = 0
    if safe_only:
        for label in SAFE_ROSTER:
            value = lookup[label.lower()]
            lines.append(f"{label}|{value}  # 0x{value:08X}")
            count += 1
    else:
        for label, value, category in canonical_entries(rows):
            lines.append(f"{label}|{value}  # {category} 0x{value:08X}")
            count += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def resolve_source(args: argparse.Namespace) -> Path:
    if args.source:
        return Path(args.source)
    for candidate in DEFAULT_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No enum source found. Expected enums.h, Enums.h, or bundled consts32.h.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Rebuild CodeRED actor enum map for the AI trainer/menu.")
    p.add_argument("--source", help="Enum source path. Defaults to enums.h/Enums.h/bundled consts32.h.")
    p.add_argument("--enum-map", type=Path, default=DEFAULT_MAP)
    p.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    p.add_argument("--replace", action="store_true")
    p.add_argument("--write-inline-roster", action="store_true", help="Write npc_roster.txt as ACTOR_NAME|enum values.")
    p.add_argument("--safe-roster-only", action="store_true", help="When writing roster, keep the small safe proof roster instead of all actors.")
    return p


def main() -> int:
    args = build_parser().parse_args()
    source = resolve_source(args)
    entries = parse_enum_source(source)
    if not entries:
        raise SystemExit(f"No ACTOR_* entries parsed from {source}")
    rows = build_rows(entries, str(source))
    errors = sanity_errors(rows)
    outputs: list[str] = []
    if not errors:
        write_csv(args.enum_map, rows, args.replace)
        outputs.append(str(args.enum_map))
        roster_count = 0
        if args.write_inline_roster:
            roster_count = write_roster(args.roster, rows, replace=args.replace, safe_only=args.safe_roster_only)
            outputs.append(str(args.roster))
    else:
        roster_count = 0
    report = Report(VERSION, utc_now(), str(source), len(entries), len(rows), roster_count, errors, outputs)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    print(f"source={source}")
    print(f"actor_entries={len(entries)} csv_rows={len(rows)}")
    print(f"sanity_errors={len(errors)} report={args.report}")
    for error in errors:
        print("ERROR " + error)
    return 0 if not errors else 2

if __name__ == "__main__":
    raise SystemExit(main())
