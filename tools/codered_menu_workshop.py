#!/usr/bin/env python3
"""Code RED Menu Workshop.

Builds validated runtime menu data from declarative JSON specs. This tool is a
preflight lane: it resolves actors/resources/actions, writes proof reports, and
marks unsafe entries before the ASI ever tries to execute them.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTOR_MAP = REPO_ROOT / "data" / "codered" / "actor_enum_map.csv"
DEFAULT_ACTIONS = REPO_ROOT / "data" / "codered" / "ai_behavior_actions.csv"
DEFAULT_RUNTIME_DIR = REPO_ROOT / "data" / "codered" / "menus" / "generated"
DEFAULT_OUT = REPO_ROOT / "logs" / "menu_workshop"
SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}
TEXT_RESOURCE_EXTS = {".xml", ".txt", ".csv", ".json", ".ini", ".strtbl"}
VEHICLE_CATEGORY_TOKENS = ("vehicle", "wagon", "coach", "cart", "canoe", "raft", "train", "truck", "car")
SPECIAL_CATEGORY_TOKENS = ("rideable", "animal", "mount", "horse", "mule", "buffalo", "object", "prop")
SUPPORTED_PED_ACTIONS = {"spawn_actor", "spawn_ped"}
RESOURCE_ACTIONS = {"load_or_probe_script", "probe_script", "script_resource_probe", "probe_resource"}
VEHICLE_ACTIONS = {"spawn_vehicle_or_object", "spawn_vehicle", "spawn_object"}


@dataclass
class ActorRecord:
    label: str
    actor_enum: str
    category: str = ""
    source: str = ""
    aliases: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def enum_int(self) -> int | None:
        return parse_int(self.actor_enum)


@dataclass
class ActionRecord:
    action: str
    label: str
    category: str
    enabled: bool
    notes: str = ""


@dataclass
class ResourceRecord:
    path: str
    source: str
    extension: str = ""


@dataclass
class MenuItemResult:
    section: str
    label: str
    action: str
    lane: str
    status: str
    enabled: bool
    blocked_reason: str = ""
    warnings: list[str] = field(default_factory=list)
    actor_label: str = ""
    actor_enum: int | None = None
    actor_enum_hex: str = ""
    actor_category: str = ""
    actor_source: str = ""
    script: str = ""
    resource: str = ""
    resolved_resource: str = ""
    runtime_entry: dict[str, Any] = field(default_factory=dict)


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError:
        return None


def normalize_key(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", value.strip().lower())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "menu"


def load_actor_map(path: Path) -> tuple[dict[str, ActorRecord], list[ActorRecord]]:
    records: list[ActorRecord] = []
    lookup: dict[str, ActorRecord] = {}
    if not path.exists():
        return lookup, records
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        filtered = (line for line in fh if not line.lstrip().startswith("#"))
        reader = csv.DictReader(filtered)
        for row in reader:
            label = (row.get("label") or "").strip()
            if not label:
                continue
            aliases = [part.strip() for part in (row.get("aliases") or "").split("|") if part.strip()]
            record = ActorRecord(
                label=label,
                actor_enum=(row.get("actor_enum") or "").strip(),
                category=(row.get("category") or "").strip(),
                source=(row.get("source") or "").strip(),
                aliases=aliases,
                notes=(row.get("notes") or "").strip(),
            )
            records.append(record)
            for key in [label, *aliases]:
                lookup.setdefault(normalize_key(key), record)
    return lookup, records


def load_actions(path: Path) -> dict[str, ActionRecord]:
    actions: dict[str, ActionRecord] = {}
    if not path.exists():
        return actions
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            action = (row.get("action") or "").strip()
            if not action:
                continue
            actions[action] = ActionRecord(
                action=action,
                label=(row.get("label") or action).strip(),
                category=(row.get("category") or "").strip(),
                enabled=(row.get("enabled") or "").strip().lower() in {"1", "true", "yes", "on"},
                notes=(row.get("notes") or "").strip(),
            )
    return actions


def load_resource_index(paths: Iterable[Path]) -> dict[str, ResourceRecord]:
    resources: dict[str, ResourceRecord] = {}
    for path in paths:
        if not path.exists():
            continue
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            rows = data.get("entries") if isinstance(data, dict) else data
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                value = str(row.get("path") or row.get("archive_path") or row.get("output") or "").replace("\\", "/")
                if value:
                    add_resource(resources, value, str(path))
        else:
            try:
                with path.open("r", newline="", encoding="utf-8-sig") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        value = str(row.get("path") or row.get("archive_path") or row.get("output") or "").replace("\\", "/")
                        if value:
                            add_resource(resources, value, str(path))
            except Exception:
                continue
    return resources


def add_resource(resources: dict[str, ResourceRecord], value: str, source: str) -> None:
    clean = value.strip().replace("\\", "/")
    if not clean:
        return
    record = ResourceRecord(path=clean, source=source, extension=Path(clean).suffix.lower())
    resources.setdefault(clean.lower(), record)
    resources.setdefault(Path(clean).name.lower(), record)
    if clean.startswith("root/"):
        resources.setdefault(clean[5:].lower(), record)


def add_resource_roots(resources: dict[str, ResourceRecord], roots: Iterable[Path]) -> None:
    for root in roots:
        if not root.exists():
            continue
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in files:
            try:
                rel = path.relative_to(root).as_posix() if root.is_dir() else path.name
            except ValueError:
                rel = path.name
            add_resource(resources, rel, str(root))
            add_resource(resources, path.as_posix(), str(root))


def resolve_actor(value: Any, actor_lookup: dict[str, ActorRecord]) -> ActorRecord | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "|" in text:
        label, enum_text = [part.strip() for part in text.split("|", 1)]
        if parse_int(enum_text) is not None:
            return ActorRecord(label=label or text, actor_enum=enum_text, category="inline", source="menu_inline")
    direct = parse_int(text)
    if direct is not None:
        return ActorRecord(label=text, actor_enum=str(direct), category="inline", source="menu_inline")
    return actor_lookup.get(normalize_key(text))


def actor_lane(record: ActorRecord | None) -> str:
    if record is None:
        return "actor"
    text = f"{record.category} {record.label}".lower()
    if any(token in text for token in VEHICLE_CATEGORY_TOKENS):
        return "vehicle_object"
    if any(token in text for token in SPECIAL_CATEGORY_TOKENS):
        return "special_case_actor"
    return "normal_ped"


def resolve_resource(value: str, resources: dict[str, ResourceRecord]) -> ResourceRecord | None:
    clean = value.strip().replace("\\", "/")
    candidates = [clean.lower(), Path(clean).name.lower()]
    if clean.startswith("root/"):
        candidates.append(clean[5:].lower())
    for key in candidates:
        if key in resources:
            return resources[key]
    local = (REPO_ROOT / clean).resolve()
    try:
        if local.exists():
            return ResourceRecord(path=str(local), source="repo_relative", extension=local.suffix.lower())
    except OSError:
        pass
    return None


def classify_item(item: dict[str, Any], section: str, actor_lookup: dict[str, ActorRecord], actions: dict[str, ActionRecord], resources: dict[str, ResourceRecord]) -> MenuItemResult:
    label = str(item.get("label") or item.get("actor") or item.get("script") or item.get("resource") or "Untitled").strip()
    action = str(item.get("action") or "").strip()
    warnings: list[str] = []
    if not action:
        return MenuItemResult(section, label, action, "unknown", "blocked", False, "missing_action")

    action_record = actions.get(action)
    if action_record and not action_record.enabled:
        warnings.append(f"action disabled in ai_behavior_actions.csv: {action_record.notes}")

    actor_value = item.get("actor")
    script_value = str(item.get("script") or "").strip().replace("\\", "/")
    resource_value = str(item.get("resource") or script_value or "").strip().replace("\\", "/")

    if actor_value:
        actor = resolve_actor(actor_value, actor_lookup)
        lane = actor_lane(actor)
        if actor is None or actor.enum_int is None:
            return MenuItemResult(section, label, action, lane, "blocked", False, "actor_enum_missing", warnings, actor_label=str(actor_value))
        enum_int = actor.enum_int
        actor_hex = f"0x{enum_int:08X}"
        blocked_reason = ""
        status = "ready"
        enabled = True
        if lane == "normal_ped" and action not in SUPPORTED_PED_ACTIONS:
            status = "blocked"
            enabled = False
            blocked_reason = "ped_action_not_supported"
        elif lane in {"vehicle_object", "special_case_actor"}:
            if action in VEHICLE_ACTIONS:
                status = "blocked"
                enabled = False
                blocked_reason = "native_mapping_unproven_for_vehicle_or_special_actor"
            elif action in SUPPORTED_PED_ACTIONS:
                status = "blocked"
                enabled = False
                blocked_reason = "raw_actor_spawn_not_allowed_for_vehicle_or_special_actor"
            else:
                status = "blocked"
                enabled = False
                blocked_reason = "actor_lane_action_unknown"
        if action_record and not action_record.enabled:
            status = "blocked"
            enabled = False
            blocked_reason = blocked_reason or "action_disabled"
        runtime = {
            "label": label,
            "section": section,
            "action": action,
            "lane": lane,
            "enabled": enabled,
            "status": status,
            "actor": actor.label,
            "actor_enum": enum_int,
            "actor_enum_hex": actor_hex,
            "actor_category": actor.category,
        }
        if blocked_reason:
            runtime["blocked_reason"] = blocked_reason
        return MenuItemResult(
            section=section,
            label=label,
            action=action,
            lane=lane,
            status=status,
            enabled=enabled,
            blocked_reason=blocked_reason,
            warnings=warnings,
            actor_label=actor.label,
            actor_enum=enum_int,
            actor_enum_hex=actor_hex,
            actor_category=actor.category,
            actor_source=actor.source,
            runtime_entry=runtime,
        )

    if script_value or resource_value:
        resource = resolve_resource(resource_value, resources)
        ext = Path(resource_value).suffix.lower()
        lane = "script_resource" if ext in SCRIPT_EXTS or action in RESOURCE_ACTIONS else "resource_probe"
        status = "ready" if resource else "blocked"
        enabled = bool(resource)
        blocked_reason = "" if resource else "resource_path_not_found"
        if action not in RESOURCE_ACTIONS:
            status = "blocked"
            enabled = False
            blocked_reason = "resource_action_not_supported"
        runtime = {
            "label": label,
            "section": section,
            "action": action,
            "lane": lane,
            "enabled": enabled,
            "status": status,
            "script": script_value,
            "resource": resource_value,
            "resolved_resource": resource.path if resource else "",
        }
        if blocked_reason:
            runtime["blocked_reason"] = blocked_reason
        return MenuItemResult(
            section=section,
            label=label,
            action=action,
            lane=lane,
            status=status,
            enabled=enabled,
            blocked_reason=blocked_reason,
            warnings=warnings,
            script=script_value,
            resource=resource_value,
            resolved_resource=resource.path if resource else "",
            runtime_entry=runtime,
        )

    return MenuItemResult(section, label, action, "unknown", "blocked", False, "missing_actor_or_resource", warnings)


def validate_project(project: Path, actor_map: Path, actions_path: Path, resource_indexes: list[Path], resource_roots: list[Path]) -> tuple[dict[str, Any], list[MenuItemResult]]:
    spec = json.loads(project.read_text(encoding="utf-8"))
    actor_lookup, actor_records = load_actor_map(actor_map)
    actions = load_actions(actions_path)
    resources = load_resource_index(resource_indexes)
    add_resource_roots(resources, resource_roots)

    results: list[MenuItemResult] = []
    for section in spec.get("sections", []):
        section_name = str(section.get("name") or "Menu").strip()
        for item in section.get("items", []):
            if isinstance(item, dict):
                results.append(classify_item(item, section_name, actor_lookup, actions, resources))

    blocked = [item for item in results if item.status == "blocked"]
    proof = {
        "menu": str(project),
        "title": spec.get("title") or project.stem,
        "hotkey": spec.get("hotkey", ""),
        "items_total": len(results),
        "items_resolved": sum(1 for item in results if item.status in {"ready", "untested"}),
        "items_blocked": len(blocked),
        "blocked_reasons": dict(Counter(item.blocked_reason for item in blocked)),
        "spawn_actions": [item.runtime_entry for item in results if item.actor_enum is not None],
        "script_actions": [item.runtime_entry for item in results if item.script or item.resource],
        "install_files": [],
        "actor_map": str(actor_map),
        "actor_map_records": len(actor_records),
        "action_map": str(actions_path),
        "resource_index_count": len(resources),
    }
    return {"spec": spec, "proof": proof}, results


def runtime_payload(spec: dict[str, Any], results: list[MenuItemResult]) -> dict[str, Any]:
    sections: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        sections.setdefault(item.section, []).append(item.runtime_entry or asdict(item))
    return {
        "schema": "codered.menu.runtime.v1",
        "title": spec.get("title") or "Code RED Menu",
        "hotkey": spec.get("hotkey", ""),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sections": [{"name": name, "items": items} for name, items in sections.items()],
    }


def write_outputs(project: Path, out_dir: Path, runtime_dir: Path, emit_runtime: bool, package: bool, validation: dict[str, Any], results: list[MenuItemResult]) -> dict[str, Any]:
    spec = validation["spec"]
    proof = validation["proof"]
    menu_id = slugify(str(spec.get("id") or spec.get("title") or project.stem))
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_dir / f"{menu_id}.menu.json"
    package_file = out_dir / "install_package" / "data" / "codered" / "menus" / f"{menu_id}.menu.json"

    plan = {
        "schema": "codered.menu.plan.v1",
        "project": str(project),
        "runtime_file": str(runtime_file) if emit_runtime else "",
        "items": [asdict(item) for item in results],
    }
    (out_dir / "menu_workshop_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (out_dir / "menu_workshop_proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    with (out_dir / "menu_workshop_items.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["section", "label", "action", "lane", "status", "enabled", "blocked_reason", "actor_label", "actor_enum", "actor_enum_hex", "actor_category", "script", "resource", "resolved_resource", "warnings"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for item in results:
            row = asdict(item)
            row["warnings"] = "; ".join(item.warnings)
            writer.writerow({field: row.get(field, "") for field in fields})

    safe_lines = ["# Code RED Menu Workshop safe/ready roster", f"# Source: {project}"]
    blocked_lines = ["# Code RED Menu Workshop blocked/unsupported roster", f"# Source: {project}"]
    for item in results:
        line = f"{item.section}|{item.label}|{item.action}|{item.actor_label or item.script or item.resource}|{item.blocked_reason}"
        if item.status == "ready":
            safe_lines.append(line)
        else:
            blocked_lines.append(line)
    (out_dir / "safe_roster.txt").write_text("\n".join(safe_lines) + "\n", encoding="utf-8")
    (out_dir / "unsupported_roster.txt").write_text("\n".join(blocked_lines) + "\n", encoding="utf-8")

    if emit_runtime:
        payload = runtime_payload(spec, results)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        proof["install_files"].append(str(runtime_file))
        if package:
            package_file.parent.mkdir(parents=True, exist_ok=True)
            package_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            proof["install_files"].append(str(package_file))
            (out_dir / "install_package" / "INSTALL_README.txt").write_text(
                "Copy data/codered/menus beside the runtime ASI install only after reviewing menu_workshop_proof.json.\n",
                encoding="utf-8",
            )
        (out_dir / "menu_workshop_proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")

    report_lines = [
        "# Code RED Menu Workshop Report",
        "",
        f"Project: `{project}`",
        f"Title: `{proof['title']}`",
        f"Items total: `{proof['items_total']}`",
        f"Items resolved: `{proof['items_resolved']}`",
        f"Items blocked: `{proof['items_blocked']}`",
        "",
        "## Blocked reasons",
    ]
    for reason, count in proof["blocked_reasons"].items():
        report_lines.append(f"- {reason}: {count}")
    report_lines.extend(["", "## Items"])
    for item in results:
        suffix = f" blocked={item.blocked_reason}" if item.blocked_reason else ""
        report_lines.append(f"- `{item.status}` [{item.lane}] {item.section} / {item.label} -> {item.action}{suffix}")
    (out_dir / "menu_workshop_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build validated Code RED runtime menu data from JSON specs.")
    parser.add_argument("--project", type=Path, required=True, help="Menu JSON/spec file.")
    parser.add_argument("--actor-map", type=Path, default=DEFAULT_ACTOR_MAP)
    parser.add_argument("--actions", type=Path, default=DEFAULT_ACTIONS)
    parser.add_argument("--resource-index", action="append", type=Path, default=[], help="CSV/JSON inventory with path/archive_path/output columns. Can be repeated.")
    parser.add_argument("--resource-root", action="append", type=Path, default=[], help="Extracted resource folder to resolve script/resource paths. Can be repeated.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--validate", action="store_true", help="Validate the project. Validation also runs when emitting runtime data.")
    parser.add_argument("--emit-runtime", action="store_true", help="Write runtime menu JSON under the runtime menu directory.")
    parser.add_argument("--package", action="store_true", help="Also stage an install package copy under the output directory.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when any item is blocked.")
    args = parser.parse_args(argv)

    validation, results = validate_project(args.project, args.actor_map, args.actions, args.resource_index, args.resource_root)
    proof = write_outputs(args.project, args.out, args.runtime_dir, args.emit_runtime, args.package, validation, results)
    print(json.dumps(proof, indent=2))
    if args.strict and proof["items_blocked"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
