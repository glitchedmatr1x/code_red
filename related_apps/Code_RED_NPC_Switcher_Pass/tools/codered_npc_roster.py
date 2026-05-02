#!/usr/bin/env python3
"""
CodeRED NPC roster tools.

Purpose:
- Keep the trainer/AI companion console from being locked to a tiny hardcoded NPC list.
- Load model names from existing text/JSON lists.
- Optionally scan large RPF/archive binaries for model-name strings such as gent_, gped_, amb_, and named fragment actors.

This is an offline/private modding helper. It does not attach to a running game and does not bypass services.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator, Sequence

VERSION = "1.0.0-npc-roster-switcher"

# RDR fragment naming families observed/expected in fragments/content lists.
# Keep this conservative so binary scans do not fill the roster with texture/material garbage.
DEFAULT_PREFIXES = (
    "gent_",
    "gped_",
    "amb_",
    "anc_",
    "com_",
    "crm_",
    "law_",
    "misc_",
    "nore_",
    "player_",
    "ranch_",
    "zombie_",
    "mex_",
)

# CS names are useful when they come from a real text/file list, but a raw binary scan has many random cs_ hits.
TEXT_ONLY_PREFIXES = ("cs_", "mp_")
ENTITY_MARKER = b"t:/rdr2/assets/entity/"
TOKEN_CHARS = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-"
STOP_CHARS = set(TOKEN_CHARS)
NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./-]{2,128}")
TEXT_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:gent|gped|amb|anc|com|crm|law|misc|nore|player|ranch|zombie|mex|cs|mp)_[A-Za-z0-9_./-]{2,128}(?![A-Za-z0-9_])",
    re.IGNORECASE,
)

BAD_SUFFIXES = (
    ".dds",
    ".ddn",
    ".ddr",
    ".png",
    ".jpg",
    ".jpeg",
    ".tga",
    ".bmp",
    ".xml",
    ".txt",
    ".csv",
    ".json",
    ".wsc",
    ".ysc",
    ".xsf",
)
BAD_EXACT_NAMES = {
    "ambient",
    "animal_or_mount",
    "generic_ped",
    "named_fragment",
    "player_like",
    "script_or_mp",
    "zombie",
    "fallback",
}

BAD_PREFIXES = (
    "amb_body",
    "amb_candle",
    "amb_flies",
    "amb_gunbelt",
    "amb_hair",
    "amb_lantern",
    "amb_rifle",
    "amb_skin",
    "amb_sleeve",
    "amb_stringtie",
    "melee_",
)

BAD_SUBSTRINGS = (
    "alpha",
    "alphakill",
    "alphacrop",
    "leather",
    "shagreen",
    "regular",
    "clavicle",
    "attachment",
    "tongue_",
    "spine",
    "pelvis",
    "wrist",
    "elbow",
    "skin",
    "gorehead",
    "coverlow",
    "blnd",
    "body0",
    "head0",
    "gunbelt",
    "holster",
    "hat0",
)

ANIMAL_SEEDS = {
    "chicken01",
    "chicken02",
    "chicken03",
    "crow01",
    "duckfroer02",
    "ducknorth02",
    "horsezombie03",
    "horsezombie04",
    "wolfzombie01",
}

@dataclass(frozen=True)
class RosterEntry:
    name: str
    category: str
    source: str


def repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_name(raw: str) -> str | None:
    text = raw.strip().replace("\\", "/")
    if not text:
        return None
    # Paths from the archive marker should collapse to the leaf actor/model name.
    marker = "t:/rdr2/assets/entity/"
    lower = text.lower()
    if marker in lower:
        text = text[lower.index(marker) + len(marker):]
    text = text.split("\x00", 1)[0].strip().strip("/.-_")
    if "/" in text:
        text = text.rstrip("/").split("/")[-1]
    if not text:
        return None
    text = text.strip().strip("/.-_")
    if not NAME_RE.fullmatch(text):
        return None
    # Names are consumed by external trainer/game bridge code; normalize case to avoid duplicates.
    text = text.lower()
    # Trim very common binary-scan trailing garbage on a few zombie horse tokens.
    text = re.sub(r"(horsezombie0[0-9]).*", r"\1", text)
    text = re.sub(r"(wolfzombie0[0-9]).*", r"\1", text)
    return text


def category_for(name: str) -> str:
    if name.startswith(("gent_", "gped_")):
        return "generic_ped"
    if name.startswith("amb_"):
        return "ambient"
    if name.startswith("player_"):
        return "player_like"
    if name.startswith("zombie_") or "zombie" in name:
        return "zombie"
    if name in ANIMAL_SEEDS or name.startswith(("chicken", "crow", "duck", "horse", "wolf")):
        return "animal_or_mount"
    if name.startswith(("anc_", "com_", "crm_", "law_", "misc_", "nore_", "ranch_", "mex_")) or name.endswith("_cs"):
        return "named_fragment"
    if name.startswith(("cs_", "mp_")):
        return "script_or_mp"
    return "other"


def looks_spawn_candidate(name: str, *, from_binary_scan: bool) -> bool:
    if name in BAD_EXACT_NAMES:
        return False
    if len(name) < 5 or len(name) > 96:
        return False
    if "." in name:
        return False
    if any(name.startswith(prefix) for prefix in BAD_PREFIXES):
        return False
    if any(name.endswith(suffix) for suffix in BAD_SUFFIXES):
        return False
    if from_binary_scan and any(bad in name for bad in BAD_SUBSTRINGS):
        return False
    if from_binary_scan and name.startswith(("cs_", "mp_")):
        return False
    prefixes = DEFAULT_PREFIXES + (() if from_binary_scan else TEXT_ONLY_PREFIXES)
    if name in ANIMAL_SEEDS:
        return True
    if name.startswith(prefixes):
        # Reject tiny binary fragments such as anc_i/crm_d/amb_ck.
        tail = name.split("_", 1)[1] if "_" in name else name
        if from_binary_scan and len(tail) < 4:
            return False
        return True
    if name.endswith("_cs") and len(name) >= 9:
        return True
    # Special named fragments in RDR often appear without a prefix but with known useful words.
    special_words = ("sheriff", "marshal", "rebel", "outlaw", "bandito", "cattlerus", "prostitute", "farmer")
    return any(word in name for word in special_words)


def iter_json_model_names(obj) -> Iterator[str]:
    """Yield likely model names from JSON without treating category/source labels as models."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        if isinstance(obj.get("name"), str):
            yield obj["name"]
            return
        if isinstance(obj.get("model"), str):
            yield obj["model"]
        models = obj.get("models")
        if isinstance(models, list):
            for value in models:
                yield from iter_json_model_names(value)
            return
        entries = obj.get("entries")
        if isinstance(entries, list):
            for value in entries:
                yield from iter_json_model_names(value)
            return
        # For unknown JSON, only recurse into list/dict values that look like collections of model records.
        for key in ("roster", "npcs", "peds", "actors"):
            value = obj.get(key)
            if isinstance(value, list):
                for item in value:
                    yield from iter_json_model_names(item)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_json_model_names(value)


