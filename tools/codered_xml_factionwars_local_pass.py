#!/usr/bin/env python3
"""Code RED XML/resource-first faction wars local pass.

Local-only tool. No GitHub, no script compiling, no ASI/menu spawning.

It scans a Code_RED workspace for loose non-compiled files, stages relevant XML
and text resources, and prepares conservative patched copies for:
- factionrelations / faction relation resources
- town activity / placement globals, excluding MacFarlane's Ranch
- behavior/template/tune pressure XML
- loose non-compiled content/resource files

It never mutates source files. It writes everything under:
  scratch/faction_wars/xml_first_pass
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

VERSION = "1.0.0-local-xml-first-pass"

PATCHABLE_SUFFIXES = {".xml", ".ini", ".cfg", ".txt", ".csv", ".json", ".md"}
NEVER_PATCH_SUFFIXES = {".rpf", ".wsc", ".xsc", ".sco", ".ysc", ".csc", ".exe", ".dll", ".asi", ".zip"}
SKIP_DIRS = {
    ".git", ".vs", ".vscode", "__pycache__", "build", "dist", "x64", "x86", "debug", "release",
    "node_modules", ".pytest_cache", "codered_backups", "staged_resources", "patched_resources",
}

TOWN_TARGETS = (
    "blackwater", "armadillo", "thieves", "thieves landing", "tumbleweed", "chuparosa", "escalera",
    "manzanita", "plainview", "rathskeller", "ridgewood", "rio bravo", "gaptooth", "fort mercer",
    "henningan", "new austin", "nuevo paraiso", "mexico", "tall trees", "landing",
)
MACFARLANE_TERMS = ("macfarlane", "macfarlanes", "macfarlane's", "macfarlanesranch", "mcfarlane")

CATEGORY_TERMS = {
    "factionrelations": (
        "factionrelations", "faction_relations", "factionrelation", "faction relation", "faction", "relation",
        "lawman", "lawmen", "sheriff", "marshal", "gang", "bandit", "bandito", "criminal", "enemy", "hostile",
    ),
    "town_activity": (
        "placementglobals", "population", "refgroup", "town", "ambient", "encounter", "spawn", "density",
        "active", "enabled", "chance", "frequency", "blackwater", "armadillo", "thieves", "landing", "tumbleweed",
    ),
    "behavior_templates": (
        "template_base_human", "template_player", "components", "actions_templates", "behavior", "behaviour",
        "combat", "awareness", "hostile", "lasso", "hogtie", "weapon", "dog", "sheriff", "npc",
    ),
    "content_loose_noncompiled": (
        "content/", "content\\", "scripting", "gringo", "commongringos", "gringobrain", "vehicle_generator",
        "holdup", "crime", "patrol", "posse", "camp", "hideout", "event",
    ),
    "tune_xml": (
        "tune", "template", "lasso", "sheriff", "npc", "dog", "weapon", "population", "spawns", "max render",
    ),
}

NUMERIC_ATTR_RE = re.compile(r'(?P<name>\b(?:chance|density|frequency|probability|weight|activeChance|spawnChance|population|populationDensity|max|maxCount|min|minCount|radius|range)\b)\s*=\s*"(?P<value>-?\d+(?:\.\d+)?)"', re.IGNORECASE)
VALUE_TAG_RE = re.compile(r'(?P<open><(?P<name>[^>\s/]*(?:chance|density|frequency|probability|weight|population|maxcount|mincount|max|min|active|enabled|disable|disabled)[^>\s/]*)\s+value=")(?P<value>[^"<>]+)(?P<close>"\s*/?>)', re.IGNORECASE)
BOOL_ATTR_RE = re.compile(r'(?P<name>\b(?:active|enabled|enable|disabled|disable)\b)\s*=\s*"(?P<value>true|false|0|1)"', re.IGNORECASE)


@dataclass
class ScanHit:
    path: str
    category: str
    score: int
    size: int
    sha1: str
    staged_path: str = ""
    patched_path: str = ""
    notes: list[str] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "main.py").exists() or (candidate / "python_workbench.py").exists() or (candidate / "research").exists():
            return candidate
    return here


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_read(path: Path, limit: int = 5_000_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        low_current = current_path.as_posix().lower()
        if "/scratch/faction_wars/xml_first_pass/" in low_current:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
        for name in filenames:
            path = current_path / name
            suffix = path.suffix.lower()
            if suffix in NEVER_PATCH_SUFFIXES:
                continue
            if suffix not in PATCHABLE_SUFFIXES:
                continue
            yield path


def classify(path: Path, root: Path, text: str) -> tuple[str, int, list[str]] | None:
    rel = rel_to(path, root).replace("\\", "/")
    blob = (rel + "\n" + text[:25000]).lower()
    notes: list[str] = []
    best_category = ""
    best_score = 0
    for category, terms in CATEGORY_TERMS.items():
        score = 0
        for term in terms:
            c = blob.count(term.lower())
            if c:
                score += c
        if category == "factionrelations" and "faction" in blob and "relation" in blob:
            score += 100
        if category == "town_activity" and any(t in blob for t in TOWN_TARGETS):
            score += 75
        if category == "behavior_templates" and path.suffix.lower() == ".xml":
            score += 25
        if category == "content_loose_noncompiled" and ("content" in rel.lower() or "scripting" in blob):
            score += 30
        if score > best_score:
            best_score = score
            best_category = category
    if best_score <= 2:
        return None
    if any(term in blob for term in MACFARLANE_TERMS):
        notes.append("contains MacFarlane term; town activation patcher will skip MacFarlane lines")
    return best_category, best_score, notes


def patch_town_activity_text(text: str) -> tuple[str, list[str]]:
    """Conservative line-based town activity patch.

    Only touches lines containing a target town and not MacFarlane. It does not
    rewrite structure or invent new entries.
    """
    changes: list[str] = []
    out_lines: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        is_target = any(t in low for t in TOWN_TARGETS) and not any(m in low for m in MACFARLANE_TERMS)
        new_line = line
        if is_target:
            def bool_sub(m: re.Match) -> str:
                name = m.group("name")
                value = m.group("value").lower()
                low_name = name.lower()
                if low_name in {"active", "enabled", "enable"} and value in {"false", "0"}:
                    changes.append(f"L{line_no}: {name}=true")
                    return f'{name}="true"'
                if low_name in {"disabled", "disable"} and value in {"true", "1"}:
                    changes.append(f"L{line_no}: {name}=false")
                    return f'{name}="false"'
                return m.group(0)
            new_line = BOOL_ATTR_RE.sub(bool_sub, new_line)

            def numeric_sub(m: re.Match) -> str:
                name = m.group("name")
                raw = m.group("value")
                try:
                    value = float(raw)
                except ValueError:
                    return m.group(0)
                lname = name.lower()
                new_value = value
                if any(k in lname for k in ("chance", "probability", "frequency", "weight")):
                    new_value = min(max(value * 1.35, 0.25 if value <= 0 else value), 1.0 if value <= 1.0 else value * 1.35)
                elif any(k in lname for k in ("density", "population", "max", "count")):
                    new_value = max(value + 1, value * 1.25)
                elif any(k in lname for k in ("radius", "range")):
                    new_value = value * 1.10
                if abs(new_value - value) > 1e-9:
                    formatted = f"{new_value:.3f}".rstrip("0").rstrip(".")
                    changes.append(f"L{line_no}: {name} {raw} -> {formatted}")
                    return f'{name}="{formatted}"'
                return m.group(0)
            new_line = NUMERIC_ATTR_RE.sub(numeric_sub, new_line)
        out_lines.append(new_line)
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), changes


def patch_behavior_template_text(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    out_lines: list[str] = []
    pressure_terms = ("awareness", "hostile", "combat", "lasso", "hogtie", "weapon", "dog", "threat", "range", "radius")
    for line_no, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        new_line = line
        if any(t in low for t in pressure_terms):
            def value_sub(m: re.Match) -> str:
                name = m.group("name")
                raw = m.group("value")
                low_name = name.lower()
                if raw.lower() in {"true", "false"}:
                    return m.group(0)
                try:
                    value = float(raw)
                except ValueError:
                    return m.group(0)
                if any(k in low_name for k in ("range", "radius", "awareness", "score", "weight", "chance")):
                    new_value = value * 1.15 if value > 0 else value
                else:
                    new_value = value
                if abs(new_value - value) > 1e-9:
                    formatted = f"{new_value:.3f}".rstrip("0").rstrip(".")
                    changes.append(f"L{line_no}: {name} value {raw} -> {formatted}")
                    return f"{m.group('open')}{formatted}{m.group('close')}"
                return m.group(0)
            new_line = VALUE_TAG_RE.sub(value_sub, new_line)
        out_lines.append(new_line)
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), changes


def patch_factionrelations_text(text: str) -> tuple[str, list[str]]:
    """Prepare a safe factionrelations candidate.

    Without the exact schema, do not invent entries. This converts existing law-vs-gang
    relation lines that already declare an inactive/neutral boolean into active/hostile
    where obvious. More complex relation values are reported for manual review.
    """
    changes: list[str] = []
    out_lines: list[str] = []
    law_terms = ("law", "sheriff", "marshal", "deputy")
    gang_terms = ("gang", "bandit", "bandito", "criminal", "outlaw", "rustler")
    for line_no, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        new_line = line
        if any(l in low for l in law_terms) and any(g in low for g in gang_terms):
            old = new_line
            new_line = re.sub(r'(hostile\s*=\s*")(?:false|0)(")', r'\1true\2', new_line, flags=re.IGNORECASE)
            new_line = re.sub(r'(enemy\s*=\s*")(?:false|0)(")', r'\1true\2', new_line, flags=re.IGNORECASE)
            new_line = re.sub(r'(relation\s*=\s*")(?:neutral|friendly)(")', r'\1hostile\2', new_line, flags=re.IGNORECASE)
            new_line = re.sub(r'(attitude\s*=\s*")(?:neutral|friendly)(")', r'\1hostile\2', new_line, flags=re.IGNORECASE)
            if new_line != old:
                changes.append(f"L{line_no}: law-vs-gang relation hardened")
            else:
                changes.append(f"L{line_no}: law-vs-gang relation candidate needs manual schema review")
        out_lines.append(new_line)
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), changes


def patch_candidate(category: str, text: str) -> tuple[str, list[str]]:
    if category == "town_activity":
        return patch_town_activity_text(text)
    if category == "behavior_templates":
        return patch_behavior_template_text(text)
    if category == "factionrelations":
        return patch_factionrelations_text(text)
    return text, []


def scan_and_stage(root: Path, limit_per_category: int = 50) -> tuple[list[ScanHit], dict[str, int]]:
    stage_root = root / "scratch" / "faction_wars" / "xml_first_pass"
    staged_root = stage_root / "staged_originals"
    patched_root = stage_root / "patched_candidates"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    staged_root.mkdir(parents=True, exist_ok=True)
    patched_root.mkdir(parents=True, exist_ok=True)

    hits_by_cat: dict[str, list[ScanHit]] = {cat: [] for cat in CATEGORY_TERMS}
    scanned = 0
    for path in iter_files(root):
        scanned += 1
        text = safe_read(path)
        if not text:
            continue
        classified = classify(path, root, text)
        if not classified:
            continue
        category, score, notes = classified
        rel = rel_to(path, root)
        hit = ScanHit(path=rel, category=category, score=score, size=path.stat().st_size, sha1=sha1_file(path), notes=notes)
        hits_by_cat[category].append(hit)

    selected: list[ScanHit] = []
    for cat, hits in hits_by_cat.items():
        hits.sort(key=lambda h: (h.score, -h.size, h.path), reverse=True)
        selected.extend(hits[:limit_per_category])

    for hit in selected:
        src = root / hit.path
        staged = staged_root / hit.path
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, staged)
        hit.staged_path = rel_to(staged, root)
        text = safe_read(src)
        patched_text, changes = patch_candidate(hit.category, text)
        if changes and patched_text != text:
            patched = patched_root / hit.path
            patched.parent.mkdir(parents=True, exist_ok=True)
            patched.write_text(patched_text, encoding="utf-8")
            hit.patched_path = rel_to(patched, root)
            hit.notes.extend(changes[:50])
        elif changes:
            hit.notes.extend(changes[:50])

    counts = {cat: len(hits_by_cat[cat]) for cat in hits_by_cat}
    counts["scanned_files"] = scanned
    counts["selected_files"] = len(selected)
    return selected, counts


def write_outputs(root: Path, hits: Sequence[ScanHit], counts: dict[str, int]) -> dict[str, str]:
    out_root = root / "scratch" / "faction_wars" / "xml_first_pass"
    reports = out_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    manifest_json = reports / "xml_first_pass_manifest.json"
    manifest_csv = reports / "xml_first_pass_manifest.csv"
    plan_md = out_root / "XML_FIRST_PASS_PLAN.md"
    faction_md = out_root / "FACTIONRELATIONS_FIRST.md"
    content_md = out_root / "CONTENT_LOOSE_NONCOMPILED_FIRST.md"

    manifest_json.write_text(json.dumps({"version": VERSION, "generated_utc": utc_now(), "counts": counts, "hits": [asdict(h) for h in hits]}, indent=2), encoding="utf-8")
    with manifest_csv.open("w", encoding="utf-8", newline="") as f:
        fields = ["category", "score", "path", "staged_path", "patched_path", "size", "sha1", "notes"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for h in sorted(hits, key=lambda x: (x.category, -x.score, x.path)):
            d = asdict(h)
            d["notes"] = " | ".join(h.notes[:20])
            w.writerow({k: d.get(k, "") for k in fields})

    def rows_for(cat: str) -> list[ScanHit]:
        return sorted([h for h in hits if h.category == cat], key=lambda x: (-x.score, x.path))

    lines = [
        "# Code RED XML-First Faction Wars Pass",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "## Goal",
        "",
        "Make the game more active through loose XML/resource edits first. All towns are eligible except MacFarlane's Ranch. Scripts, SC-CL, and ASI/menu spawning stay parked.",
        "",
        "## Counts",
        "",
    ]
    for k, v in counts.items():
        lines.append(f"- {k}: `{v}`")
    lines.extend([
        "",
        "## Priority order",
        "",
        "1. Faction relations: harden existing law-vs-gang/bandit/criminal relationships where an existing loose file supports it.",
        "2. Town activity / placement globals: activate/increase all towns except MacFarlane's Ranch.",
        "3. Behavior/templates: increase awareness/combat/hostile pressure conservatively.",
        "4. Loose non-compiled content: gringo/event/camp/holdup resources only after review.",
        "",
        "## Top staged candidates",
        "",
        "| Category | Score | Source | Patched candidate | Notes |",
        "|---|---:|---|---|---|",
    ])
    for h in sorted(hits, key=lambda x: (-x.score, x.category, x.path))[:80]:
        lines.append(f"| {h.category} | {h.score} | `{h.path}` | `{h.patched_path}` | {'; '.join(h.notes[:3])} |")
    plan_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    f_lines = ["# Factionrelations First", "", "Open these staged files first. If `patched_path` is blank, the schema needs manual review before changing.", "", "| Score | Source | Patched candidate | Notes |", "|---:|---|---|---|"]
    for h in rows_for("factionrelations"):
        f_lines.append(f"| {h.score} | `{h.path}` | `{h.patched_path}` | {'; '.join(h.notes[:5])} |")
    faction_md.write_text("\n".join(f_lines) + "\n", encoding="utf-8")

    c_lines = ["# Loose Non-Compiled Content First", "", "These are loose content/script-like resources that are not compiled script binaries. Review before patching.", "", "| Category | Score | Source | Staged | Patched |", "|---|---:|---|---|---|"]
    for h in rows_for("content_loose_noncompiled") + rows_for("town_activity"):
        c_lines.append(f"| {h.category} | {h.score} | `{h.path}` | `{h.staged_path}` | `{h.patched_path}` |")
    content_md.write_text("\n".join(c_lines) + "\n", encoding="utf-8")

    return {
        "stage_root": rel_to(out_root, root),
        "plan": rel_to(plan_md, root),
        "factionrelations_first": rel_to(faction_md, root),
        "content_loose_noncompiled_first": rel_to(content_md, root),
        "manifest_json": rel_to(manifest_json, root),
        "manifest_csv": rel_to(manifest_csv, root),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Code RED local XML/resource-first faction wars pass")
    p.add_argument("--root", type=Path, default=None, help="Code_RED root. Default: current folder or nearest repo-like parent.")
    p.add_argument("--limit-per-category", type=int, default=50)
    p.add_argument("--json", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = (args.root.resolve() if args.root else find_root())
    hits, counts = scan_and_stage(root, limit_per_category=max(1, args.limit_per_category))
    outputs = write_outputs(root, hits, counts)
    summary = {"version": VERSION, "root": str(root), "counts": counts, "outputs": outputs}
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("# Code RED XML-first Faction Wars local pass")
        print("Root:", root)
        for k, v in counts.items():
            print(f"{k}: {v}")
        print("Review first:", outputs["factionrelations_first"])
        print("Then:", outputs["plan"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
