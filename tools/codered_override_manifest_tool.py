#!/usr/bin/env python3
"""Code RED override manifest proof tool.

Creates and validates CodeRED_Overrides/manifest.json without enabling live file redirects.
Pass 0.5 is proof-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

ALLOWED_EXTENSIONS = {".xtbl", ".xml", ".txt", ".strtbl", ".wsc", ".json", ".ini", ".cfg"}
DENIED_EXTENSIONS = {".exe", ".dll", ".asi", ".bat", ".cmd", ".ps1"}


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


def normalize_rel(path: Path) -> str:
    return path.as_posix().replace("//", "/").lstrip("/")


def is_safe_rel(rel: str) -> bool:
    if ".." in Path(rel).parts:
        return False
    if rel.startswith("/") or rel.startswith("\\"):
        return False
    return True


def scan(game_root: Path) -> dict:
    root = override_root(game_root)
    root.mkdir(parents=True, exist_ok=True)
    rules = []
    rejected = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.lower() == "manifest.json":
            continue
        rel = normalize_rel(path.relative_to(root))
        ext = path.suffix.lower()
        safe = is_safe_rel(rel)
        allowed = safe and ext in ALLOWED_EXTENSIONS and ext not in DENIED_EXTENSIONS
        item = {
            "id": hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12],
            "virtual_path": rel,
            "override_path": f"CodeRED_Overrides/{rel}",
            "enabled": bool(allowed),
            "extension": ext,
            "size_bytes": path.stat().st_size,
            "sha1": sha1_file(path),
            "proof_only": True,
        }
        if allowed:
            rules.append(item)
        else:
            item["reject_reason"] = "unsafe_relative_path_or_extension_not_allowed"
            rejected.append(item)
    return {
        "version": "0.5.0-override-manifest-proof",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "enabled": False,
        "mode": "proof_only",
        "file_redirects_enabled": False,
        "archive_writes_enabled": False,
        "allow_extensions": sorted(ALLOWED_EXTENSIONS),
        "deny_extensions": sorted(DENIED_EXTENSIONS),
        "rules": rules,
        "rejected": rejected,
        "summary": {
            "allowed_rules": len(rules),
            "rejected_rules": len(rejected),
            "root": str(root),
        },
    }


def write_manifest(game_root: Path, replace: bool) -> Path:
    path = manifest_path(game_root)
    if path.exists() and not replace:
        raise FileExistsError(f"Manifest exists. Use --replace to overwrite: {path}")
    payload = scan(game_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def add_rule(game_root: Path, source: Path, virtual_path: str, replace: bool) -> Path:
    root = override_root(game_root)
    rel = normalize_rel(Path(virtual_path))
    if not is_safe_rel(rel):
        raise ValueError(f"Unsafe virtual path: {virtual_path}")
    ext = Path(rel).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS or ext in DENIED_EXTENSIONS:
        raise ValueError(f"Extension is not allowed in Pass 0.5: {ext}")
    target = root / rel
    if target.exists() and not replace:
        raise FileExistsError(f"Override exists. Use --replace to overwrite: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    write_manifest(game_root, replace=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/validate Code RED override manifest proof files.")
    parser.add_argument("--game-root", type=Path, default=Path.cwd(), help="Folder containing the game executable")
    parser.add_argument("--replace", action="store_true", help="Replace existing manifest or override target")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init", help="Create CodeRED_Overrides and manifest.json")
    sub.add_parser("scan", help="Print a scan summary without writing")
    add = sub.add_parser("add", help="Copy one override file and regenerate manifest")
    add.add_argument("source", type=Path)
    add.add_argument("virtual_path")
    args = parser.parse_args()

    if args.cmd in {None, "init"}:
        path = write_manifest(args.game_root, replace=args.replace)
        print(f"Manifest: {path}")
        return 0
    if args.cmd == "scan":
        print(json.dumps(scan(args.game_root), indent=2))
        return 0
    if args.cmd == "add":
        target = add_rule(args.game_root, args.source, args.virtual_path, replace=args.replace)
        print(f"Override: {target}")
        print(f"Manifest: {manifest_path(args.game_root)}")
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