def extract_from_text(text: str, source: str) -> list[RosterEntry]:
    names: OrderedDict[str, RosterEntry] = OrderedDict()
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    raw_items: list[str] = []
    if parsed is not None:
        raw_items.extend(iter_json_model_names(parsed))
    raw_items.extend(TEXT_TOKEN_RE.findall(text))
    # Also handle one-name-per-line files where names may not match the regex until normalized.
    raw_items.extend(line.strip() for line in text.splitlines() if line.strip())
    for raw in raw_items:
        name = normalize_name(raw)
        if not name or not looks_spawn_candidate(name, from_binary_scan=False):
            continue
        names.setdefault(name, RosterEntry(name=name, category=category_for(name), source=source))
    return list(names.values())


def load_roster_files(paths: Sequence[Path]) -> list[RosterEntry]:
    merged: OrderedDict[str, RosterEntry] = OrderedDict()
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            print(f"[warn] could not read {path}: {exc}", file=sys.stderr)
            continue
        for entry in extract_from_text(text, str(path)):
            merged.setdefault(entry.name, entry)
    return sorted(merged.values(), key=lambda item: (item.category, item.name))


def read_token(data: bytes, index: int) -> str | None:
    end = index
    limit = min(len(data), index + 128)
    while end < limit and data[end] in STOP_CHARS:
        end += 1
    try:
        return normalize_name(data[index:end].decode("latin1", errors="ignore"))
    except Exception:
        return None


