#!/usr/bin/env python3
"""
CodeRED actor enum workbench.

This is the Python-side editor/validator for the CodeRED ScriptHookRDR AI menu.
The point is to make actor work data-driven:

    edit data/codered/actor_enum_map.csv -> press F5 in game -> test again

The ASI only needs one rebuild after adding the map loader. After that, actor
labels, aliases, and enum values can be changed from CSV/text files.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

VERSION = "1.1.0-actor-enum-workbench"
DEFAULT_MAP = Path("data/codered/actor_enum_map.csv")
DEFAULT_ROSTER = Path("data/codered/npc_roster.txt")
DEFAULT_REPORT = Path("scratch/codered_actor_enum_report.json")

LABEL_RE = re.compile(r"^[A-Za-z0-9_./:-]{2,128}$")
COMMENT_PREFIXES = ("#", ";")

SEED_LABELS = [
    "AE_Caucasian_Army_Easy01",
    "AE_Caucasian_Army_Easy02",
    "AE_Caucasian_Army_Easy03",
    "AE_Caucasian_Army_Medium01",
    "AE_Caucasian_Army_Medium02",
    "AE_Caucasian_Army_Medium03",
    "AE_Caucasian_Army_Hard01",
    "AE_Caucasian_Army_Hard02",
    "AE_Caucasian_Army_Hard03",
    "AE_Mexican_Army_Easy01",
    "AE_Mexican_Army_Easy02",
    "AE_Mexican_Army_Easy03",
    "AE_Mexican_Army_Medium01",
    "AE_Mexican_Army_Medium02",
    "AE_Mexican_Army_Medium03",
    "AE_Mexican_Army_Hard01",
    "AE_Mexican_Army_Hard02",
    "AE_Mexican_Army_Hard03",
    "amb_fh_farmer06",
    "amb_cowboy",
    "amb_worker",
    "amb_townswoman",
    "amb_townsman",
    "amb_mexican",
    "amb_rancher",
    "amb_miner",
    "amb_prostitute",
    "gent_default",
    "gent_rancher",
    "gent_worker",
    "gped_default",
    "gped_lawman",
    "gped_bandito",
    "player_bandito",
    "player_lawman",
    "player_marston",
    "player_dutch",
    "player_javier",
    "player_bill",
    "law_sheriff",
    "law_deputy",
    "misc_rancher",
    "misc_bountyhunter",
    "com_companion",
    "crm_outlaw",
    "crm_bandit",
    "anc_oldman",
    "zombie_default",
]

CATEGORY_HINTS = [
    ("AE_Caucasian_Army_", "army"),
    ("AE_Mexican_Army_", "army"),
    ("amb_", "ambient"),
    ("gent_", "generic_ped"),
    ("gped_", "generic_ped"),
    ("player_", "player_like"),
    ("law_", "law"),
    ("misc_", "named"),
    ("com_", "companion"),
    ("crm_", "gang"),
    ("anc_", "named"),
    ("zombie", "zombie"),
]

ALIASES = {
    "player_marston": "john_marston|marston",
    "player_dutch": "dutch",
    "player_javier": "javier",
    "player_bill": "bill|bill_williamson",
    "law_sheriff": "sheriff",
    "law_deputy": "deputy",
    "misc_bountyhunter": "bountyhunter",
    "com_companion": "companion",
    "crm_outlaw": "outlaw",
    "crm_bandit": "bandit",
    "anc_oldman": "oldman",
    "zombie_default": "zombie",
}


@dataclass
class ActorEnumRow:
    label: str
    actor_enum: str = ""
    category: str = ""
    source: str = "manual"
    aliases: str = ""
    notes: str = ""

    @property
    def resolved(self) -> bool:
        return parse_actor_enum(self.actor_enum) is not None

    @property
    def enum_int(self) -> int | None:
        return parse_actor_enum(self.actor_enum)

    def as_csv_row(self) -> dict[str, str]:
        return {
            "label": self.label,
            "actor_enum": self.actor_enum,
            "category": self.category,
            "source": self.source,
            "aliases": self.aliases,
            "notes": self.notes,
        }


def repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


def rel(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def clean_label(raw: str) -> str:
    label = raw.strip().strip('"').strip("'")
    # Support inline roster forms: label|123, label=123, label,123.
    for marker in ("|", "=", ","):
        if marker in label:
            label = label.split(marker, 1)[0].strip()
    return label


def category_for(label: str) -> str:
    lower = label.lower()
    for prefix, category in CATEGORY_HINTS:
        if lower.startswith(prefix.lower()) or prefix.lower() in lower:
            return category
    return "other"


def parse_actor_enum(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    if not text or text.lower() in {"?", "none", "null", "todo", "unresolved"}:
        return None
    base = 16 if text.lower().startswith("0x") else 10
    try:
        enum_value = int(text, base)
    except ValueError:
        return None
    if enum_value <= 0 or enum_value > 0x7FFFFFFF:
        return None
    return enum_value


def enum_to_text(value: str | int, *, prefer_hex: bool = False) -> str:
    enum_value = parse_actor_enum(value)
    if enum_value is None:
        raise ValueError(f"invalid actor enum: {value!r}")
    return f"0x{enum_value:08X}" if prefer_hex else str(enum_value)


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak_{stamp}")
    shutil.copy2(path, backup)
    return backup


def read_roster_labels(path: Path) -> list[str]:
    labels: list[str] = []
    if not path.exists():
        return labels
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith(COMMENT_PREFIXES):
            continue
        text = text.split("#", 1)[0].strip()
        label = clean_label(text)
        if label and label not in labels:
            labels.append(label)
    return labels


def csv_comments() -> str:
    return (
        "# CodeRED actor enum map\n"
        "# Edit this file instead of recompiling the ASI.\n"
        "# Format: label,actor_enum,category,source,aliases,notes\n"
        "# actor_enum accepts decimal or hex, e.g. amb_prostitute,12345 or player_marston,0x00003039\n"
        "# Blank actor_enum means unresolved/research-only. Press F5 in-game after edits.\n"
    )


def read_map(path: Path) -> list[ActorEnumRow]:
    rows: list[ActorEnumRow] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        filtered = (line for line in handle if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(filtered)
        if not reader.fieldnames:
            return rows
        for raw in reader:
            label = clean_label(raw.get("label") or raw.get("name") or "")
            if not label:
                continue
            row = ActorEnumRow(
                label=label,
                actor_enum=(raw.get("actor_enum") or raw.get("enum") or "").strip(),
                category=(raw.get("category") or category_for(label)).strip(),
                source=(raw.get("source") or "manual").strip(),
                aliases=(raw.get("aliases") or "").strip(),
                notes=(raw.get("notes") or "").strip(),
            )
            rows.append(row)
    return rows


def write_map(path: Path, rows: Sequence[ActorEnumRow], *, backup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        backup_file(path)
    deduped: dict[str, ActorEnumRow] = {}
    for row in rows:
        if not row.label:
            continue
        deduped[row.label.lower()] = row
    ordered = sorted(deduped.values(), key=lambda row: (row.category.lower(), row.label.lower()))
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(csv_comments())
        writer = csv.DictWriter(handle, fieldnames=["label", "actor_enum", "category", "source", "aliases", "notes"])
        writer.writeheader()
        for row in ordered:
            writer.writerow(row.as_csv_row())


def seed_rows(labels: Iterable[str]) -> list[ActorEnumRow]:
    rows: list[ActorEnumRow] = []
    for label in labels:
        label = clean_label(label)
        if not label:
            continue
        rows.append(
            ActorEnumRow(
                label=label,
                actor_enum="",
                category=category_for(label),
                source="seed",
                aliases=ALIASES.get(label, ""),
                notes="fill actual eActorEnum integer",
            )
        )
    return rows


def merge_rows(base: Sequence[ActorEnumRow], incoming: Sequence[ActorEnumRow], *, prefer_incoming: bool = False) -> list[ActorEnumRow]:
    merged: dict[str, ActorEnumRow] = {row.label.lower(): row for row in base if row.label}
    for row in incoming:
        key = row.label.lower()
        if key not in merged:
            merged[key] = row
            continue
        current = merged[key]
        # Preserve known-good enum values unless explicit replacement is requested.
        if prefer_incoming or (not current.resolved and row.resolved):
            if not row.category:
                row.category = current.category
            if not row.aliases:
                row.aliases = current.aliases
            merged[key] = row
        else:
            if not current.category:
                current.category = row.category
            if not current.aliases:
                current.aliases = row.aliases
            if not current.notes and row.notes:
                current.notes = row.notes
    return list(merged.values())


def import_source(path: Path) -> list[ActorEnumRow]:
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return import_json_rows(data, source=str(path))
    if suffix == ".csv":
        return read_map(path)
    labels: list[str] = []
    rows: list[ActorEnumRow] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith(COMMENT_PREFIXES):
            continue
        text = text.split("#", 1)[0].strip()
        # Accept label=enum / label|enum / label,enum from quick notes.
        enum_text = ""
        label_text = text
        for marker in ("|", "=", ","):
            if marker in text:
                label_text, enum_text = text.split(marker, 1)
                break
        label = clean_label(label_text)
        if not label:
            continue
        if enum_text:
            rows.append(
                ActorEnumRow(
                    label=label,
                    actor_enum=enum_to_text(enum_text) if parse_actor_enum(enum_text) else "",
                    category=category_for(label),
                    source=str(path),
                    aliases=ALIASES.get(label, ""),
                    notes="imported text source",
                )
            )
        else:
            labels.append(label)
    rows.extend(seed_rows(labels))
    return rows


def import_json_rows(data, *, source: str) -> list[ActorEnumRow]:
    rows: list[ActorEnumRow] = []
    if isinstance(data, dict):
        if isinstance(data.get("actors"), list):
            for item in data["actors"]:
                rows.extend(import_json_rows(item, source=source))
        if isinstance(data.get("models"), list):
            for item in data["models"]:
                rows.extend(import_json_rows(item, source=source))
        label = data.get("label") or data.get("name") or data.get("model")
        if isinstance(label, str):
            enum_value = data.get("actor_enum") or data.get("enum") or ""
            enum_text = enum_to_text(enum_value) if parse_actor_enum(enum_value) else ""
            rows.append(
                ActorEnumRow(
                    label=clean_label(label),
                    actor_enum=enum_text,
                    category=str(data.get("category") or category_for(label)),
                    source=str(data.get("source") or source),
                    aliases=str(data.get("aliases") or ""),
                    notes=str(data.get("notes") or "imported json source"),
                )
            )
    elif isinstance(data, list):
        for item in data:
            rows.extend(import_json_rows(item, source=source))
    elif isinstance(data, str):
        rows.append(ActorEnumRow(label=clean_label(data), category=category_for(data), source=source))
    return [row for row in rows if row.label]


def write_roster(path: Path, rows: Sequence[ActorEnumRow], *, resolved_only: bool = False, inline_enum: bool = False, backup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        backup_file(path)
    selected = [row for row in rows if not resolved_only or row.resolved]
    selected = sorted(selected, key=lambda row: (not row.resolved, row.category.lower(), row.label.lower()))
    lines = [
        "# CodeRED NPC roster generated by tools/codered_actor_enum_workbench.py",
        "# Edit actor enum values in data/codered/actor_enum_map.csv, then press F5 in game.",
        "# One label per line. Inline label|enum is supported but the CSV map is preferred.",
        "",
    ]
    for row in selected:
        if inline_enum and row.resolved:
            lines.append(f"{row.label}|{row.actor_enum}")
        else:
            lines.append(row.label)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_rows(rows: Sequence[ActorEnumRow]) -> dict:
    labels: dict[str, int] = {}
    aliases: dict[str, str] = {}
    duplicate_labels: list[str] = []
    duplicate_aliases: list[dict[str, str]] = []
    invalid_labels: list[str] = []
    invalid_enums: list[dict[str, str]] = []

    for row in rows:
        key = row.label.lower()
        labels[key] = labels.get(key, 0) + 1
        if labels[key] == 2:
            duplicate_labels.append(row.label)
        if not LABEL_RE.match(row.label):
            invalid_labels.append(row.label)
        if row.actor_enum and not row.resolved:
            invalid_enums.append({"label": row.label, "actor_enum": row.actor_enum})
        for alias in [a.strip() for a in row.aliases.replace(";", "|").split("|") if a.strip()]:
            alias_key = alias.lower()
            if alias_key in aliases and aliases[alias_key] != row.label:
                duplicate_aliases.append({"alias": alias, "first": aliases[alias_key], "second": row.label})
            aliases.setdefault(alias_key, row.label)

    resolved = [row for row in rows if row.resolved]
    unresolved = [row for row in rows if not row.resolved]
    return {
        "tool": VERSION,
        "total": len(rows),
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "duplicate_labels": duplicate_labels,
        "duplicate_aliases": duplicate_aliases,
        "invalid_labels": invalid_labels,
        "invalid_enums": invalid_enums,
        "resolved_labels": [row.label for row in resolved],
        "unresolved_labels": [row.label for row in unresolved],
    }


def save_report(root: Path, report: dict, out: Path = DEFAULT_REPORT) -> Path:
    report_path = rel(root, out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def print_rows(rows: Sequence[ActorEnumRow], *, filter_text: str = "", resolved_only: bool = False, limit: int = 100) -> None:
    filt = filter_text.lower().strip()
    shown = []
    for row in rows:
        hay = f"{row.label} {row.category} {row.aliases} {row.notes}".lower()
        if resolved_only and not row.resolved:
            continue
        if filt and filt not in hay:
            continue
        shown.append(row)
    print(f"rows={len(rows)} shown={len(shown)} resolved_only={resolved_only} filter={filter_text!r}")
    for idx, row in enumerate(shown[:limit]):
        enum_text = row.actor_enum if row.actor_enum else "<unresolved>"
        print(f"{idx:04d}  {row.label:<36} {enum_text:<12} {row.category:<14} {row.aliases}")
    if len(shown) > limit:
        print(f"... {len(shown) - limit} more")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CodeRED actor enum CSV editor/validator")
    parser.add_argument("--root", default=None, help="Project root. Defaults to parent of tools/.")
    parser.add_argument("--map", default=str(DEFAULT_MAP), help="Actor enum CSV path")
    parser.add_argument("--roster", default=str(DEFAULT_ROSTER), help="NPC roster text path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create or refresh actor_enum_map.csv from seed/roster labels")
    p_init.add_argument("--merge-roster", action="store_true", help="Also merge labels already present in npc_roster.txt")
    p_init.add_argument("--no-backup", action="store_true")

    p_list = sub.add_parser("list", help="List map rows")
    p_list.add_argument("--filter", default="")
    p_list.add_argument("--resolved", action="store_true")
    p_list.add_argument("--limit", type=int, default=100)

    p_set = sub.add_parser("set", help="Set one actor enum value")
    p_set.add_argument("label")
    p_set.add_argument("actor_enum", help="Decimal or hex enum value")
    p_set.add_argument("--alias", action="append", default=[], help="Alias to append")
    p_set.add_argument("--category", default=None)
    p_set.add_argument("--source", default="manual")
    p_set.add_argument("--hex", action="store_true", help="Store enum in hex form")

    p_unset = sub.add_parser("unset", help="Clear one actor enum but keep the label")
    p_unset.add_argument("label")

    p_import = sub.add_parser("import", help="Merge rows from CSV/JSON/TXT source")
    p_import.add_argument("source")
    p_import.add_argument("--replace", action="store_true", help="Incoming rows replace existing rows")

    p_roster = sub.add_parser("build-roster", help="Rebuild npc_roster.txt from actor_enum_map.csv")
    p_roster.add_argument("--resolved-only", action="store_true")
    p_roster.add_argument("--inline-enum", action="store_true", help="Write label|enum for resolved rows")

    p_validate = sub.add_parser("validate", help="Validate actor enum map and write scratch report")
    p_validate.add_argument("--strict", action="store_true", help="Fail if no resolved enum rows exist")

    p_resolve = sub.add_parser("resolve", help="Resolve one label/alias to an actor enum")
    p_resolve.add_argument("label")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else repo_root_from_file()
    map_path = rel(root, args.map)
    roster_path = rel(root, args.roster)

    if args.command == "init":
        labels = list(SEED_LABELS)
        if args.merge_roster:
            for label in read_roster_labels(roster_path):
                if label not in labels:
                    labels.append(label)
        existing = read_map(map_path)
        rows = merge_rows(seed_rows(labels), existing)
        write_map(map_path, rows, backup=not args.no_backup)
        report = validate_rows(rows)
        report_path = save_report(root, report)
        print(f"initialized {len(rows)} rows -> {map_path}")
        print(f"report -> {report_path}")
        return 0

    rows = read_map(map_path)

    if args.command == "list":
        print_rows(rows, filter_text=args.filter, resolved_only=args.resolved, limit=args.limit)
        return 0

    if args.command == "set":
        enum_text = enum_to_text(args.actor_enum, prefer_hex=args.hex)
        target = args.label.lower()
        updated = False
        for row in rows:
            if row.label.lower() == target:
                row.actor_enum = enum_text
                if args.category:
                    row.category = args.category
                row.source = args.source
                aliases = [a for a in row.aliases.split("|") if a]
                for alias in args.alias:
                    if alias not in aliases:
                        aliases.append(alias)
                row.aliases = "|".join(aliases)
                row.notes = "known-good/manual enum"
                updated = True
                break
        if not updated:
            rows.append(
                ActorEnumRow(
                    label=args.label,
                    actor_enum=enum_text,
                    category=args.category or category_for(args.label),
                    source=args.source,
                    aliases="|".join(args.alias),
                    notes="known-good/manual enum",
                )
            )
        write_map(map_path, rows)
        print(f"set {args.label} -> {enum_text}")
        return 0

    if args.command == "unset":
        found = False
        for row in rows:
            if row.label.lower() == args.label.lower():
                row.actor_enum = ""
                row.notes = "enum cleared"
                found = True
                break
        if not found:
            print(f"label not found: {args.label}", file=sys.stderr)
            return 2
        write_map(map_path, rows)
        print(f"cleared enum for {args.label}")
        return 0

    if args.command == "import":
        incoming = import_source(rel(root, args.source))
        rows = merge_rows(rows, incoming, prefer_incoming=args.replace)
        write_map(map_path, rows)
        print(f"merged {len(incoming)} incoming rows -> {map_path}")
        return 0

    if args.command == "build-roster":
        write_roster(roster_path, rows, resolved_only=args.resolved_only, inline_enum=args.inline_enum)
        mode = "resolved only" if args.resolved_only else "all labels"
        print(f"rebuilt roster ({mode}) -> {roster_path}")
        return 0

    if args.command == "validate":
        report = validate_rows(rows)
        report_path = save_report(root, report)
        print(json.dumps({k: v for k, v in report.items() if k not in {"resolved_labels", "unresolved_labels"}}, indent=2))
        print(f"report -> {report_path}")
        if report["duplicate_labels"] or report["duplicate_aliases"] or report["invalid_labels"] or report["invalid_enums"]:
            return 1
        if args.strict and report["resolved"] == 0:
            print("strict validation failed: no resolved actor enum rows yet", file=sys.stderr)
            return 1
        return 0

    if args.command == "resolve":
        target = args.label.lower()
        for row in rows:
            aliases = [a.strip().lower() for a in row.aliases.replace(";", "|").split("|") if a.strip()]
            if row.label.lower() == target or target in aliases:
                if row.resolved:
                    print(f"{args.label} -> {row.enum_int} / 0x{row.enum_int:08X} ({row.label})")
                    return 0
                print(f"{args.label} exists as {row.label}, but actor_enum is unresolved")
                return 1
        print(f"{args.label} not found")
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
