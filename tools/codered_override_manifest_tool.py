#!/usr/bin/env python3
"""Code RED override manifest proof tool.

Creates, edits, and validates CodeRED_Overrides/manifest.json without enabling live file redirects.
Pass 0.6 is proof-only and keeps redirect_adapter.enabled = false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

VERSION = "0.6.0-override-editor-validator-proof"
ALLOWED_EXTENSIONS = {".xtbl", ".xml", ".txt", ".strtbl", ".wsc", ".json", ".ini", ".cfg"}
DENIED_EXTENSIONS = {".exe", ".dll", ".asi", ".bat", ".cmd", ".ps1"}
PRESETS = {
    "tune-refgroup": "content/tune/refgroups/{name}.xtbl",
    "tune-table": "content/tune/{name}.xtbl",
    "string-table": "content/strings/{name}.strtbl",
    "script-source": "content/scripts/{name}.wsc",
    "config-json": "content/config/{name}.json",
    "text-note": "content/notes/{name}.txt",
}


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def override_root(game_root: Path) -> Path:
    return game_root / "CodeRED_Overrides"


def manifest_path(game_root: Path) -> Path:
    return override_root(game_root) / "manifest.json"


def reports_root(game_root: Path) -> Path:
    return game_root / "CodeRED_ASI_Logs"


def report_path(game_root: Path) -> Path:
    return reports_root(game_root) / "override_manifest_validation_report.json"


def normalize_rel(path: str | Path) -> str:
    return Path(path).as_posix().replace("//", "/").lstrip("/")


def is_safe_rel(rel: str) -> bool:
    if ".." in Path(rel).parts:
        return False
    if rel.startswith("/") or rel.startswith("\\"):
        return False
    if ":" in rel:
        return False
    return True


def rule_id(virtual_path: str) -> str:
    return hashlib.sha1(virtual_path.encode("utf-8")).hexdigest()[:12]


def base_manifest() -> dict[str, Any]:
    return {
        "version": VERSION,
        "generated_utc": utc_now(),
        "updated_utc": utc_now(),
        "enabled": False,
        "mode": "proof_only",
        "file_redirects_enabled": False,
        "archive_writes_enabled": False,
        "allow_extensions": sorted(ALLOWED_EXTENSIONS),
        "deny_extensions": sorted(DENIED_EXTENSIONS),
        "redirect_adapter": {
            "enabled": False,
            "mode": "disabled_proof_only",
            "adapter": "none",
            "notes": "Pass 0.6 validates rules only. No CreateFile/RPF/archive interception is enabled.",
        },
        "presets": PRESETS,
        "rules": [],
        "rejected": [],
        "summary": {"allowed_rules": 0, "rejected_rules": 0},
    }


def load_manifest(game_root: Path) -> dict[str, Any]:
    path = manifest_path(game_root)
    if not path.exists():
        return base_manifest()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return base_manifest()
    merged = base_manifest()
    merged.update(payload)
    merged["redirect_adapter"] = {**base_manifest()["redirect_adapter"], **payload.get("redirect_adapter", {})}
    merged["presets"] = {**PRESETS, **payload.get("presets", {})}
    return merged


def save_manifest(game_root: Path, payload: dict[str, Any]) -> Path:
    path = manifest_path(game_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["version"] = VERSION
    payload["updated_utc"] = utc_now()
    payload["enabled"] = False
    payload["mode"] = "proof_only"
    payload["file_redirects_enabled"] = False
    payload["archive_writes_enabled"] = False
    payload["redirect_adapter"] = {**base_manifest()["redirect_adapter"], **payload.get("redirect_adapter", {})}
    payload["redirect_adapter"]["enabled"] = False
    payload["redirect_adapter"]["mode"] = "disabled_proof_only"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def validate_rule(game_root: Path, rule: dict[str, Any]) -> dict[str, Any]:
    virtual_path = normalize_rel(str(rule.get("virtual_path", "")))
    override_path_value = str(rule.get("override_path", ""))
    override_path = game_root / override_path_value if override_path_value else override_root(game_root) / virtual_path
    ext = Path(virtual_path).suffix.lower() or Path(override_path).suffix.lower()
    errors: list[str] = []
    warnings: list[str] = []

    if not virtual_path:
        errors.append("missing_virtual_path")
    if not is_safe_rel(virtual_path):
        errors.append("unsafe_virtual_path")
    if ext not in ALLOWED_EXTENSIONS:
        errors.append("extension_not_allowed")
    if ext in DENIED_EXTENSIONS:
        errors.append("extension_denied")
    if not override_path.exists():
        warnings.append("override_file_missing")
    if not str(override_path).replace("\\", "/").find("CodeRED_Overrides") >= 0:
        warnings.append("override_path_not_under_CodeRED_Overrides")

    size_bytes = override_path.stat().st_size if override_path.exists() and override_path.is_file() else 0
    digest = sha1_file(override_path) if override_path.exists() and override_path.is_file() else ""
    return {
        "id": str(rule.get("id") or rule_id(virtual_path)),
        "virtual_path": virtual_path,
        "override_path": override_path_value or f"CodeRED_Overrides/{virtual_path}",
        "enabled": bool(rule.get("enabled", False)) and not errors,
        "extension": ext,
        "size_bytes": size_bytes,
        "sha1": digest,
        "proof_only": True,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def scan(game_root: Path) -> dict[str, Any]:
    root = override_root(game_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = load_manifest(game_root)
    manual_rules = {normalize_rel(rule.get("virtual_path", "")): rule for rule in payload.get("rules", []) if rule.get("virtual_path")}
    rules: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.lower() == "manifest.json":
            continue
        rel = normalize_rel(path.relative_to(root))
        existing = manual_rules.pop(rel, {})
        rule = {
            "id": existing.get("id") or rule_id(rel),
            "virtual_path": rel,
            "override_path": f"CodeRED_Overrides/{rel}",
            "enabled": bool(existing.get("enabled", True)),
        }
        validated = validate_rule(game_root, rule)
        if validated["valid"]:
            rules.append(validated)
        else:
            rejected.append({**validated, "reject_reason": "unsafe_relative_path_or_extension_not_allowed"})

    for rel, rule in manual_rules.items():
        validated = validate_rule(game_root, rule)
        if validated["valid"]:
            rules.append(validated)
        else:
            rejected.append({**validated, "reject_reason": "manual_rule_invalid"})

    payload["rules"] = sorted(rules, key=lambda item: item["virtual_path"])
    payload["rejected"] = sorted(rejected, key=lambda item: item["virtual_path"])
    payload["summary"] = {
        "allowed_rules": len(rules),
        "enabled_rules": sum(1 for item in rules if item.get("enabled")),
        "rejected_rules": len(rejected),
        "root": str(root),
        "redirect_adapter_enabled": False,
    }
    return payload


def write_manifest(game_root: Path, replace: bool) -> Path:
    path = manifest_path(game_root)
    if path.exists() and not replace:
        raise FileExistsError(f"Manifest exists. Use --replace to overwrite: {path}")
    return save_manifest(game_root, scan(game_root))


def add_rule(game_root: Path, source: Path, virtual_path: str, replace: bool) -> Path:
    root = override_root(game_root)
    rel = normalize_rel(virtual_path)
    if not is_safe_rel(rel):
        raise ValueError(f"Unsafe virtual path: {virtual_path}")
    ext = Path(rel).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS or ext in DENIED_EXTENSIONS:
        raise ValueError(f"Extension is not allowed in Pass 0.6: {ext}")
    target = root / rel
    if target.exists() and not replace:
        raise FileExistsError(f"Override exists. Use --replace to overwrite: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    save_manifest(game_root, scan(game_root))
    return target


def add_preset(game_root: Path, preset: str, name: str, source: Path, replace: bool) -> Path:
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Choices: {', '.join(sorted(PRESETS))}")
    safe_name = name.strip().replace("\\", "/").strip("/")
    if not safe_name or ".." in Path(safe_name).parts:
        raise ValueError(f"Unsafe preset name: {name}")
    virtual_path = PRESETS[preset].format(name=safe_name)
    return add_rule(game_root, source, virtual_path, replace=replace)


def set_rule_enabled(game_root: Path, rule: str, enabled: bool) -> Path:
    payload = scan(game_root)
    changed = False
    for item in payload.get("rules", []):
        if item.get("id") == rule or item.get("virtual_path") == rule:
            item["enabled"] = bool(enabled and item.get("valid", False))
            changed = True
    if not changed:
        raise KeyError(f"No rule found for: {rule}")
    return save_manifest(game_root, payload)


def validate_manifest(game_root: Path, write_report: bool) -> dict[str, Any]:
    payload = scan(game_root)
    errors = []
    if payload.get("enabled") is not False:
        errors.append("manifest_enabled_must_remain_false_in_pass_0_6")
    if payload.get("file_redirects_enabled") is not False:
        errors.append("file_redirects_enabled_must_remain_false_in_pass_0_6")
    if payload.get("archive_writes_enabled") is not False:
        errors.append("archive_writes_enabled_must_remain_false_in_pass_0_6")
    if payload.get("redirect_adapter", {}).get("enabled") is not False:
        errors.append("redirect_adapter_enabled_must_remain_false_in_pass_0_6")

    report = {
        "version": VERSION,
        "generated_utc": utc_now(),
        "manifest": str(manifest_path(game_root)),
        "root": str(override_root(game_root)),
        "ok": not errors and not payload.get("rejected"),
        "errors": errors,
        "summary": payload.get("summary", {}),
        "rules": payload.get("rules", []),
        "rejected": payload.get("rejected", []),
        "redirect_adapter": payload.get("redirect_adapter", {}),
    }
    if write_report:
        path = report_path(game_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/edit/validate Code RED override manifest proof files.")
    parser.add_argument("--game-root", type=Path, default=Path.cwd(), help="Folder containing the game executable")
    parser.add_argument("--replace", action="store_true", help="Replace existing manifest or override target")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init", help="Create CodeRED_Overrides and manifest.json")
    sub.add_parser("scan", help="Print a scan summary without writing")
    sub.add_parser("validate", help="Validate manifest and print report")
    sub.add_parser("write-report", help="Validate and write CodeRED_ASI_Logs/override_manifest_validation_report.json")
    presets = sub.add_parser("presets", help="List virtual path presets")
    add = sub.add_parser("add", help="Copy one override file and regenerate manifest")
    add.add_argument("source", type=Path)
    add.add_argument("virtual_path")
    add_p = sub.add_parser("add-preset", help="Copy one override file using a virtual path preset")
    add_p.add_argument("preset", choices=sorted(PRESETS))
    add_p.add_argument("name")
    add_p.add_argument("source", type=Path)
    enable = sub.add_parser("enable", help="Enable one proof rule by id or virtual path")
    enable.add_argument("rule")
    disable = sub.add_parser("disable", help="Disable one proof rule by id or virtual path")
    disable.add_argument("rule")
    args = parser.parse_args()

    if args.cmd in {None, "init"}:
        path = write_manifest(args.game_root, replace=args.replace)
        print(f"Manifest: {path}")
        return 0
    if args.cmd == "scan":
        print(json.dumps(scan(args.game_root), indent=2))
        return 0
    if args.cmd == "validate":
        print(json.dumps(validate_manifest(args.game_root, write_report=False), indent=2))
        return 0
    if args.cmd == "write-report":
        print(json.dumps(validate_manifest(args.game_root, write_report=True), indent=2))
        return 0
    if args.cmd == "presets":
        print(json.dumps(PRESETS, indent=2))
        return 0
    if args.cmd == "add":
        target = add_rule(args.game_root, args.source, args.virtual_path, replace=args.replace)
        print(f"Override: {target}")
        print(f"Manifest: {manifest_path(args.game_root)}")
        return 0
    if args.cmd == "add-preset":
        target = add_preset(args.game_root, args.preset, args.name, args.source, replace=args.replace)
        print(f"Override: {target}")
        print(f"Manifest: {manifest_path(args.game_root)}")
        return 0
    if args.cmd == "enable":
        print(f"Manifest: {set_rule_enabled(args.game_root, args.rule, True)}")
        return 0
    if args.cmd == "disable":
        print(f"Manifest: {set_rule_enabled(args.game_root, args.rule, False)}")
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