def scan_binary_archive(path: Path, *, max_bytes: int = 0, chunk_size: int = 64 * 1024 * 1024) -> list[RosterEntry]:
    """Fast string scan for names inside a large RPF/archive.

    This does not decode the RPF directory. It only mines visible model/entity strings.
    It is intentionally safe: read-only, streaming, and no archive mutation.
    """
    names: OrderedDict[str, RosterEntry] = OrderedDict()
    prefixes = tuple(prefix.encode("ascii") for prefix in DEFAULT_PREFIXES)
    total = 0
    carry = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            data = carry + chunk
            lower = data.lower()

            pos = 0
            while True:
                idx = lower.find(ENTITY_MARKER, pos)
                if idx < 0:
                    break
                name = read_token(data, idx + len(ENTITY_MARKER))
                if name and looks_spawn_candidate(name, from_binary_scan=True):
                    names.setdefault(name, RosterEntry(name=name, category=category_for(name), source=str(path)))
                pos = idx + len(ENTITY_MARKER)

            for prefix in prefixes:
                pos = 0
                while True:
                    idx = lower.find(prefix, pos)
                    if idx < 0:
                        break
                    if idx == 0 or lower[idx - 1] not in b"abcdefghijklmnopqrstuvwxyz0123456789_":
                        name = read_token(data, idx)
                        if name and looks_spawn_candidate(name, from_binary_scan=True):
                            names.setdefault(name, RosterEntry(name=name, category=category_for(name), source=str(path)))
                    pos = idx + len(prefix)

            carry = data[-256:]
            if max_bytes and total >= max_bytes:
                break
    return sorted(names.values(), key=lambda item: (item.category, item.name))


def save_roster(entries: Sequence[RosterEntry], out_path: Path, *, note: str = "") -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter(entry.category for entry in entries)
    payload = {
        "version": 1,
        "tool": VERSION,
        "note": note,
        "count": len(entries),
        "categories": dict(sorted(counts.items())),
        "models": [asdict(entry) for entry in entries],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def default_source_paths(root: Path) -> list[Path]:
    return [
        root / "data" / "codered" / "npc_model_roster_v1.json",
        root / "scratch" / "codered_npc_roster.json",
        root / "scratch" / "codered_npc_roster_scan.json",
        root / "Smart Menu" / "ImportedFileNames.txt",
        root / "Smart_Menu" / "ImportedFileNames.txt",
        root / "ImportedFileNames.txt",
    ]


def print_entries(entries: Sequence[RosterEntry], *, filter_text: str = "", limit: int = 80) -> None:
    filt = filter_text.lower().strip()
    shown = [entry for entry in entries if not filt or filt in entry.name or filt in entry.category]
    print(f"roster_count={len(entries)} shown={len(shown)} filter={filter_text!r}")
    for idx, entry in enumerate(shown[:limit]):
        print(f"{idx:04d}  {entry.name:<42}  {entry.category}")
    if len(shown) > limit:
        print(f"... {len(shown) - limit} more")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CodeRED NPC/model roster loader and scanner")
    parser.add_argument("--root", default=None, help="Repository/root path. Defaults to the folder above tools/.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List loaded NPC model candidates")
    p_list.add_argument("--filter", default="", help="Case-insensitive name/category filter")
    p_list.add_argument("--limit", type=int, default=80)
    p_list.add_argument("--source", action="append", default=[], help="Extra roster text/JSON source file")

    p_scan = sub.add_parser("scan", help="Scan an RPF/archive/list file and write a roster JSON")
    p_scan.add_argument("archive", help="RPF/archive/text file to scan")
    p_scan.add_argument("--out", default="scratch/codered_npc_roster_scan.json")
    p_scan.add_argument("--max-bytes", type=int, default=0, help="Optional scan byte limit for quick tests")
    p_scan.add_argument("--merge", action="store_true", help="Merge with default roster sources before saving")

    p_validate = sub.add_parser("validate", help="Validate loaded roster sources and report category counts")
    p_validate.add_argument("--source", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else repo_root_from_file()

    if args.command == "list":
        entries = load_roster_files(default_source_paths(root) + [Path(p) for p in args.source])
        print_entries(entries, filter_text=args.filter, limit=args.limit)
        return 0

    if args.command == "scan":
        path = Path(args.archive).resolve()
        if not path.exists():
            print(f"missing archive/source: {path}", file=sys.stderr)
            return 2
        if path.suffix.lower() in {".txt", ".json", ".csv", ".lst"}:
            entries = extract_from_text(path.read_text(encoding="utf-8", errors="ignore"), str(path))
        else:
            entries = scan_binary_archive(path, max_bytes=args.max_bytes)
        if args.merge:
            merged = OrderedDict((entry.name, entry) for entry in load_roster_files(default_source_paths(root)))
            for entry in entries:
                merged.setdefault(entry.name, entry)
            entries = sorted(merged.values(), key=lambda item: (item.category, item.name))
        out = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
        save_roster(entries, out, note=f"scanned {path}")
        print(f"saved {len(entries)} model candidates -> {out}")
        print_entries(entries, limit=40)
        return 0

    if args.command == "validate":
        entries = load_roster_files(default_source_paths(root) + [Path(p) for p in args.source])
        counts = Counter(entry.category for entry in entries)
        print(f"loaded={len(entries)}")
        for category, count in sorted(counts.items()):
            print(f"{category}: {count}")
        return 0 if entries else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
